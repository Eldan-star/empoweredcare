"""
Disease settings for detection (SYSTEM_SPEC section 6, METHODOLOGY section 4.7).

Every number here comes from the EPHI PHEM Guideline 2022 (docs/references/ephi), Table
4-5 (pp. 67-70) and Table 4-6 (humanitarian settings, p. 71), unless marked "internal".
Diseases share one rule shape so that new diseases are added as data, not code.

A rule fires when, over the last `window_weeks` ISO weeks (current week included), the
suspected total reaches `suspected` OR the confirmed total reaches `confirmed`. A field
left as None is not part of the rule.
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass(frozen=True)
class CountRule:
    suspected: Optional[int] = None
    confirmed: Optional[int] = None
    window_weeks: int = 1

    def met(self, suspected: int, confirmed: int) -> bool:
        return ((self.suspected is not None and suspected >= self.suspected)
                or (self.confirmed is not None and confirmed >= self.confirmed))


@dataclass(frozen=True)
class DiseaseConfig:
    name: str
    alert: CountRule
    action: CountRule
    source: str
    # Internal priority flag below the action threshold (not an EPHI rule).
    approaching: Optional[CountRule] = None
    # Humanitarian alert: current week at least `factor` x the mean of the previous
    # `weeks` weeks (Table 4-6). None where EPHI gives no rule.
    humanitarian_factor: Optional[float] = None
    humanitarian_weeks: int = 3
    # Acceptable case fatality rate; a higher rate in an outbreak is flagged. The flag
    # needs at least `cfr_min_cases` cases in the window so one death in a handful of
    # cases does not trip it (internal choice).
    acceptable_cfr: Optional[float] = None
    cfr_min_cases: int = 10
    # Diseases whose thresholds need multi-year baselines or population rates (malaria,
    # meningitis, dysentery) are listed here until their rules are implemented.
    notes: list[str] = field(default_factory=list)


# "Within 1 month" is applied as the last 4 ISO weeks, because routine data is weekly.
# Configurable; EPHI to confirm (docs/EPHI_ALIGNMENT.md section 5).
MONTH_WEEKS = 4

PHEM = "EPHI PHEM Guideline 2022, Table 4-5"

DISEASES: dict[str, DiseaseConfig] = {
    "measles": DiseaseConfig(
        name="measles",
        alert=CountRule(suspected=1),
        action=CountRule(suspected=5, confirmed=3, window_weeks=MONTH_WEEKS),
        approaching=CountRule(suspected=3, confirmed=2, window_weeks=MONTH_WEEKS),
        humanitarian_factor=2.0,
        humanitarian_weeks=3,
        acceptable_cfr=0.03,
        source=f"{PHEM} (pp. 67-68); Table 4-6 (p. 71)",
    ),
    # Single suspected case = alert, single confirmed case = action.
    **{name: DiseaseConfig(name=name, alert=CountRule(suspected=1), action=CountRule(confirmed=1),
                           acceptable_cfr=cfr, source=PHEM)
       for name, cfr in [("cholera", 0.01), ("anthrax", None), ("yellow_fever", None),
                         ("dengue", 0.01), ("chikungunya", 0.001), ("mpox", None),
                         ("rift_valley_fever", None), ("vhf", None), ("afp_polio", 0.05)]},
}


def get(disease: str) -> DiseaseConfig:
    key = disease.strip().lower().replace(" ", "_")
    if key not in DISEASES:
        raise KeyError(f"No detection settings for {disease!r}. Known: {', '.join(sorted(DISEASES))}")
    return DISEASES[key]
