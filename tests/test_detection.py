"""Detection tests. Expected values are worked out by hand from the published
definitions (see the comments), not copied from the code's output."""

import math

import pytest

from services.detection import diseases, early_rise
from services.detection.series import WeekCount, complete, shift
from services.detection.thresholds import evaluate

MEASLES = diseases.get("measles")


def weeks(suspected, confirmed=None, deaths=None, start=(2026, 1)):
    out, cur = [], start
    for i, s in enumerate(suspected):
        out.append(WeekCount(*cur, suspected=s,
                             confirmed=None if confirmed is None else confirmed[i],
                             deaths=None if deaths is None else deaths[i]))
        cur = shift(*cur, 1)
    return out


# --- EARS ------------------------------------------------------------------------

def test_ears_c1_hand_computed():
    # Baseline 0,1,0,2,1,0,1: mean 5/7; sample variance (7 - 7*(5/7)^2)/6 = 4/7.
    # C1 = (6 - 5/7) / sqrt(4/7) = (37/7) / 0.755929 = 6.99234
    c1 = early_rise.ears_c1([0, 1, 0, 2, 1, 0, 1, 6])
    assert c1[:7] == [None] * 7
    assert c1[7] == pytest.approx((37 / 7) / math.sqrt(4 / 7))
    assert c1[7] == pytest.approx(6.99234, abs=1e-4)


def test_ears_c2_uses_a_two_week_guard_and_the_sd_floor():
    # Baseline for t=9 is weeks 0..6 (all 1, sd 0 -> floor 0.5); the 9s in weeks 7-8 are
    # inside the guard band and ignored. C2 = (4 - 1) / 0.5 = 6.
    c2 = early_rise.ears_c2([1, 1, 1, 1, 1, 1, 1, 9, 9, 4])
    assert c2[9] == pytest.approx(6.0)


def test_ears_c3_accumulates_c2_above_one():
    # C2 at t=9,10,11 = (2-1)/.5, (3-1)/.5, (4-1)/.5 = 2, 4, 6 -> C3 = 1 + 3 + 5 = 9
    c3 = early_rise.ears_c3([1] * 9 + [2, 3, 4])
    assert c3[10] is None and c3[11] == pytest.approx(9.0)


def test_poisson_cusum_hand_computed():
    # mu0 = 1, mu1 = 2, k = 1/ln 2 = 1.442695. Week 10: S = 4 - k = 2.557 (no alarm,
    # h = 4). Week 11: S = 5.115 > 4 -> alarm, then reset.
    r = early_rise.poisson_cusum([1] * 10 + [4, 4])
    k = 1 / math.log(2)
    assert r.statistic[9] is None
    assert r.statistic[10] == pytest.approx(4 - k) and not r.alarm[10]
    assert r.statistic[11] == pytest.approx(2 * (4 - k)) and r.alarm[11]
    assert r.expected[11] == 1


def test_humanitarian_doubling_rule():
    assert early_rise.doubling([0, 0, 0, 1])[3] is True      # first case after zeros
    assert early_rise.doubling([2, 2, 2, 3])[3] is False     # 3 < 2 x 2
    assert early_rise.doubling([2, 2, 2, 4])[3] is True
    assert early_rise.doubling([0, 0, 0, 0])[3] is False     # zeros never "double"


# --- Weeks -------------------------------------------------------------------------

def test_iso_weeks_cross_the_year_and_gaps_become_unreported():
    assert shift(2026, 52, 1) == (2026, 53)  # 2026 has 53 ISO weeks
    assert shift(2026, 53, 1) == (2027, 1)
    s = complete([WeekCount(2026, 52, 1), WeekCount(2027, 2, 0)])
    assert [w.key for w in s] == [(2026, 52), (2026, 53), (2027, 1), (2027, 2)]
    assert [w.reported for w in s] == [True, False, False, True]


# --- EPHI thresholds (PHEM Guideline 2022, Table 4-5) ---------------------------------

