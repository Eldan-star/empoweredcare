"""
Prospective space-time permutation scan statistic (Kulldorff et al. 2005, PLoS Med
2:e59), the method behind SaTScan's space-time permutation model.

It looks for places where recent cases are more concentrated than the overall pattern
would predict, using case counts only (no population or baseline needed), and can find
clusters that straddle unit boundaries, which per-unit thresholds miss.

- Cylinders: a circle of the k nearest units around each unit's centroid (k up to
  `max_units`, radius up to `max_km`), times a window of the last 1..`max_weeks` weeks
  (prospective: windows end in the current week).
- Expected cases in a cylinder, under no space-time interaction:
  mu = sum over its units and weeks of (cases in unit) x (cases in week) / (all cases).
- Score: Poisson generalised likelihood ratio,
  c log(c/mu) + (C-c) log((C-c)/(C-mu)) for c > mu.
- p-value: the observed best score ranked among the best scores of `reps` permutations
  that shuffle case weeks across cases (keeping each unit's and week's totals).

Clusters raise priority and are shown as evidence; they never set an EPHI level.
"""

from dataclasses import dataclass, field

import numpy as np

from services.risk.measles_risk import distance_matrix


@dataclass
class Cluster:
    centre: int
    units: list[int]
    weeks: int
    observed: int
    expected: float
    relative_risk: float
    llr: float
    p_value: float
    extra: dict = field(default_factory=dict)


def _circles(lat, lon, max_units: int, max_km: float, centres) -> list[tuple[int, np.ndarray]]:
    d = distance_matrix(lat, lon)
    out = []
    for i in centres:
        nb = np.argsort(d[i])[:max_units]
        out.append((int(i), nb[d[i, nb] <= max_km]))
    return out


def _candidates(counts: np.ndarray, circles, max_weeks: int) -> list[tuple]:
    """Best cylinder per circle: (llr, centre, member indices, weeks, observed, expected)."""
    W, U = counts.shape
    C = counts.sum()
    if C == 0:
        return []
    unit_tot = counts.sum(axis=0)
    week_tot = counts.sum(axis=1)
    best = {}
    for w in range(1, min(max_weeks, W) + 1):
        recent = counts[W - w:].sum(axis=0)
        exp_unit = unit_tot * (week_tot[W - w:].sum() / C)
        for i, nb in circles:
            c_cum = np.cumsum(recent[nb])
            mu_cum = np.cumsum(exp_unit[nb])
            ok = (c_cum > mu_cum) & (mu_cum > 0) & (c_cum < C)
            if not ok.any():
                continue
            c, mu = c_cum[ok], mu_cum[ok]
            llr = c * np.log(c / mu) + (C - c) * np.log((C - c) / (C - mu))
            j = int(np.argmax(llr))
            if llr[j] > best.get(i, (0.0,))[0]:
                k = np.flatnonzero(ok)[j] + 1
                best[i] = (float(llr[j]), i, nb[:k].tolist(), w, int(c[j]), float(mu[j]))
    return sorted(best.values(), reverse=True)


def scan_all(counts: np.ndarray, lat, lon, max_units: int = 15, max_km: float = 100.0, max_weeks: int = 4,
             reps: int = 199, seed: int = 0, max_clusters: int = 10) -> list[Cluster]:
    """The most likely cluster and non-overlapping secondary clusters, each with a p-value
    against the same permutation distribution of the maximum score (as SaTScan reports
    secondary clusters). Sorted by score."""
    counts = np.nan_to_num(np.asarray(counts, float)).astype(np.int64)
    centres = np.flatnonzero(counts[-max_weeks:].sum(axis=0) > 0)
    circles = _circles(np.asarray(lat), np.asarray(lon), max_units, max_km, centres)
    cands = _candidates(counts, circles, max_weeks)
    if not cands:
        return []
    rng = np.random.default_rng(seed)
    W, U = counts.shape
    units = np.repeat(np.tile(np.arange(U), W), counts.ravel())
    weeks = np.repeat(np.repeat(np.arange(W), U), counts.ravel())
    null_max = []
    for _ in range(reps):
        perm = np.zeros_like(counts)
        np.add.at(perm, (rng.permutation(weeks), units), 1)
        sim = _candidates(perm, circles, max_weeks)
        null_max.append(sim[0][0] if sim else 0.0)
    null_max = np.array(null_max)
    C = counts.sum()
    out, used = [], set()
    for llr, centre, members, w, c, mu in cands:
        if used.intersection(members):
            continue
        used.update(members)
        rr = (c / mu) / ((C - c) / (C - mu)) if C > c else float("inf")
        out.append(Cluster(centre, members, w, c, mu, float(rr), llr, float((np.sum(null_max >= llr) + 1) / (reps + 1))))
        if len(out) >= max_clusters:
            break
    return out


def scan(counts: np.ndarray, lat, lon, max_units: int = 15, max_km: float = 100.0, max_weeks: int = 4,
         reps: int = 199, seed: int = 0) -> Cluster | None:
    """The most likely current cluster in a (weeks x units) matrix of case counts, with its
    Monte Carlo p-value; None when there are no cases or no excess anywhere."""
    found = scan_all(counts, lat, lon, max_units, max_km, max_weeks, reps, seed, max_clusters=1)
    return found[0] if found else None
