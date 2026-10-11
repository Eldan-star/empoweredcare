import pytest
from sqlalchemy.orm import sessionmaker

from connectors.dhis2 import DHIS2Client
from db import guard
from db.models import IndicatorCount, OrgUnit


@pytest.fixture
def guarded(engine, monkeypatch):
    monkeypatch.delenv("ALLOW_TEST_DATA", raising=False)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    guard.install(factory)
    session = factory()
    session.add(OrgUnit(pcode="ET04", name="Oromia", level=1, level_name="region", source="OCHA COD-AB 2024"))
    session.commit()
    yield session
    session.rollback()
    session.close()


def count(source):
    return IndicatorCount(pcode="ET04", disease="measles", iso_year=2026, iso_week=40, suspected=3, source=source)


def test_labels_that_are_refused_and_allowed():
    for s in ["simulated", "Simulation run 3", "synthetic", "laser-measles", "test", "testing", "dhis2-demo",
              "fake", "dummy", "mock"]:
        assert guard.blocked(s), s
    for s in ["dhis2", "manual", "bulletin", "OCHA COD-PS 2023 under-5 (CSA)", "IOM DTM (HDX API extract)",
              "AHEAD 2024 latest", "WUENIC contest", None]:
        assert not guard.blocked(s), s


def test_real_database_refuses_simulated_rows(guarded):
    guarded.add(count("simulated"))
    with pytest.raises(guard.TestDataRefused, match="IndicatorCount"):
        guarded.commit()
    guarded.rollback()
    guarded.add(count("dhis2"))
    guarded.commit()


def test_changing_a_row_to_a_test_source_is_refused(guarded):
    row = count("manual")
    guarded.add(row)
    guarded.commit()
    row.source = "test"
    with pytest.raises(guard.TestDataRefused):
        guarded.commit()


def test_sandbox_can_switch_the_guard_off(guarded, monkeypatch):
    monkeypatch.setenv("ALLOW_TEST_DATA", "true")
    guarded.add(count("simulated"))
    guarded.commit()


def test_dhis2_demo_rows_are_labelled_as_demo():
    assert DHIS2Client(url="https://play.im.dhis2.org/stable-2-41-4", token="t").source == "dhis2-demo"
    assert DHIS2Client(url="https://dhis.moh.gov.et", token="t").source == "dhis2"
