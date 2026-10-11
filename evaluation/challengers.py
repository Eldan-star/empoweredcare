"""
Challenger rankings for the evaluation harness (METHODOLOGY section 5).

Every challenger predicts next-quarter measles burden per unit from data that would have
been observable at the time. Learned models are trained only on REPORTED cases (settled)
whose 3-month outcome window had closed, never on the simulator's truth, and are
re-fitted once a year on an expanding window. They are scored against the truth like the
risk index.

    persistence      reported incidence over the last 3 months
    ewma             exponentially weighted average of monthly reported incidence
    ar1_log          ARIMA(1,0,0) on log(1 + monthly incidence), one model per unit
    count_regression endemic-epidemic Poisson regression (hhh4-type): own recent cases,
                     neighbours' recent cases, coverage, population, season
    hybrid_regression the same regression plus the risk model's susceptible share and
                     importation pressure as covariates (mechanism-informed regression)
    boosted_trees    gradient-boosted trees (Poisson loss) on the same features plus the
                     risk model's outputs

Two references bound what is possible:
    oracle_mechanistic   our risk formula fed the simulator's TRUE recent infections and
                         TRUE susceptibles (the formula's ceiling)
    oracle_recent_truth  true infections over the last 2 months (perfect nowcast)
"""

import numpy as np

from services.risk import measles_risk as mr


def _incidence(cases, pop):
    return np.nan_to_num(cases) / pop[None, :] * 1e5


def _window_sum(x, m, months):
    return x[max(0, m - months + 1):m + 1].sum(axis=0)


def neighbour_matrix(lat, lon, c: float = 2.0, max_km: float = 300.0):
    d = np.maximum(mr.distance_matrix(lat, lon), 10.0)
    w = 1.0 / d ** c
    w[d > max_km] = 0.0
    np.fill_diagonal(w, 0.0)
    s = w.sum(axis=1, keepdims=True)
    return np.divide(w, s, out=np.zeros_like(w), where=s > 0)


def features(panel, res, m: int, W: np.ndarray, inc_known: np.ndarray) -> np.ndarray:
    """Feature matrix (units x features) as known at the end of month m."""
    pop = panel.population
    last1 = inc_known[m]
    last3 = _window_sum(inc_known, m, 3)
    last12 = _window_sum(inc_known, m, 12)
    nb = W @ last3
    month = panel.months[m][1]
    cols = [np.log1p(last1), np.log1p(last3), np.log1p(last12), np.log1p(nb),
            1 - panel.mcv1[m], panel.mcv2[m], np.log(pop),
            np.full(len(pop), np.sin(2 * np.pi * month / 12)), np.full(len(pop), np.cos(2 * np.pi * month / 12))]
    if res is not None:
        cols += [res.s[m] / pop, np.log(res.lam[m] + 1e-9)]
    return np.column_stack(cols)


def _fit_ar1(y: np.ndarray) -> tuple[float, float]:
    """Least-squares AR(1) with intercept on one series."""
    if len(y) < 6 or np.ptp(y) == 0:
        return float(y.mean()) if len(y) else 0.0, 0.0
    x, z = y[:-1], y[1:]
    phi, c = np.polyfit(x, z, 1)
    return float(c), float(np.clip(phi, -0.99, 0.99))


