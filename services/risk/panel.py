"""
Run the measles risk model month by month over a panel of zones (months x zones arrays).

The same function serves real data (built from the database by `runner.py`) and
simulated data (the evaluation harness). Every month uses only data up to that month, so
results are what the model would have said at the time (no look-ahead), which is what a
backtest needs.
"""

from dataclasses import dataclass, field
from typing import Optional

import numpy as np

from services.risk import measles_risk as mr


@dataclass
class Panel:
    pcodes: list[str]
    population: np.ndarray            # (zones,)
    lat: np.ndarray
    lon: np.ndarray
    months: list[tuple[int, int]]     # (year, month), consecutive
    births: np.ndarray                # (months, zones) births per month
    mcv1: np.ndarray                  # (months, zones) coverage 0-1
    mcv2: np.ndarray
    cases: np.ndarray                 # (months, zones) reported cases, settled; NaN = no report
    # Backtests only: what had arrived by each month's own end (late reports missing). When
    # given, month t sees provisional values for its last `settle_months` months and settled
    # values before that, as the live system would.
    cases_provisional: Optional[np.ndarray] = None
    # Backtests only: what had arrived by the end of the FOLLOWING month (lag 1).
    cases_provisional_lag1: Optional[np.ndarray] = None
    sia_coverage: Optional[np.ndarray] = None   # (months, zones), 0 where no campaign
    sia_target_share: object = 51 / 180         # 9-59 months under an even spread; or (months, zones)
    region: Optional[list[str]] = None          # region code per zone, for pooling rho
    threats: Optional[list[list[str]]] = None   # per zone, current context factors


@dataclass
class PanelResult:
    s: np.ndarray            # (months, zones) susceptibles at month end
    rho: np.ndarray          # (months, zones) reporting rate used
    rho_estimated: np.ndarray  # (months, zones) bool: from data (True) or fallback
    peff: np.ndarray
    lam: np.ndarray
    index: np.ndarray        # 1-month horizon, 0-100
    index_3m: np.ndarray
    silent: np.ndarray       # (months, zones) bool
    factors: list[list[dict]] = field(default_factory=list)  # per month, per zone


def _rho_for_month(panel: Panel, unvacc: np.ndarray, cases: np.ndarray, t: int,
                   min_months: int, prior_months: float, window_months: int) -> tuple[np.ndarray, np.ndarray]:
    zones = len(panel.pcodes)
    lo = max(0, t + 1 - window_months)  # a rolling window: reporting and coverage change over years
    est = [mr.reporting_rate(unvacc[lo:t + 1, z], cases[lo:t + 1, z]) if t + 1 >= min_months else None
           for z in range(zones)]
    rates = np.array([e.rate for e in est if e is not None])
    national = float(np.median(rates)) if len(rates) else 1.0  # 1.0 = no correction possible
    regions = panel.region or ["all"] * zones
    regional = {}
    for r in set(regions):
        rs = [e.rate for e, rr in zip(est, regions) if e is not None and rr == r]
        regional[r] = float(np.median(rs)) if rs else national
    rho = np.array([mr.pooled_rate(est[z], regional[regions[z]], prior_months) for z in range(zones)])
    return rho, np.array([e is not None for e in est])


def _seen_by_lag(panel: Panel) -> dict:
    out = {}
    if panel.cases_provisional is not None:
        out[0] = panel.cases_provisional
    if panel.cases_provisional_lag1 is not None:
        out[1] = panel.cases_provisional_lag1
    return out


def _known(panel: Panel, t: int, settle_months: int, nowcast: bool = False) -> np.ndarray:
    """Cases for months 0..t as known at the end of month t: settled history, then each
    recent month as seen at its lag (lag 0 = this month), optionally nowcast."""
    seen = _seen_by_lag(panel)
    if not seen:
        return panel.cases[:t + 1]
    k = panel.cases[:t + 1].copy()
    for lag in range(settle_months):
        m = t - lag
        if m < 0:
            break
        src = seen.get(lag, seen.get(0))  # no lag-1 view: the lag-0 view is the best known
        if src is not None:
            k[m] = src[m]
    if nowcast:
        from services.risk import nowcast as nc
        k, _ = nc.apply(k, panel.cases, {lag: v for lag, v in seen.items() if lag < settle_months}, t)
    return k


def run(panel: Panel, incidence_months: int = 2, silent_months: int = 1, min_months: int = 24,
        prior_months: float = 36.0, ve1: float = mr.VE1, ve2: float = mr.VE2, r0: float = mr.R0,
        settle_months: int = 2, rho_window_months: int = 96, nowcast: bool = True,
        **gravity) -> PanelResult:
    T, Z = panel.births.shape
    peff = mr.p_eff(panel.mcv1, panel.mcv2, ve1, ve2)
    unvacc = panel.births * (1 - peff)
    dist = mr.distance_matrix(panel.lat, panel.lon)
    sia = panel.sia_coverage if panel.sia_coverage is not None else np.zeros((T, Z))

    z, zb = (lambda: np.zeros((T, Z))), (lambda: np.zeros((T, Z), bool))
    out = PanelResult(s=z(), rho=z(), rho_estimated=zb(), peff=z(), lam=z(), index=z(),
                      index_3m=z(), silent=zb())
    s0 = mr.initial_susceptibles(panel.population, r0)
    s = s0
    for t in range(T):
        known = _known(panel, t, settle_months, nowcast)
        reported = ~np.isnan(known)
        cases = np.nan_to_num(known, nan=0.0)
        rho, estimated = _rho_for_month(panel, unvacc, cases, t, min_months, prior_months, rho_window_months)
        share = (lambda m: panel.sia_target_share[m] if np.ndim(panel.sia_target_share) == 2
                 else panel.sia_target_share)
        if panel.cases_provisional is None:
            s = mr.step_susceptibles(s, panel.births[t], peff[t], cases[t], rho,
                                     mr.sia_immunized(s, sia[t], share(t), ve2))
        else:  # data were revised: rebuild the susceptible path from the start
            s = s0
            for m in range(t + 1):
                s = mr.step_susceptibles(s, panel.births[m], peff[m], cases[m], rho,
                                         mr.sia_immunized(s, sia[m], share(m), ve2))
        lo = max(0, t - incidence_months + 1)
        incidence = cases[lo:t + 1].sum(axis=0) / rho
        silent = ~reported[max(0, t - silent_months + 1):t + 1].any(axis=0)
        res = mr.score(s, panel.population, incidence, dist, panel.births[t], peff[t],
                       silent=silent, threats=panel.threats, **gravity)
        out.s[t], out.rho[t], out.rho_estimated[t], out.peff[t] = s, rho, estimated, peff[t]
        out.lam[t], out.index[t], out.index_3m[t], out.silent[t] = res.lam, res.index, res.index_3m, silent
        out.factors.append(res.factors)
    return out
