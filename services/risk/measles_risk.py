"""
Measles ignition-risk model (SYSTEM_SPEC section 5, METHODOLOGY sections 4.1-4.6).

Pure functions over arrays, one entry per zone, so the same code runs on real data, on
simulated data and in tests. Every default is a parameter so sensitivity analysis can
vary it.

The output is a ranked index (0-100 within a month), not a probability.
"""

import math
from dataclasses import dataclass, field
from typing import Optional, Sequence

import numpy as np

# --- 4.1 Vaccine protection ------------------------------------------------------------

VE1 = 0.84  # first dose at 9 months; Uzicanin & Zimmerman 2011 (range 0.80-0.90)
VE2 = 0.90  # second dose protecting a first-dose failure (range 0.85-0.95)


def p_eff(mcv1, mcv2, ve1: float = VE1, ve2: float = VE2):
    """Share of a birth cohort protected by routine vaccination.
    MCV2 is given almost only to MCV1 recipients, so it is capped at MCV1 and protects
    mainly the children whose first dose failed: P = MCV1*VE1 + MCV2*(1-VE1)*VE2."""
    mcv1 = np.clip(np.asarray(mcv1, dtype=float), 0, 1)
    mcv2 = np.minimum(np.clip(np.asarray(mcv2, dtype=float), 0, 1), mcv1)
    return mcv1 * ve1 + mcv2 * (1 - ve1) * ve2


# --- 4.2 Susceptible accumulation ------------------------------------------------------

AGE_BAND_MONTHS = 15 * 12  # children 0-14 years
R0 = 15.0  # measles basic reproduction number, commonly 12-18


def initial_susceptibles(population, r0: float = R0):
    """Endemic-equilibrium starting point S* = N / R0 (basic SIR theory). A burn-in over
    historical coverage then moves S away from it; the starting value matters less the
    longer the burn-in."""
    return np.asarray(population, dtype=float) / r0


def step_susceptibles(s_prev, births, peff, cases, reporting_rate, sia_immunized=0.0,
                      age_band_months: int = AGE_BAND_MONTHS):
    """One month of S_t = S_{t-1} + B(1-P_eff) - C/rho - SIA - ageing.

    Ageing removes S/age_band per month, assuming susceptibles spread evenly across the
    0-14 age band (a simplification). True infections C/rho cannot exceed the pool."""
    s_prev = np.asarray(s_prev, dtype=float)
    rho = np.clip(np.asarray(reporting_rate, dtype=float), 1e-3, 1.0)
    gained = np.asarray(births, dtype=float) * (1 - np.asarray(peff, dtype=float))
    infections = np.asarray(cases, dtype=float) / rho
    ageing = s_prev / age_band_months
    s = s_prev + gained - ageing
    s = s - np.minimum(infections, s)
    s = s - np.minimum(np.asarray(sia_immunized, dtype=float), s)
    return np.maximum(s, 0.0)


def sia_immunized(s, coverage, target_share, ve: float = VE2):
    """Children made immune by a campaign: susceptibles in the target ages x coverage x VE.
    target_share is the share of the susceptible pool in the campaign's age range (for
    9-59 months under an even spread: 51/180)."""
    return np.asarray(s, dtype=float) * np.asarray(target_share) * np.asarray(coverage) * ve


# --- 4.3 Reporting rate (susceptible reconstruction) -------------------------------------

@dataclass
class ReportingRate:
    rate: float              # share of infections reported
    slope: float             # d(cumulative births) / d(cumulative cases) = 1 / rate
    months: int
    residuals: np.ndarray    # reconstructed susceptible deviations D_t


def reporting_rate(unvaccinated_births: Sequence[float], cases: Sequence[float]) -> Optional[ReportingRate]:
    """Finkenstaedt & Grenfell 2000: regress cumulative (unvaccinated) births X on
    cumulative reported cases Y; with every susceptible eventually infected, X = Y/rate +
    D, so the slope estimates 1/rate and the residuals D are the susceptible deviations.
    Unvaccinated births reduce the bias the standard estimator has under vaccination
    (PLOS ONE 2025, SYSTEM_SPEC ref 3). Returns None when there are too few cases."""
    x = np.cumsum(np.asarray(unvaccinated_births, dtype=float))
    y = np.cumsum(np.asarray(cases, dtype=float))
    if len(x) < 12 or y[-1] <= 0 or np.ptp(y) == 0:
        return None
    slope, intercept = np.polyfit(y, x, 1)
    if slope <= 0:
        return None
    rate = float(np.clip(1.0 / slope, 1e-3, 1.0))
    return ReportingRate(rate, float(slope), len(x), x - (slope * y + intercept))


def pooled_rate(zone: Optional[ReportingRate], regional_rate: float, prior_months: float = 36.0) -> float:
    """Shrink a zone's estimate toward its region's when the zone has little data:
    weight = months / (months + prior_months). Zones with no estimate take the regional
    value."""
    if zone is None:
        return regional_rate
    w = zone.months / (zone.months + prior_months)
    return w * zone.rate + (1 - w) * regional_rate


