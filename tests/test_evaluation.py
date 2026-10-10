"""Evaluation-harness tests that run without laser-measles (a hand-made 'truth')."""

from datetime import date

import numpy as np

from evaluation import harness as h
from services.detection import diseases
from services.detection.series import WeekCount
from services.detection.thresholds import evaluate
from simulation import ethiopia as eth


def fake_truth(weekly):
    weekly = np.asarray(weekly, dtype=np.int64)
    return eth.Truth(date(2020, 1, 6), weekly, np.zeros((weekly.shape[0] // 2, weekly.shape[1])), "test")


def test_reporting_layer_is_seeded_and_never_reports_more_than_true():
    truth = fake_truth(np.full((52, 500), 50))
    a, b = eth.report(truth, seed=3), eth.report(truth, seed=3)
    assert np.array_equal(a.suspected, b.suspected, equal_nan=True)
    assert np.nanmax(a.suspected) <= 50
    assert 0.05 < np.isnan(a.suspected).mean() < 0.15          # ~10% missing
    s, _ = a.as_of(10)
    assert s.shape == (11, 500)
    # In the same week: delay 0 (35%), not backfilled (85%), not missing (90%) = 26.8%,
    # so about 73% of this week's reports are not in yet
    assert 0.69 < np.isnan(s[10]).mean() < 0.77


def test_outbreak_onsets_need_a_quiet_period_first():
    pop = np.array([100_000, 100_000])
    w = np.zeros((40, 2))
    w[20:30, 0] = 10      # unit 0: quiet for 20 weeks, then 40/100k in 4 weeks -> one onset
    w[:, 1] = 10          # unit 1: never quiet -> no onset
    on = eth.outbreak_onsets(fake_truth(w), pop)
    assert [(t, u) for t, u, _ in on] == [(21, 0)]  # 4-week sum first reaches 20 at week 21
    assert on[0][2] == 90.0  # 9 weeks x 10 infections in the 12 weeks from onset, per 100k


def test_vectorised_levels_match_the_threshold_module():
    rng = np.random.default_rng(0)
    W, U = 30, 8
    truth = fake_truth(rng.poisson(15, (W, U)))
    rep = eth.report(truth, seed=1, p_missing=0.0, p_backfill=0.0, delay_probs=(1, 0, 0, 0, 0))
    cfg = diseases.get("measles")
    for t in (5, 17, 29):
        action, alert = h.levels_as_of(rep, t)
        s, c = rep.as_of(t)
        for u in range(U):
            series = [WeekCount(2020, i + 1, suspected=int(s[i, u]), confirmed=int(c[i, u])) for i in range(t + 1)]
            level = evaluate(series, cfg, weeks=[-1])[0].level
            assert (level == "action") == action[u]
            assert (level in ("action", "alert")) == (action[u] or alert[u])


def test_episodes_and_detection_scoring():
    flags = np.zeros((20, 1), bool)
    flags[[3, 4, 5, 15], 0] = True
    assert h.episodes(flags) == [(3, 0), (15, 0)]  # week 15 is > 4 weeks after the last flag
    transmitting = np.zeros((20, 1), bool)
    transmitting[3, 0] = True
    d = h.score_detection([(3, 0), (15, 0)], [(5, 0)], 0, units=1, weeks=52, transmitting=transmitting)
    assert d["sensitivity"] == 1.0 and d["median_delay_days"] == -14.0  # detected 2 weeks early
    assert d["ppv"] == 0.5  # week 15 had no true transmission


def test_precision_recall_at_k():
    p, r = h.precision_recall_at_k(np.array([0.9, 0.1, 0.8, 0.2]), np.array([True, False, False, True]), 2)
    assert p == 0.5 and r == 0.5
