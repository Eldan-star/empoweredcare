"""
EPHI threshold rules and the evidence ladder for one unit (SYSTEM_SPEC sections 6 and 8).

For each week the result gives:
- `level`: "action", "alert" or None, from EPHI's rules only;
- evidence that ranks results within a level but never changes it: approaching the
  action threshold, early-rise statistics, case fatality, surveillance silence and
  report completeness, plus any risk index or context factors passed in;
- `priority` (0-100) for ordering within a level.

"Signal" (unverified reports) is the third level. It comes from the signals table, not
from counts, and is added when signals are fused with counts (M5).
"""

from dataclasses import dataclass, field
from typing import Optional, Sequence

from services.detection import early_rise
from services.detection.diseases import DiseaseConfig
from services.detection.series import WeekCount, value

# Weeks without a report, ending in the current week, after which a unit is "silent".
SILENT_WEEKS = 2
# Minimum share of expected reports. CEBS Manual 2021 p. 14 sets 80% as the minimum for
# community notification timeliness, "same as with the national indicator based
# surveillance" requirement.
MIN_COMPLETENESS = 0.8

# Points for ordering results within a level. A transparent design choice, shown with
# every result and to be reviewed with EPHI (METHODOLOGY section 4.10).
PRIORITY_POINTS = {
    "approaching_action": 20,
    "early_rise_per_method": 10,   # up to 4 methods
    "cfr_above_acceptable": 20,
    "risk_index_max": 30,          # scaled by the 0-100 risk index
    "per_threat_factor": 5,        # conflict, displacement, ... up to 2
    "space_time_cluster": 10,      # inside a significant space-time cluster (p <= 0.05)
}


@dataclass
class WeekResult:
    iso_year: int
    iso_week: int
    level: Optional[str]
    reasons: list[str] = field(default_factory=list)
    window: dict = field(default_factory=dict)
    flags: dict = field(default_factory=dict)
    early_rise: dict = field(default_factory=dict)
    priority: float = 0.0
    priority_parts: dict = field(default_factory=dict)

    def as_dict(self) -> dict:
        return {k: getattr(self, k) for k in self.__dataclass_fields__}


def _window(series: Sequence[WeekCount], t: int, weeks: int) -> Sequence[WeekCount]:
    return series[max(0, t - weeks + 1):t + 1]


def _silent_run(series: Sequence[WeekCount], t: int) -> int:
    run = 0
    while t - run >= 0 and not series[t - run].reported:
        run += 1
    return run


def evaluate(series: Sequence[WeekCount], cfg: DiseaseConfig, humanitarian: bool = False,
             risk_index: Optional[float] = None, threat_factors: Sequence[str] = (),
             weeks: Optional[Sequence[int]] = None) -> list[WeekResult]:
    """Evaluate every week of a gap-free, oldest-first series (see series.complete), or
    only the positions in `weeks` (e.g. [-1] for the latest week)."""
    suspected = [value(w, "suspected") for w in series]
    positions = range(len(series)) if weeks is None else [p % len(series) for p in weeks]
    doubling = early_rise.doubling(suspected, cfg.humanitarian_weeks, cfg.humanitarian_factor or 2.0)
    results = []
    for t in positions:
        w = series[t]
        act = _window(series, t, cfg.action.window_weeks)
        s_act = sum(value(x, "suspected") for x in act)
        c_act = sum(value(x, "confirmed") for x in act)
        d_act = sum(value(x, "deaths") for x in act)
        alw = _window(series, t, cfg.alert.window_weeks)
        s_al = sum(value(x, "suspected") for x in alw)
        c_al = sum(value(x, "confirmed") for x in alw)

        res = WeekResult(w.iso_year, w.iso_week, None)
        res.window = {"weeks": len(act), "suspected": s_act, "confirmed": c_act, "deaths": d_act,
                      "unreported_weeks": sum(not x.reported for x in act)}

        if cfg.action.met(s_act, c_act):
            res.level = "action"
            res.reasons.append(
                f"Action threshold: {s_act} suspected / {c_act} confirmed in {len(act)} weeks "
                f"(rule: >= {cfg.action.suspected} suspected or >= {cfg.action.confirmed} confirmed; {cfg.source})")
        if humanitarian and cfg.humanitarian_factor:
            if doubling[t]:
                res.level = res.level or "alert"
                res.reasons.append(
                    f"Humanitarian alert: {suspected[t]} cases is at least {cfg.humanitarian_factor:g}x "
                    f"the average of the previous {cfg.humanitarian_weeks} weeks (EPHI PHEM Guideline 2022, Table 4-6)")
        elif cfg.alert.met(s_al, c_al):
            res.level = res.level or "alert"
            res.reasons.append(f"Alert threshold: {s_al} suspected / {c_al} confirmed this week ({cfg.source})")

        # Evidence that orders results within a level.
        if cfg.approaching and res.level != "action" and cfg.approaching.met(s_act, c_act):
            res.flags["approaching_action"] = True
        if cfg.acceptable_cfr is not None and s_act >= cfg.cfr_min_cases:
            cfr = d_act / s_act
            res.flags["cfr"] = round(cfr, 4)
            res.flags["cfr_above_acceptable"] = cfr > cfg.acceptable_cfr
        run = _silent_run(series, t)
        res.flags["surveillance_silent"] = run >= SILENT_WEEKS
        res.flags["unreported_weeks_running"] = run
        if w.reports_expected:
            completeness = (w.reports_received or 0) / w.reports_expected
            res.flags["completeness"] = round(completeness, 3)
            res.flags["low_completeness"] = completeness < MIN_COMPLETENESS
        res.early_rise = early_rise.flags_at(suspected[:t + 1]) if t >= 1 else {"fired": []}
        if humanitarian and doubling[t]:
            res.early_rise["fired"] = res.early_rise.get("fired", []) + ["DOUBLING"]

        parts = {}
        if res.flags.get("approaching_action"):
            parts["approaching_action"] = PRIORITY_POINTS["approaching_action"]
        n_rise = len([f for f in res.early_rise.get("fired", []) if f != "DOUBLING"])
        if n_rise:
            parts["early_rise"] = PRIORITY_POINTS["early_rise_per_method"] * min(n_rise, 4)
        if res.flags.get("cfr_above_acceptable"):
            parts["cfr_above_acceptable"] = PRIORITY_POINTS["cfr_above_acceptable"]
        if risk_index is not None:
            parts["risk_index"] = round(PRIORITY_POINTS["risk_index_max"] * max(0.0, min(risk_index, 100.0)) / 100, 1)
        if threat_factors:
            parts["threat_factors"] = PRIORITY_POINTS["per_threat_factor"] * min(len(threat_factors), 2)
            res.flags["threat_factors"] = list(threat_factors)
        res.priority_parts = parts
        res.priority = min(100.0, float(sum(parts.values())))
        results.append(res)
    return results
