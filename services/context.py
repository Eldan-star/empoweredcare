"""
Context factors (displacement, conflict) turned into the named pathways of SYSTEM_SPEC 5.6.

- Threat / priority factor: a unit hosting many displaced people gets a visible
  "displacement" factor (raises priority within an EPHI level, shown as evidence).
- Vaccination disruption (optional, for sensitivity analysis): coverage in units with
  conflict displacement can be reduced by a stated fraction. Off by default, because the
  size of the effect in Ethiopia is not known.
- Surveillance quality is handled by the silence and completeness flags in detection.

Thresholds are design choices, stated here and in METHODOLOGY 5.2, to be reviewed with
EPHI.
"""

from datetime import date
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from db.models import ContextFactor, OrgUnit

DISPLACEMENT_SHARE = 0.10     # IDPs hosted >= 10% of the zone's population, or
DISPLACEMENT_MIN = 100_000    # >= 100,000 IDPs (about 15-20 of 107 zones in the Aug 2024 DTM round)
CONFLICT_SHARE = 0.05         # disruption sensitivity: conflict IDPs >= 5% of the zone
MAX_AGE_MONTHS = 12           # ignore DTM rounds older than this


def latest(session: Session, factor: str, as_of: Optional[date] = None) -> dict[str, float]:
    """{pcode: value} from the most recent period up to `as_of` (within MAX_AGE_MONTHS)."""
    as_of = as_of or date.today()
    rows = session.scalars(select(ContextFactor).where(ContextFactor.factor == factor,
                                                       ContextFactor.period_start <= as_of)
                           .order_by(ContextFactor.period_start)).all()
    out = {}
    for r in rows:
        months = (as_of.year - r.period_start.year) * 12 + as_of.month - r.period_start.month
        if months <= MAX_AGE_MONTHS and r.value is not None:
            out[r.pcode] = r.value
    return out


def threat_factors(session: Session, as_of: Optional[date] = None) -> dict[str, list[str]]:
    """{pcode: ["displacement"]} for zones over the thresholds AND every unit inside them
    (DTM reports by zone)."""
    idps = latest(session, "idps_hosted", as_of)
    units = {u.pcode: u for u in session.scalars(select(OrgUnit))}
    flagged = {p for p, v in idps.items()
               if p in units and (v >= DISPLACEMENT_MIN or (units[p].population and v / units[p].population >= DISPLACEMENT_SHARE))}
    out = {}
    for p, u in units.items():
        anc, chain = p, []
        while anc:
            chain.append(anc)
            anc = units[anc].parent_pcode if anc in units else None
        if flagged.intersection(chain):
            out[p] = ["displacement"]
    return out


def disrupted_coverage(session: Session, as_of: Optional[date] = None, reduction: float = 0.0) -> dict[str, float]:
    """{pcode: multiplier} for coverage in zones hosting conflict-displaced people, for a
    sensitivity run (multiplier = 1 - reduction). Empty when reduction is 0."""
    if reduction <= 0:
        return {}
    conflict = latest(session, "idps_conflict", as_of)
    units = {u.pcode: u for u in session.scalars(select(OrgUnit))}
    return {p: 1 - reduction for p, v in conflict.items()
            if p in units and units[p].population and v / units[p].population >= CONFLICT_SHARE}