def test_single_suspected_case_is_an_alert():
    r = evaluate(weeks([0, 0, 1]), MEASLES)
    assert [x.level for x in r] == [None, None, "alert"]


def test_five_suspected_in_four_weeks_is_action():
    r = evaluate(weeks([0, 0, 1, 2, 1, 1]), MEASLES)
    # Week 3: window 0+0+1+2 = 3 -> alert, approaching. Week 5: 1+2+1+1 = 5 -> action.
    assert r[3].level == "alert" and r[3].flags["approaching_action"]
    assert r[5].level == "action" and r[5].window["suspected"] == 5
    assert "approaching_action" not in r[5].flags


def test_cases_older_than_four_weeks_drop_out_of_the_window():
    r = evaluate(weeks([4, 0, 0, 0, 1]), MEASLES)
    assert r[3].level is None and r[4].level == "alert"  # 0+0+0+1 = 1, the 4 has expired


def test_three_confirmed_is_action_even_without_five_suspected():
    r = evaluate(weeks([1, 1, 1], confirmed=[1, 1, 1]), MEASLES)
    assert r[2].level == "action" and r[2].window["confirmed"] == 3


def test_humanitarian_setting_uses_the_doubling_rule():
    steady = evaluate(weeks([1, 1, 1, 1]), MEASLES, humanitarian=True)
    assert steady[3].level is None  # endemic baseline, no doubling
    rising = evaluate(weeks([0, 1, 0, 2]), MEASLES, humanitarian=True)  # 2 >= 2 x 1/3
    assert rising[3].level == "alert" and "DOUBLING" in rising[3].early_rise["fired"]
    # The action threshold still applies in humanitarian settings.
    assert evaluate(weeks([0, 2, 2, 2]), MEASLES, humanitarian=True)[3].level == "action"


def test_case_fatality_above_three_percent_is_flagged():
    r = evaluate(weeks([5, 5, 5, 5], deaths=[0, 0, 0, 1]), MEASLES)
    assert r[3].flags["cfr"] == 0.05 and r[3].flags["cfr_above_acceptable"]
    small = evaluate(weeks([1, 1, 1, 1], deaths=[0, 0, 0, 1]), MEASLES)
    assert "cfr" not in small[3].flags  # fewer than 10 cases: too few to judge


def test_unreported_weeks_mean_silence_not_zero_cases():
    reported_zero = evaluate(weeks([0, 0, 0]), MEASLES)
    assert not reported_zero[2].flags["surveillance_silent"]
    silent = evaluate(weeks([0, None, None]), MEASLES)
    assert silent[2].flags["surveillance_silent"] and silent[2].level is None
    assert silent[2].window["unreported_weeks"] == 2


def test_completeness_below_eighty_percent_is_flagged():
    s = weeks([0])
    s[0].reports_expected, s[0].reports_received = 10, 7
    r = evaluate(s, MEASLES)[0]
    assert r.flags["completeness"] == 0.7 and r.flags["low_completeness"]


def test_priority_orders_within_a_level_but_never_changes_it():
    base = evaluate(weeks([0, 0, 1]), MEASLES, weeks=[-1])[0]
    boosted = evaluate(weeks([0, 0, 1]), MEASLES, risk_index=100, threat_factors=["conflict"],
                       weeks=[-1])[0]
    assert base.level == boosted.level == "alert"
    assert boosted.priority == base.priority + 30 + 5
    nothing = evaluate(weeks([0, 0, 0]), MEASLES, risk_index=100, weeks=[-1])[0]
    assert nothing.level is None  # a high index alone never creates an alert


def test_other_diseases_single_case_rules():
    cholera = diseases.get("Cholera")
    r = evaluate(weeks([1], confirmed=[0]), cholera)[0]
    assert r.level == "alert"
    assert evaluate(weeks([1], confirmed=[1]), cholera)[0].level == "action"
    with pytest.raises(KeyError):
        diseases.get("malaria")  # baseline rules not implemented yet