def rankings(panel, res, m0: int, monthly_truth: np.ndarray, true_s_share: np.ndarray,
             refit_every: int = 12, seed: int = 0) -> dict:
    """Scores (months x units) for every challenger and reference."""
    from sklearn.ensemble import HistGradientBoostingRegressor
    from sklearn.linear_model import PoissonRegressor

    T, U = panel.cases.shape
    pop = panel.population
    W = neighbour_matrix(panel.lat, panel.lon)
    # What was known at each month: settled history plus provisional recent months.
    settled_inc = _incidence(panel.cases, pop)
    prov_inc = _incidence(panel.cases_provisional if panel.cases_provisional is not None else panel.cases, pop)

    def known(m):
        k = settled_inc[:m + 1].copy()
        k[max(0, m - 1):] = prov_inc[max(0, m - 1):m + 1]
        return k

    out = {name: np.zeros((T, U)) for name in
           ("persistence", "ewma", "ar1_log", "count_regression", "hybrid_regression", "boosted_trees",
            "oracle_mechanistic", "oracle_recent_truth")}
    dist = mr.distance_matrix(panel.lat, panel.lon)
    true_inc = monthly_truth / pop[None, :] * 1e5
    # Observable training target: reported (settled) incidence over the next 3 months.
    target = np.full((T, U), np.nan)
    for m in range(T - 3):
        target[m] = settled_inc[m + 1:m + 4].sum(axis=0)

    glm = gbm = hyb = None
    ar_params = None
    for m in range(T):
        inc_k = known(m)
        out["persistence"][m] = _window_sum(inc_k, m, 3)
        alpha, e = 0.3, np.zeros(U)
        for t in range(max(0, m - 24), m + 1):
            e = alpha * inc_k[t] + (1 - alpha) * e
        out["ewma"][m] = e
        # References
        recent_true = monthly_truth[max(0, m - 1):m + 1].sum(axis=0)
        s_true = true_s_share[m] * pop
        out["oracle_mechanistic"][m] = mr.importation_pressure(s_true, pop, recent_true, dist)[0]
        out["oracle_recent_truth"][m] = recent_true / pop
        if m < m0:
            continue
        refit = (m - m0) % refit_every == 0
        # Training rows: months whose 3-month outcome window had closed and settled
        # (outcome months end by m-1; settling takes about 2 more months).
        train_months = [t for t in range(12, m - 5)]
        if refit and len(train_months) >= 12:
            X = np.vstack([features(panel, res, t, W, known(t)) for t in train_months])
            y = np.concatenate([target[t] for t in train_months])
            ok = ~np.isnan(y)
            glm = PoissonRegressor(alpha=1e-4, max_iter=300).fit(X[ok][:, :9], y[ok])
            hyb = PoissonRegressor(alpha=1e-4, max_iter=300).fit(X[ok], y[ok])
            gbm = HistGradientBoostingRegressor(loss="poisson", max_iter=200, learning_rate=0.05,
                                                random_state=seed).fit(X[ok], y[ok])
            ly = np.log1p(settled_inc[:m - 2])
            ar_params = [_fit_ar1(ly[:, u]) for u in range(U)]
        Xm = features(panel, res, m, W, inc_k)
        if glm is not None:
            out["count_regression"][m] = glm.predict(Xm[:, :9])
            out["hybrid_regression"][m] = hyb.predict(Xm)
            out["boosted_trees"][m] = gbm.predict(Xm)
        if ar_params is not None:
            ly_now = np.log1p(inc_k[m])
            # three steps ahead, summed
            pred = np.zeros(U)
            cur = ly_now
            for _ in range(3):
                cur = np.array([c + phi * v for (c, phi), v in zip(ar_params, cur)])
                pred += np.expm1(np.maximum(cur, 0))
            out["ar1_log"][m] = pred
    return out


def hubverse_rows(scores: dict, panel, m0: int, scenario: str) -> list[dict]:
    """Model output in the Hubverse column layout (one 'mean' value per model, unit and
    reference month; the value is each model's next-quarter burden score)."""
    rows = []
    for model, sc in scores.items():
        for m in range(m0, len(panel.months)):
            y, mo = panel.months[m]
            ref = f"{y}-{mo:02d}-01"
            for u, loc in enumerate(panel.pcodes):
                rows.append({"model_id": model, "scenario": scenario, "reference_date": ref, "horizon": 3,
                             "target": "measles burden score next quarter", "location": loc,
                             "output_type": "mean", "output_type_id": "", "value": float(sc[m, u])})
    return rows
