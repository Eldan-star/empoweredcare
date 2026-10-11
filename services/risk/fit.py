"""
Fit the risk model's scoring settings on past data (METHODOLOGY 5.2: placeholders
"to be fitted on Ethiopian history").

Settings: the distance exponent c, the background introduction rate, and the weight given
to case-based versus coverage-based susceptibles. They are chosen by grid search to
maximise how often the top 10% of units by the index contain the top 10% by REPORTED
incidence over the following 3 months, using only months whose outcome had settled
before `fit_until`. Reported, not true, incidence: the truth is never observable.
"""

import itertools

import numpy as np

from services.risk.panel import Panel, PanelResult, rescore

GRID = {"c": (1.0, 2.0, 3.0), "background": (0.01, 0.1, 1.0), "s_anchor_weight": (0.0, 0.5, 1.0)}


def _precision(scores: np.ndarray, target: np.ndarray, k: int) -> float:
    top = np.argsort(-scores, kind="mergesort")[:k]
    return float(target[top].mean())


def fit(panel: Panel, res: PanelResult, fit_from: int, fit_until: int, k_share: float = 0.1,
        grid: dict = GRID) -> dict:
    """Best settings and their in-sample precision; {} if there is too little data."""
    T, U = panel.cases.shape
    cases = np.nan_to_num(panel.cases)
    inc = cases / panel.population[None, :]
    months = [m for m in range(max(fit_from, 0), min(fit_until, T) - 3)]
    if len(months) < 6:
        return {}
    k = max(1, int(round(k_share * U)))
    targets = {}
    for m in months:
        nxt = inc[m + 1:m + 4].sum(axis=0)
        if nxt.sum() > 0:
            targets[m] = nxt >= np.quantile(nxt, 1 - k_share)
    if not targets:
        return {}
    best = {"precision": -1.0}
    for c, bg, w in itertools.product(grid["c"], grid["background"], grid["s_anchor_weight"]):
        lam = rescore(panel, res, s_anchor_weight=w, c=c, background=bg)
        p = float(np.mean([_precision(lam[m], targets[m], k) for m in targets]))
        if p > best["precision"]:
            best = {"precision": p, "c": c, "background": bg, "s_anchor_weight": w}
    best["months_used"] = len(targets)
    return best
