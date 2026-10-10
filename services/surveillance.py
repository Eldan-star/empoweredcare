"""
Surveillance queries over the database: weekly series, EPHI threshold detection and the
stored risk index. Used by the /surveillance API endpoints.

Counts can be stored at any level (woreda, zone, facility); a unit's series sums every
row whose P-code starts with the unit's P-code (P-codes nest: ET0407 is inside ET04).
A week with no reported value anywhere in the unit stays None ("no report"), never 0.
"""

from collections import defaultdict
from datetime import date, timedelta
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from db.models import IndicatorCount, OrgUnit, RiskScore
from services.detection import diseases
from services.detection.series import WeekCount, complete, shift
from services.detection.thresholds import evaluate

FIELDS = ("suspected", "confirmed", "deaths", "reports_expected", "reports_received")


def current_week(today: Optional[date] = None) -> tuple[int, int]:
    """The last complete ISO week (Monday-Sunday) before today."""
    y, w, _ = ((today or date.today()) - timedelta(days=7)).isocalendar()
    return y, w


def _containing(pcode: str, units, lengths) -> Optional[str]:
    """The unit (from `units`) whose P-code is a prefix of `pcode`, if any."""
    return next((pcode[:n] for n in lengths if pcode[:n] in units), None)


def _rows(session: Session, prefixes, disease: str, start: tuple[int, int], end: tuple[int, int]):
    """(unit, row) for every count row inside one of the `prefixes` units."""
    prefixes = set(prefixes)
    lengths = sorted({len(p) for p in prefixes}, reverse=True)
    q = select(IndicatorCount).where(func.lower(IndicatorCount.disease) == disease.lower())
    q = q.where((IndicatorCount.iso_year * 100 + IndicatorCount.iso_week) >= start[0] * 100 + start[1])
    q = q.where((IndicatorCount.iso_year * 100 + IndicatorCount.iso_week) <= end[0] * 100 + end[1])
    out = []
    for r in session.scalars(q):
        unit = _containing(r.pcode, prefixes, lengths)
        if unit:
            out.append((unit, r))
    return out


def _sum(rows) -> dict:
    out = {}
    for f in FIELDS:
        vals = [getattr(r, f) for r in rows if getattr(r, f) is not None]
        out[f] = sum(vals) if vals else None
    return out


def weekly_series(session: Session, pcode: str, disease: str = "measles", weeks: int = 52,
                  end: Optional[tuple[int, int]] = None) -> list[WeekCount]:
    end = end or current_week()
    start = shift(*end, -(weeks - 1))
    by_week = defaultdict(list)
    for _, r in _rows(session, [pcode], disease, start, end):
        by_week[(r.iso_year, r.iso_week)].append(r)
    found = [WeekCount(y, w, **_sum(rs)) for (y, w), rs in by_week.items()]
    return complete(found, start, end)


def detect(session: Session, disease: str = "measles", week: Optional[tuple[int, int]] = None,
           level: int = 3, humanitarian: set[str] = frozenset(), history_weeks: int = 12) -> list[dict]:
    """EPHI levels for every unit at `level` with any data in the last `history_weeks`
    weeks, ordered: action threshold first, then alert, then by priority."""
    cfg = diseases.get(disease)
    week = week or current_week()
    start = shift(*week, -(history_weeks - 1))
    units = {u.pcode: u for u in session.scalars(select(OrgUnit).where(OrgUnit.level == level))}
    rows_by_unit = defaultdict(lambda: defaultdict(list))
    for unit, r in _rows(session, units, disease, start, week):
        rows_by_unit[unit][(r.iso_year, r.iso_week)].append(r)
    out = []
    for pcode, weeks_rows in rows_by_unit.items():
        series = complete([WeekCount(y, w, **_sum(rs)) for (y, w), rs in weeks_rows.items()], start, week)
        res = evaluate(series, cfg, humanitarian=pcode in humanitarian, weeks=[-1])[0]
        u = units[pcode]
        out.append({"pcode": pcode, "name": u.name, "parent_pcode": u.parent_pcode, **res.as_dict()})
    rank = {"action": 0, "alert": 1, None: 2}
    out.sort(key=lambda r: (rank[r["level"]], -r["priority"], r["pcode"]))
    return out


def latest_risk(session: Session, year: Optional[int] = None, month: Optional[int] = None,
                model_version: str = "v1") -> list[dict]:
    q = select(RiskScore).where(RiskScore.model_version == model_version)
    if year and month:
        q = q.where(RiskScore.year == year, RiskScore.month == month)
    else:
        last = session.execute(select(RiskScore.year, RiskScore.month).where(RiskScore.model_version == model_version)
                               .order_by(RiskScore.year.desc(), RiskScore.month.desc()).limit(1)).first()
        if not last:
            return []
        q = q.where(RiskScore.year == last[0], RiskScore.month == last[1])
    names = dict(session.execute(select(OrgUnit.pcode, OrgUnit.name)).all())
    rows = session.scalars(q.order_by(RiskScore.risk_index.desc())).all()
    return [{"pcode": r.pcode, "name": names.get(r.pcode), "year": r.year, "month": r.month,
             "risk_index": r.risk_index, "susceptibles": r.susceptibles, "reporting_rate": r.reporting_rate,
             "p_eff": r.p_eff, "importation_pressure": r.importation_pressure, "factors": r.factors}
            for r in rows]
