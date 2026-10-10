from pathlib import Path

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import create_engine, select
from sqlalchemy.exc import IntegrityError

from db.models import Base, IndicatorCount, OrgUnit, OrgUnitAdjacency, Signal

ROOT = Path(__file__).resolve().parent.parent


def add_hierarchy(db):
    region = OrgUnit(pcode="ET04", name="Oromia", level=1, level_name="region")
    zone = OrgUnit(pcode="ET0407", name="Jimma", level=2, level_name="zone", parent_pcode="ET04")
    woreda = OrgUnit(pcode="ET040712", name="Seka Chekorsa", level=3, level_name="woreda",
                     parent_pcode="ET0407", aliases=["Seka", "ሰቃ ጨቆርሳ"], population=250000)
    db.add_all([region, zone, woreda])
    db.flush()
    return region, zone, woreda


def test_hierarchy_parents_children_and_aliases(db):
    region, zone, woreda = add_hierarchy(db)
    db.commit()
    w = db.get(OrgUnit, "ET040712")
    assert w.parent.pcode == "ET0407"
    assert w.parent.parent.name == "Oromia"
    assert [c.pcode for c in db.get(OrgUnit, "ET04").children] == ["ET0407"]
    assert "ሰቃ ጨቆርሳ" in w.aliases  # Amharic survives the JSON round trip


def test_weekly_counts_are_unique_per_unit_disease_week_source(db):
    add_hierarchy(db)
    row = dict(pcode="ET040712", disease="measles", iso_year=2026, iso_week=40, source="dhis2")
    db.add(IndicatorCount(suspected=6, **row))
    db.commit()
    db.add(IndicatorCount(suspected=9, **row))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()
    db.add(IndicatorCount(suspected=9, **{**row, "source": "simulated"}))  # another source is fine
    db.commit()


def test_foreign_keys_are_enforced(db):
    db.add(IndicatorCount(pcode="ET999999", disease="measles", iso_year=2026, iso_week=1))
    with pytest.raises(IntegrityError):
        db.commit()


def test_signal_stores_extraction_and_analysis_json(db):
    add_hierarchy(db)
    db.add(Signal(
        id="0589235d-0000-0000-0000-000000000000", source_type="report",
        raw_text="Jimma zone, Seka Chekorsa woreda: 4 children with rash and fever",
        extracted={"location": "Jimma zone, Seka Chekorsa woreda", "cases": 4, "symptoms": ["rash", "fever"]},
        analysis={"consensus": {"final_risk_level": "HIGH"}},
        pcode="ET040712", geocode_confidence=0.95,
    ))
    db.commit()
    s = db.scalars(select(Signal)).one()
    assert s.status == "pending" and s.analysis_failed is False
    assert s.extracted["symptoms"] == ["rash", "fever"]
    assert s.analysis["consensus"]["final_risk_level"] == "HIGH"
    assert s.created_at is not None


def test_adjacency_pair(db):
    add_hierarchy(db)
    db.add(OrgUnit(pcode="ET040713", name="Kersa", level=3, parent_pcode="ET0407"))
    db.add(OrgUnitAdjacency(a_pcode="ET040712", b_pcode="ET040713", shared_border_km=31.5))
    db.commit()
    assert db.get(OrgUnitAdjacency, ("ET040712", "ET040713")).shared_border_km == 31.5


def test_migrations_build_exactly_the_models(tmp_path):
    """`alembic upgrade head` on an empty database must produce the tables in db/models.py."""
    url = f"sqlite:///{tmp_path / 'migrated.db'}"
    cfg = Config(str(ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(ROOT / "migrations"))
    cfg.set_main_option("sqlalchemy.url", url)
    command.upgrade(cfg, "head")
    engine = create_engine(url)
    with engine.connect() as conn:
        diff = compare_metadata(MigrationContext.configure(conn, opts={"compare_type": False}), Base.metadata)
    engine.dispose()
    assert diff == [], f"models and migrations differ; run `alembic revision --autogenerate`: {diff}"
