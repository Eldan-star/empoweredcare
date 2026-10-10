"""Risk-model tests, with expected values worked out by hand."""

import numpy as np
import pytest

from services.risk import measles_risk as mr


def test_p_eff_hand_computed():
    # 0.8*0.84 + 0.5*(1-0.84)*0.90 = 0.672 + 0.072 = 0.744
    assert float(mr.p_eff(0.8, 0.5)) == pytest.approx(0.744)
    # MCV2 above MCV1 is capped at MCV1: 0.5*0.84 + 0.5*0.16*0.9 = 0.492
    assert float(mr.p_eff(0.5, 0.7)) == pytest.approx(0.492)
    assert float(mr.p_eff(0, 0)) == 0


def test_one_month_of_susceptible_accumulation():
    # 1000 + 100*(1-0.5) - 1000/180 - 10/0.5 = 1000 + 50 - 5.556 - 20 = 1024.444
    s = mr.step_susceptibles(1000, births=100, peff=0.5, cases=10, reporting_rate=0.5)
    assert float(s) == pytest.approx(1024.444, abs=1e-3)


def test_infections_and_campaigns_cannot_push_s_below_zero():
    assert float(mr.step_susceptibles(10, 0, 0, cases=100, reporting_rate=0.1)) == 0
    assert float(mr.step_susceptibles(100, 0, 0, 0, 1, sia_immunized=500)) == 0


def test_campaign_immunizes_the_target_share():
    # 1800 susceptible, 9-59 months is 51/180 of the band, 90% coverage, VE 0.9:
    # 1800 * 51/180 * 0.9 * 0.9 = 413.1
    assert float(mr.sia_immunized(1800, 0.9, 51 / 180)) == pytest.approx(413.1)


def test_reporting_rate_is_recovered_from_synthetic_data():
    rng = np.random.default_rng(1)
    months = 120
    births = np.full(months, 100.0)
    # Infections oscillate around births (epidemic cycles), so cumulative infections track
    # cumulative births; 20% of infections are reported.
    infections = births * (1 + 0.9 * np.sin(np.arange(months) * 2 * np.pi / 24))
    cases = rng.poisson(0.2 * infections)
    est = mr.reporting_rate(births, cases)
    assert est.rate == pytest.approx(0.2, rel=0.1)
    assert mr.reporting_rate(births[:6], cases[:6]) is None  # too short
    assert mr.reporting_rate(births, np.zeros(months)) is None


def test_pooling_shrinks_toward_the_region():
    zone = mr.ReportingRate(rate=0.4, slope=2.5, months=36, residuals=np.zeros(36))
    assert mr.pooled_rate(zone, 0.2) == pytest.approx(0.3)  # weight 36/(36+36)
    assert mr.pooled_rate(None, 0.2) == 0.2


def test_a_zone_next_to_an_outbreak_scores_higher_than_a_distant_twin():
    # A has the outbreak; B is 50 km away, C 300 km; B and C are otherwise identical.
    d = np.array([[0, 50, 300], [50, 0, 250], [300, 250, 0]], float)
    lam, local, imported = mr.importation_pressure(
        s=[100, 100, 100], population=[1000, 1000, 1000], incidence=[50, 0, 0], distance_km=d)
    assert lam[1] > lam[2] and imported[1] > imported[2]
    assert local[0] > 0 and local[1] == 0


def test_rank_index():
    assert list(mr.rank_index([1, 2, 3])) == [0, 50, 100]
    assert list(mr.rank_index([1, 1, 3])) == [25, 25, 100]


def test_with_no_infections_anywhere_zones_rank_by_susceptibility():
    d = mr.distance_matrix([7, 8, 9], [38, 38, 38])
    r = mr.score(s=[50, 100, 150], population=[1000] * 3, incidence=[0, 0, 0], distance_km=d,
                 births_per_month=[3, 3, 3], peff=[0.8, 0.8, 0.8])
    assert list(r.index) == [0, 50, 100]
    assert r.factors[2]["main_driver"].startswith("susceptible build-up")


def test_three_month_horizon_favours_low_coverage():
    # Equal pools today, but zone 1 vaccinates far less, so it pulls ahead in 3 months.
    d = mr.distance_matrix([7, 9], [38, 38])
    r = mr.score(s=[100, 100], population=[1000, 1000], incidence=[0, 0], distance_km=d,
                 births_per_month=[30, 30], peff=[0.9, 0.2])
    assert r.index[0] == r.index[1] == 50
    assert r.index_3m[1] > r.index_3m[0]


def test_distance_matrix_km():
    # One degree of latitude is about 111 km.
    assert mr.distance_matrix([7, 8], [38, 38])[0, 1] == pytest.approx(111.2, abs=0.5)


def test_panel_runs_without_look_ahead_and_flags_silence():
    from services.risk.panel import Panel, run
    T, Z = 30, 3
    cases = np.zeros((T, Z))
    cases[:, 2] = np.nan            # zone 2 never reports
    cases[25, 0] = 40               # outbreak in zone 0 in month 25
    p = Panel(pcodes=["A", "B", "C"], population=np.array([1e5, 1e5, 1e5]),
              lat=np.array([7.0, 7.3, 9.0]), lon=np.array([38.0, 38.0, 38.0]),
              months=[(2024 + (m // 12), m % 12 + 1) for m in range(T)],
              births=np.full((T, Z), 300.0), mcv1=np.full((T, Z), 0.6), mcv2=np.full((T, Z), 0.3),
              cases=cases)
    r = run(p)
    assert r.silent[:, 2].all() and not r.silent[:, 0].any()
    # Before month 25 nothing distinguishes A and B; afterwards B (33 km from the outbreak)
    # outranks C (222 km), and A ranks first.
    assert r.index[24, 0] == r.index[24, 1]
    assert r.index[25, 0] > r.index[25, 1] > r.index[25, 2]
    # Changing a later month cannot change an earlier result.
    cases2 = cases.copy(); cases2[28, 1] = 99
    p.cases = cases2
    assert np.array_equal(run(p).index[:28], r.index[:28])