# --- 4.4 Importation pressure (gravity) --------------------------------------------------

GRAVITY_A = 0.0   # exponent on source population; incidence I_j already scales with N_j
GRAVITY_C = 2.0   # distance decay
MIN_DISTANCE_KM = 10.0
MAX_DISTANCE_KM = 600.0
# Unobserved introductions (travellers, unreported cases), in infections per month. Keeps
# the ranking meaningful between epidemics: with no recorded infections anywhere, zones
# rank by their susceptible share instead of all tying.
BACKGROUND = 0.1


def importation_pressure(s, population, incidence, distance_km, a: float = GRAVITY_A,
                         c: float = GRAVITY_C, min_km: float = MIN_DISTANCE_KM,
                         max_km: float = MAX_DISTANCE_KM, background: float = BACKGROUND):
    """lambda_i = (S_i/N_i) * (I_i + sum_{j != i} N_j^a I_j / d_ij^c + background), with I = estimated
    true infections (cases / rho) over the last 4-8 weeks. Returns (lambda, local, imported)
    so explanations can say whether pressure is local or from neighbours.
    Initial exponents are placeholders for ranking, to be fitted on Ethiopian history
    (Xia, Bjornstad & Grenfell 2004 give the gravity form) and varied in sensitivity runs."""
    s = np.asarray(s, dtype=float)
    n = np.maximum(np.asarray(population, dtype=float), 1.0)
    inc = np.asarray(incidence, dtype=float)
    d = np.maximum(np.asarray(distance_km, dtype=float), min_km)
    w = (n[None, :] ** a) / d ** c
    w[np.asarray(distance_km) > max_km] = 0.0
    np.fill_diagonal(w, 0.0)
    imported = w @ inc
    share = s / n
    return share * (inc + imported + background), share * inc, share * imported


def distance_matrix(lat: Sequence[float], lon: Sequence[float]) -> np.ndarray:
    """Great-circle distances in km between unit centroids."""
    la, lo = np.radians(np.asarray(lat, float)), np.radians(np.asarray(lon, float))
    dlat = la[:, None] - la[None, :]
    dlon = lo[:, None] - lo[None, :]
    h = np.sin(dlat / 2) ** 2 + np.cos(la[:, None]) * np.cos(la[None, :]) * np.sin(dlon / 2) ** 2
    return 2 * 6371.0 * np.arcsin(np.sqrt(np.clip(h, 0, 1)))


# --- 4.6 Index and explanation -------------------------------------------------------------

def rank_index(values) -> np.ndarray:
    """Rescale to a 0-100 rank within the month (ties share the average rank)."""
    v = np.asarray(values, dtype=float)
    if len(v) == 1:
        return np.array([50.0])
    order = v.argsort(kind="mergesort")
    ranks = np.empty(len(v))
    ranks[order] = np.arange(len(v))
    for val in np.unique(v):  # average ties
        idx = v == val
        ranks[idx] = ranks[idx].mean()
    return 100.0 * ranks / (len(v) - 1)


@dataclass
class RiskResult:
    index: np.ndarray            # 0-100 rank, 1-month horizon
    index_3m: np.ndarray         # 0-100 rank, 3-month horizon (mostly susceptibility)
    lam: np.ndarray
    susceptible_share: np.ndarray
    local: np.ndarray
    imported: np.ndarray
    factors: list[dict] = field(default_factory=list)


def score(s, population, incidence, distance_km, births_per_month, peff,
          silent: Optional[Sequence[bool]] = None, threats: Optional[Sequence[Sequence[str]]] = None,
          **gravity) -> RiskResult:
    """Risk index for every zone for one month, with the factors behind each rank."""
    lam, local, imported = importation_pressure(s, population, incidence, distance_km, **gravity)
    n = np.maximum(np.asarray(population, float), 1.0)
    share = np.asarray(s, float) / n
    # 3-month horizon: three months of births at current coverage, infections unknown, so
    # recent incidence is held at its current level.
    s3 = np.asarray(s, float)
    for _ in range(3):
        s3 = step_susceptibles(s3, births_per_month, peff, 0.0, 1.0)
    lam3, _, _ = importation_pressure(s3, population, incidence, distance_km, **gravity)
    idx, idx3 = rank_index(lam), rank_index(lam3)
    share_rank = rank_index(share)
    factors = []
    for i in range(len(n)):
        f = {
            "susceptible_share": round(float(share[i]), 4),
            "susceptible_share_rank": round(float(share_rank[i]), 1),
            "local_pressure": round(float(local[i]), 6),
            "imported_pressure": round(float(imported[i]), 6),
            "main_driver": ("susceptible build-up; no recent infections nearby"
                            if local[i] + imported[i] < 0.1 * lam[i]
                            else "infections nearby" if imported[i] > local[i] else "infections in the zone"),
        }
        if silent is not None and silent[i]:
            f["surveillance_silent"] = True  # low counts here may be missing data
        if threats is not None and threats[i]:
            f["threat_factors"] = list(threats[i])
        factors.append(f)
    return RiskResult(idx, idx3, lam, share, local, imported, factors)
