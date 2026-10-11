"""
Early-rise statistics on a weekly count series (METHODOLOGY section 4.8).

All functions take counts in time order (oldest first) and return one value per week;
weeks without enough history return None. They rank and explain alerts; they never set an
alert level (SYSTEM_SPEC section 8).

EARS C1, C2, C3 follow Hutwagner et al. 2003 as written out in Fricker, Hegler & Dunfee
2008 (Stat Med 27:3407):
    C1_t = (x_t - mean(x_{t-7..t-1})) / sd(x_{t-7..t-1})              flag if > 3
    C2_t = (x_t - mean(x_{t-9..t-3})) / sd(x_{t-9..t-3})              flag if > 3
    C3_t = sum_{i=t-2..t} max(0, C2_i - 1)                            flag if > 2
Routine data is weekly, so one period is one week. Standard deviations use n-1, and are
floored at `min_sd`: most woredas report zero most weeks, which gives sd = 0 and an
infinite statistic. The floor is an implementation choice, stated in METHODOLOGY.

EWMA follows Roberts 1959 (Technometrics 1:239), the exponentially weighted moving
average chart, on a rolling baseline:
    z_t = lam x_t + (1 - lam) z_{t-1};  flag if (z_t - mean) / (sd sqrt(lam / (2 - lam))) > L
with lam = 0.3 and L = 3, conventional values, and the same baseline/guard as CUSUM.

Poisson CUSUM follows Lucas 1985 (Technometrics 27:129):
    S_t = max(0, S_{t-1} + x_t - k),  k = (mu1 - mu0) / (ln mu1 - ln mu0)
with mu0 the expected count, mu1 = shift x mu0 the rise worth detecting, an alarm when
S_t > h, and S reset to 0 after an alarm.
"""

import math
from dataclasses import dataclass
from statistics import mean, stdev
from typing import Optional, Sequence

EARS_THRESHOLD = {"C1": 3.0, "C2": 3.0, "C3": 2.0}
EWMA_L = 3.0


def _z(x: float, base: Sequence[float], min_sd: float) -> float:
    return (x - mean(base)) / max(stdev(base), min_sd)


def ears_c1(counts: Sequence[float], min_sd: float = 0.5) -> list[Optional[float]]:
    return [None if t < 7 else _z(counts[t], counts[t - 7:t], min_sd) for t in range(len(counts))]


def ears_c2(counts: Sequence[float], min_sd: float = 0.5) -> list[Optional[float]]:
    return [None if t < 9 else _z(counts[t], counts[t - 9:t - 2], min_sd) for t in range(len(counts))]


def ears_c3(counts: Sequence[float], min_sd: float = 0.5) -> list[Optional[float]]:
    c2 = ears_c2(counts, min_sd)
    out: list[Optional[float]] = []
    for t in range(len(counts)):
        window = c2[t - 2:t + 1] if t >= 2 else []
        out.append(None if len(window) < 3 or None in window else sum(max(0.0, v - 1) for v in window))
    return out


@dataclass
class CusumResult:
    statistic: list[Optional[float]]
    alarm: list[bool]
    expected: list[Optional[float]]


def poisson_cusum(counts: Sequence[float], baseline_weeks: int = 8, guard_weeks: int = 2,
                  shift: float = 2.0, h: float = 4.0, min_mu0: float = 0.5) -> CusumResult:
    """Rolling-baseline Poisson CUSUM: mu0 for week t is the mean of the `baseline_weeks`
    weeks before a `guard_weeks` gap, so a rise in progress does not inflate its own
    baseline."""
    stat: list[Optional[float]] = []
    alarm: list[bool] = []
    expected: list[Optional[float]] = []
    s = 0.0
    for t, x in enumerate(counts):
        lo, hi = t - guard_weeks - baseline_weeks, t - guard_weeks
        if lo < 0:
            stat.append(None), alarm.append(False), expected.append(None)
            continue
        mu0 = max(mean(counts[lo:hi]), min_mu0)
        mu1 = shift * mu0
        k = (mu1 - mu0) / (math.log(mu1) - math.log(mu0))
        s = max(0.0, s + x - k)
        fired = s > h
        stat.append(s), alarm.append(fired), expected.append(mu0)
        if fired:
            s = 0.0
    return CusumResult(stat, alarm, expected)


def ewma(counts: Sequence[float], lam: float = 0.3, baseline_weeks: int = 8, guard_weeks: int = 2,
         min_sd: float = 0.5) -> list[Optional[float]]:
    """Standardised EWMA statistic per week (None until a baseline exists)."""
    out: list[Optional[float]] = []
    z = None
    for t, x in enumerate(counts):
        z = x if z is None else lam * x + (1 - lam) * z
        lo, hi = t - guard_weeks - baseline_weeks, t - guard_weeks
        if lo < 0:
            out.append(None)
            continue
        base = counts[lo:hi]
        sd = max(stdev(base), min_sd)
        out.append((z - mean(base)) / (sd * math.sqrt(lam / (2 - lam))))
    return out


def doubling(counts: Sequence[float], weeks: int = 3, factor: float = 2.0) -> list[Optional[bool]]:
    """EPHI humanitarian alert (PHEM Guideline 2022, Table 4-6): the current week is at
    least `factor` times the average of the previous `weeks` weeks. A week with no cases
    never fires, so a run of zeros cannot "double"."""
    out: list[Optional[bool]] = []
    for t, x in enumerate(counts):
        if t < weeks:
            out.append(None)
            continue
        out.append(x > 0 and x >= factor * mean(counts[t - weeks:t]))
    return out


def flags_at(counts: Sequence[float], t: int = -1, min_sd: float = 0.5) -> dict:
    """All early-rise results for one week (default: the latest), for evidence JSON."""
    t = t % len(counts)
    c1, c2, c3 = ears_c1(counts, min_sd)[t], ears_c2(counts, min_sd)[t], ears_c3(counts, min_sd)[t]
    cus = poisson_cusum(counts)
    ew = ewma(counts)[t]
    out = {
        "ears_c1": c1, "ears_c2": c2, "ears_c3": c3,
        "cusum": cus.statistic[t], "cusum_expected": cus.expected[t], "ewma": ew,
    }
    fired = [name for name, v in (("C1", c1), ("C2", c2), ("C3", c3))
             if v is not None and v > EARS_THRESHOLD[name]]
    if cus.alarm[t]:
        fired.append("CUSUM")
    if ew is not None and ew > EWMA_L:
        fired.append("EWMA")
    out["fired"] = fired
    return out
