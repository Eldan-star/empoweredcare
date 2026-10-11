"""Surveillance queries, the coverage loader and the risk runner on a small database."""

import importlib.util
from datetime import date
from pathlib import Path

import numpy as np
import pytest

from db.models import Campaign, Immunization, IndicatorCount, OrgUnit, RiskScore
from services import surveillance
from services.risk.panel import run
from services.risk.runner import build_panel, store

ROOT = Path(__file__).resolve().parent.parent


def load_script(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def geo(db):
    db.add_all([
        OrgUnit(pcode="ET04", name="Oromia", level=1, population=2_000_000, lat=8.0, lon=38.0),
        OrgUnit(pcode="ET0407", name="Jimma", level=2, parent_pcode="ET04", population=1_000_000, lat=7.7, lon=36.8),
        OrgUnit(pcode="ET0410", name="North Shewa", level=2, parent_pcode="ET04", population=1_000_000, lat=9.7, lon=38.7),
        OrgUnit(pcode="ET040701", name="Seka Chekorsa", level=3, parent_pcode="ET0407", population=200_000, lat=7.6, lon=36.7),
        OrgUnit(pcode="ET040702", name="Kersa", level=3, parent_pcode="ET0407", population=150_000, lat=7.8, lon=36.9),
        OrgUnit(pcode="ET041001", name="Dera", level=3, parent_pcode="ET0410", population=120_000, lat=9.6, lon=38.6),
    ])
    db.flush()
    return db


def counts(db, pcode, start_week, values, year=2026, confirmed=None):
    for i, v in enumerate(values):
        db.add(IndicatorCount(pcode=pcode, disease="measles", iso_year=year, iso_week=start_week + i,
                              suspected=v, confirmed=(confirmed or [None] * len(values))[i], source="test"))
    db.flush()


def test_series_sums_inside_a_unit_and_keeps_missing_weeks_missing(geo):
    counts(geo, "ET040701", 30, [1, 0, None, 2])
    counts(geo, "ET040702", 30, [2, None, None, 0])
    s = surveillance.weekly_series(geo, "ET0407", weeks=6, end=(2026, 34))
    # Weeks 29-34: nothing stored for 29 and 34; week 32 nobody reported (both None).
    assert [w.suspected for w in s] == [None, 3, 0, None, 2, None]


def test_detect_orders_action_before_alert(geo):
    counts(geo, "ET040701", 37, [2, 1, 1, 1])     # 5 in 4 weeks -> action
    counts(geo, "ET040702", 40, [1])              # 1 this week -> alert
    counts(geo, "ET041001", 37, [0, 0, 0, 0])     # reported zeros -> no level
    res = surveillance.detect(geo, "measles", (2026, 40), level=3)
    assert [(r["pcode"], r["level"]) for r in res] == [("ET040701", "action"), ("ET040702", "alert"), ("ET041001", None)]
    assert res[0]["window"]["suspected"] == 5 and "PHEM Guideline 2022" in res[0]["reasons"][0]
    zones = surveillance.detect(geo, "measles", (2026, 40), level=2)
    assert zones[0]["pcode"] == "ET0407" and zones[0]["level"] == "action"  # woredas roll up


def test_coverage_loader_expands_national_rows_and_reads_percentages(geo, tmp_path):
    loader = load_script("load_immunization")
    f = tmp_path / "cov.csv"
    f.write_text("pcode,year,mcv1,mcv2,source\nET,2023,62,45,WUENIC 2023\nET0407,2023,0.55,,IHME\n", encoding="utf-8")
    rep = loader.load_coverage(geo, loader.read_csv(f), "file")
    geo.flush()
    assert rep["stored"] == 3 and not rep["skipped"]  # national -> 2 zones, plus one zone row
    rows = {(r.pcode, r.source): r for r in geo.query(Immunization)}
    assert rows[("ET0410", "WUENIC 2023 (national applied to zone)")].mcv1_coverage == 0.62
    assert rows[("ET0407", "IHME")].mcv1_coverage == 0.55 and rows[("ET0407", "IHME")].mcv2_coverage is None
    bad = tmp_path / "bad.csv"
    bad.write_text("pcode,year,mcv1\nET9999,2023,50\nET0407,2023,150\n", encoding="utf-8")
    rep = loader.load_coverage(geo, loader.read_csv(bad), "file")
    assert rep["stored"] == 0 and len(rep["skipped"]) == 2


def test_campaign_loader(geo, tmp_path):
    loader = load_script("load_immunization")
    f = tmp_path / "sia.csv"
    f.write_text("pcode,start_date,age_min_months,age_max_months,coverage\nET0407,2024-03-01,9,59,90\n", encoding="utf-8")
    rep = loader.load_campaigns(geo, loader.read_csv(f), "EPHI report")
    geo.flush()
    c = geo.query(Campaign).one()
    assert rep["stored"] == 1 and c.coverage == 0.9 and c.start_date == date(2024, 3, 1)


def test_risk_runner_builds_scores_and_stores_them(geo):
    geo.add_all([Immunization(pcode="ET0407", year=2024, month=0, mcv1_coverage=0.4, mcv2_coverage=0.2, source="t"),
                 Immunization(pcode="ET0410", year=2024, month=0, mcv1_coverage=0.9, mcv2_coverage=0.7, source="t")])
    counts(geo, "ET040701", 10, [3, 4, 5], year=2026)
    built = build_panel(geo, end=(2026, 6), years=3)
    p = built.panel
    assert p.pcodes == ["ET0407", "ET0410"] and built.births_estimated
    # ISO weeks 10-12 of 2026 (Thursdays 5, 12, 19 March) fall in March, 3 months before June.
    assert p.cases[-4, 0] == 12 and int((~np.isnan(p.cases)).sum()) == 1
    res = run(p)
    assert res.index[-1, 0] > res.index[-1, 1]  # low coverage + recent cases outranks high coverage
    assert store(geo, p, res, last_months=2) == 4
    geo.flush()
    rows = surveillance.latest_risk(geo)
    assert [r["pcode"] for r in rows] == ["ET0407", "ET0410"] and rows[0]["month"] == 6
    assert "main_driver" in rows[0]["factors"]


def test_risk_runner_explains_missing_inputs(db):
    assert build_panel(db, end=(2026, 6)).panel is None


def test_births_loader_uses_woreda_rates_with_fallbacks(geo, tmp_path):
    import pandas as pd
    from db.models import Demographics
    loader = load_script("load_births")
    book = tmp_path / "eth_admpop_2023.xlsx"
    with pd.ExcelWriter(book) as w:
        pd.DataFrame({"admin3Name_en": ["Seka", "Old woreda", "Reused code"],
                      "admin3Pcode": ["ET040701", "ET049999", "ET041001"],
                      "admin1Name_en": ["Oromia", "Oromia", "Amhara"],
                      "Total": [100_000, 50_000, 10_000], "T_00_04": [15_000, 9_000, 4_000]}).to_excel(
            w, sheet_name="ETH_admpop_adm3_2023", index=False)
    rates = loader.read_rates(book, adjustment=1.0)
    assert rates["woreda"]["ET040701"][0] == pytest.approx(30.0)   # 15,000 / 5 / 100,000 x 1,000
    rows = {r.pcode: r for r in loader.assign({u.pcode: u for u in geo.query(OrgUnit)}, rates, 2026, successors={})}
    assert rows["ET040701"].method == "woreda under-5" and rows["ET040701"].births == pytest.approx(6000)
    assert rows["ET040702"].method == "zone average" and rows["ET040702"].birth_rate == pytest.approx(30.0)
    # ET041001 exists, but in 2023 that code was an Amhara woreda: not used; region average instead.
    assert rows["ET041001"].method == "region average"
    assert rows["ET0407"].method == "sum of woredas" and rows["ET0407"].births == pytest.approx(6000 + 4500)
    geo.add_all(rows.values())
    geo.add_all([Immunization(pcode="ET0407", year=2024, month=0, mcv1_coverage=0.5, source="t"),
                 Immunization(pcode="ET0410", year=2024, month=0, mcv1_coverage=0.5, source="t")])
    geo.flush()
    built = build_panel(geo, end=(2026, 6), years=2)
    assert not built.births_estimated
    assert built.panel.births[0, 0] == pytest.approx(10500 / 12)


def test_counts_keep_snapshots_and_feed_the_nowcast(geo):
    from datetime import datetime, timezone
    from db.models import CountSnapshot
    geo.add(Immunization(pcode="ET0407", year=2026, month=0, mcv1_coverage=0.5, source="t"))
    # ISO week 10 of 2026 is in March. 2 cases known on 9 March, revised to 6 on 20 April.
    row = {"pcode": "ET040701", "disease": "measles", "iso_year": 2026, "iso_week": 10, "suspected": 2}
    surveillance.record_counts(geo, [row], datetime(2026, 3, 9, tzinfo=timezone.utc))
    surveillance.record_counts(geo, [{**row, "suspected": 6}], datetime(2026, 4, 20, tzinfo=timezone.utc))
    geo.flush()
    assert geo.query(IndicatorCount).one().suspected == 6 and geo.query(CountSnapshot).count() == 2
    p = build_panel(geo, end=(2026, 6), years=1).panel
    march = p.months.index((2026, 3))
    assert p.cases[march, 0] == 6                       # final value
    assert p.cases_provisional[march, 0] == 2           # as seen at the end of March
    assert p.cases_provisional_lag1[march, 0] == 6      # as seen at the end of April
