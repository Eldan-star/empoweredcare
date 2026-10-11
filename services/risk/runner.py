"""
Build the risk panel from the database and store monthly risk scores (risk_scores).

Inputs:
- zones (org_units at `level`, default 2) with population and centroid (OCHA load);
- vaccination coverage (`immunization`; scripts/load_immunization.py). A row with month 0
  is an annual estimate. Each month uses that month's row, else the same year's annual
  row, else the latest earlier value;
- births from `immunization.births` when present, else population x crude birth rate;
- reported cases (`indicator_counts`, any level inside the zone), by month;
- campaigns (`campaigns`, at the zone, inside it, or at its region).

Only zones with coverage data are scored; the result says which were skipped.
"""

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Optional

import numpy as np
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from db.models import Campaign, CountSnapshot, Demographics, Immunization, IndicatorCount, OrgUnit, RiskScore
from services.risk import measles_risk as mr
from services.risk.panel import Panel, PanelResult, run

CRUDE_BIRTH_RATE = 31.9  # per 1,000 per year, Ethiopia 2023 (World Bank SP.DYN.CBRT.IN)
MODEL_VERSION = "v1"


@dataclass
class Built:
    panel: Optional[Panel]
    skipped_no_coverage: list[str] = field(default_factory=list)
    births_estimated: bool = False
    notes: list[str] = field(default_factory=list)


def _months(end: tuple[int, int], n: int) -> list[tuple[int, int]]:
    y, m = end
    out = []
    for _ in range(n):
        out.append((y, m))
        y, m = (y, m - 1) if m > 1 else (y - 1, 12)
    return out[::-1]


def _week_month(iso_year: int, iso_week: int) -> tuple[int, int]:
    d = date.fromisocalendar(iso_year, iso_week, 4)  # the Thursday decides, as in ISO 8601
    return d.year, d.month


def build_panel(session: Session, end: tuple[int, int], years: int = 10, level: int = 2,
                disease: str = "measles") -> Built:
    months = _months(end, years * 12)
    idx = {k: i for i, k in enumerate(months)}
    zones = session.scalars(select(OrgUnit).where(OrgUnit.level == level, OrgUnit.lat.is_not(None))
                            .order_by(OrgUnit.pcode)).all()
    # Databases loaded before population roll-up: sum the units inside each zone.
    child_pop = defaultdict(int)
    for u in session.scalars(select(OrgUnit).where(OrgUnit.level == level + 1, OrgUnit.population.is_not(None))):
        child_pop[u.parent_pcode] += u.population
    for z in zones:
        if z.population is None and child_pop.get(z.pcode):
            z.population = child_pop[z.pcode]
    zones = [z for z in zones if z.population]
    if not zones:
        return Built(None, notes=[f"No level-{level} units with population and centroid. Load the OCHA boundaries first."])

    imm = defaultdict(dict)
    for r in session.scalars(select(Immunization)):
        imm[r.pcode][(r.year, r.month)] = r
    keep = [z for z in zones if z.pcode in imm]
    built = Built(None, skipped_no_coverage=[z.pcode for z in zones if z.pcode not in imm])
    if not keep:
        built.notes.append("No vaccination coverage loaded. Run scripts/load_immunization.py first.")
        return built

    T, Z = len(months), len(keep)
    mcv1, mcv2, births = np.full((T, Z), np.nan), np.full((T, Z), np.nan), np.full((T, Z), np.nan)
    for j, z in enumerate(keep):
        rows = imm[z.pcode]
        last = None
        for i, (y, m) in enumerate(months):
            r = rows.get((y, m)) or rows.get((y, 0))
            if r is None:
                earlier = [k for k in rows if k <= (y, m)]
                r = rows[max(earlier)] if earlier else last
            if r is None:  # nothing yet: use the earliest available
                r = rows[min(rows)]
            last = r
            mcv1[i, j] = r.mcv1_coverage if r.mcv1_coverage is not None else np.nan
            mcv2[i, j] = r.mcv2_coverage if r.mcv2_coverage is not None else 0.0
            births[i, j] = r.births if r.births else np.nan
    pop = np.array([z.population for z in keep], float)
    if np.isnan(births).any():
        # Next: births per unit from the demographics table (scripts/load_births.py),
        # else the national crude birth rate.
        demo = {}
        for d in session.scalars(select(Demographics).order_by(Demographics.year)):
            demo[d.pcode] = d
        rate = np.array([(demo[z.pcode].births / z.population * 1000) if z.pcode in demo and demo[z.pcode].births
                         else np.nan for z in keep])
        built.births_estimated = bool(np.isnan(rate).any())
        rate = np.where(np.isnan(rate), CRUDE_BIRTH_RATE, rate)
        if not built.births_estimated:
            built.notes.append("Births: per-zone rates from the demographics table.")
        est = np.tile(pop * rate / 1000 / 12, (T, 1))
        births = np.where(np.isnan(births), est, births)
    mcv1 = np.nan_to_num(mcv1, nan=0.0)

    cases = np.full((T, Z), np.nan)
    zone_of = {z.pcode: j for j, z in enumerate(keep)}
    lengths = sorted({len(p) for p in zone_of}, reverse=True)
    q = select(IndicatorCount).where(func.lower(IndicatorCount.disease) == disease, IndicatorCount.suspected.is_not(None))
    for r in session.scalars(q):
        j = next((zone_of[r.pcode[:n]] for n in lengths if r.pcode[:n] in zone_of), None)
        i = idx.get(_week_month(r.iso_year, r.iso_week))
        if j is not None and i is not None:
            cases[i, j] = (0 if np.isnan(cases[i, j]) else cases[i, j]) + r.suspected

    lag0, lag1 = _lagged_from_snapshots(session, months, idx, zone_of, lengths, disease)

    sia = np.zeros((T, Z))
    share = np.full((T, Z), 51 / 180)
    for c in session.scalars(select(Campaign).where(func.lower(Campaign.vaccine).like("%measles%"))):
        i = idx.get((c.start_date.year, c.start_date.month))
        if i is None or c.coverage is None:
            continue
        for j, z in enumerate(keep):
            if c.pcode.startswith(z.pcode) or z.pcode.startswith(c.pcode):
                sia[i, j] = max(sia[i, j], c.coverage)
                lo, hi = c.age_min_months or 9, c.age_max_months or 59
                share[i, j] = max(0.0, min(hi - lo + 1, mr.AGE_BAND_MONTHS)) / mr.AGE_BAND_MONTHS
    built.panel = Panel(pcodes=[z.pcode for z in keep], population=pop,
                        lat=np.array([z.lat for z in keep]), lon=np.array([z.lon for z in keep]),
                        months=months, births=births, mcv1=mcv1, mcv2=mcv2, cases=cases,
                        cases_provisional=lag0, cases_provisional_lag1=lag1,
                        sia_coverage=sia, sia_target_share=share, region=[z.parent_pcode or "" for z in keep])
    return built


