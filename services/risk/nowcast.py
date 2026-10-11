"""
Nowcasting late reports (METHODOLOGY 7.1, first version).

Recent months are incomplete: reports keep arriving for weeks (PHEM weekly reports reach
the national level 5-11 days late; batches arrive later still). Using raw recent counts
makes every month look quieter than it was, which biases incidence and the reporting rate.

Method (multiplicative "chain-ladder", the simplest standard nowcast): for each lag l
(0 = the current month, 1 = the month before), compare what had arrived by then with the
final count, over older months whose counts have settled, pooled across units:

    completeness_l = sum(count seen at lag l) / sum(final count)
    nowcast        = count seen at lag l / completeness_l

Bayesian nowcasts (Hoehle & an der Heiden 2014; NobBS, McGough 2020) add uncertainty and
changing delays; this version gives the point correction and is the base for them.
"""

from typing import Optional

import numpy as np

MAX_FACTOR = 5.0  # never inflate a recent count more than 5x


def completeness(settled: np.ndarray, seen_at_lag: np.ndarray, t: int, lag: int,
                 settle_months: int = 4, history: int = 24) -> Optional[float]:
    """Share of the final count that had arrived `lag` months after each month, from
    months that had settled by month t (no look-ahead). None without enough data."""
    hi = t - settle_months - lag
    lo = max(0, hi - history)
    if hi <= lo:
        return None
    final = settled[lo:hi]
    seen = seen_at_lag[lo:hi]
    ok = ~np.isnan(final) & ~np.isnan(seen)
    tot = final[ok].sum()
    if tot <= 0:
        return None
    return float(np.clip(seen[ok].sum() / tot, 1.0 / MAX_FACTOR, 1.0))


def apply(known: np.ndarray, settled: np.ndarray, seen_by_lag: dict, t: int) -> tuple[np.ndarray, dict]:
    """Correct the last months of `known` (cases for months 0..t as seen at t). Returns
    the corrected array and the completeness used per lag."""
    out = known.copy()
    used = {}
    for lag, seen in seen_by_lag.items():
        m = t - lag
        if m < 0:
            continue
        c = completeness(settled, seen, t, lag)
        used[lag] = c
        if c is not None:
            out[m] = known[m] / c
    return out, used