def _month_end(y: int, m: int) -> datetime:
    nxt = date(y + (m == 12), m % 12 + 1, 1)
    return datetime.combine(nxt, datetime.min.time(), tzinfo=timezone.utc)


def _lagged_from_snapshots(session, months, idx, zone_of, lengths, disease):
    """Monthly zone counts as they looked at the end of the same month (lag 0) and of the
    next month (lag 1), rebuilt from count_snapshots. (None, None) when there are no
    snapshots, in which case no nowcast is applied."""
    snaps = session.scalars(select(CountSnapshot).where(func.lower(CountSnapshot.disease) == disease)
                            .order_by(CountSnapshot.observed_at)).all()
    if not snaps:
        return None, None
    by_week = defaultdict(list)
    for sn in snaps:
        j = next((zone_of[sn.pcode[:n]] for n in lengths if sn.pcode[:n] in zone_of), None)
        i = idx.get(_week_month(sn.iso_year, sn.iso_week))
        if j is not None and i is not None:
            by_week[(sn.pcode, sn.iso_year, sn.iso_week)].append((sn.observed_at, sn.suspected, i, j))
    T, Z = len(months), len(zone_of)
    out = []
    for lag in (0, 1):
        arr = np.full((T, Z), np.nan)
        for versions in by_week.values():
            i, j = versions[0][2], versions[0][3]
            if i + lag >= T:
                continue
            cutoff = _month_end(*months[i + lag])
            seen = [v for obs, v, _, _ in versions if _aware(obs) <= cutoff and v is not None]
            if seen:
                arr[i, j] = (0 if np.isnan(arr[i, j]) else arr[i, j]) + seen[-1]
        out.append(arr)
    return out[0], out[1]


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def store(session: Session, panel: Panel, res: PanelResult, last_months: int = 12) -> int:
    """Upsert the last `last_months` months of results into risk_scores."""
    n = 0
    T = len(panel.months)
    existing = {(r.pcode, r.year, r.month): r for r in session.scalars(
        select(RiskScore).where(RiskScore.model_version == MODEL_VERSION))}
    for t in range(max(0, T - last_months), T):
        y, m = panel.months[t]
        for j, pcode in enumerate(panel.pcodes):
            row = existing.get((pcode, y, m)) or RiskScore(pcode=pcode, year=y, month=m, model_version=MODEL_VERSION)
            row.susceptibles = float(res.s[t, j])
            row.reporting_rate = float(res.rho[t, j])
            row.p_eff = float(res.peff[t, j])
            row.importation_pressure = float(res.lam[t, j])
            row.risk_index = float(res.index[t, j])
            row.factors = {**res.factors[t][j], "index_3m": round(float(res.index_3m[t, j]), 1),
                           "reporting_rate_from_data": bool(res.rho_estimated[t, j])}
            session.add(row)
            n += 1
    return n
