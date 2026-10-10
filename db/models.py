"""
Database tables for Phase 1 (docs/SYSTEM_SPEC.md section 3).

Geography is keyed by OCHA P-codes (e.g. ET04 = Oromia, ET0401 = a zone, ET040101 = a
woreda). Weekly counts follow DHIS2/PHEM ISO weeks. JSON columns become JSONB on
PostgreSQL and plain JSON elsewhere (SQLite in tests).
"""

from datetime import date, datetime
from typing import Any, Optional

from sqlalchemy import (
    JSON, Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text,
    UniqueConstraint, func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

JSONType = JSON().with_variant(JSONB(), "postgresql")


class Base(DeclarativeBase):
    type_annotation_map = {dict[str, Any]: JSONType, list[Any]: JSONType}


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


# --- Geography -------------------------------------------------------------------

class OrgUnit(Base):
    """An administrative unit or facility. Levels are open-ended: 1 region, 2 zone,
    3 woreda, 4 kebele or facility, and deeper if a source provides it."""

    __tablename__ = "org_units"

    pcode: Mapped[str] = mapped_column(String(32), primary_key=True)
    name: Mapped[str] = mapped_column(String(200), index=True)
    level: Mapped[int] = mapped_column(Integer, index=True)
    level_name: Mapped[Optional[str]] = mapped_column(String(32))  # "region", "zone", "woreda", ...
    parent_pcode: Mapped[Optional[str]] = mapped_column(ForeignKey("org_units.pcode"), index=True)
    # Other spellings and names (Amharic, older names) used by the geocoder.
    aliases: Mapped[list[Any]] = mapped_column(default=list)
    population: Mapped[Optional[int]] = mapped_column(Integer)
    lat: Mapped[Optional[float]] = mapped_column(Float)
    lon: Mapped[Optional[float]] = mapped_column(Float)
    dhis2_uid: Mapped[Optional[str]] = mapped_column(String(11), unique=True)
    valid_from: Mapped[Optional[date]] = mapped_column(Date)
    valid_to: Mapped[Optional[date]] = mapped_column(Date)  # NULL = still current
    source: Mapped[Optional[str]] = mapped_column(String(100))  # e.g. "OCHA COD-AB 2024"

    parent: Mapped[Optional["OrgUnit"]] = relationship(remote_side=[pcode], back_populates="children")
    children: Mapped[list["OrgUnit"]] = relationship(back_populates="parent")


class OrgUnitAdjacency(Base):
    """Pairs of units that share a border. Stored once per pair with a_pcode < b_pcode."""

    __tablename__ = "org_unit_adjacency"

    a_pcode: Mapped[str] = mapped_column(ForeignKey("org_units.pcode"), primary_key=True)
    b_pcode: Mapped[str] = mapped_column(ForeignKey("org_units.pcode"), primary_key=True)
    shared_border_km: Mapped[Optional[float]] = mapped_column(Float)
    centroid_distance_km: Mapped[Optional[float]] = mapped_column(Float)


class BoundaryCrosswalk(Base):
    """Maps a retired unit to its successors (e.g. the SNNPR split), with the share of
    population each successor took, so old data can be carried onto new boundaries."""

    __tablename__ = "boundary_crosswalk"
    __table_args__ = (UniqueConstraint("old_pcode", "new_pcode"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    old_pcode: Mapped[str] = mapped_column(String(32), index=True)
    new_pcode: Mapped[str] = mapped_column(String(32), index=True)
    population_share: Mapped[Optional[float]] = mapped_column(Float)
    effective_date: Mapped[Optional[date]] = mapped_column(Date)
    note: Mapped[Optional[str]] = mapped_column(Text)


# --- Routine data ----------------------------------------------------------------

class IndicatorCount(Base):
    """Weekly counts for one disease in one unit (PHEM weekly reporting)."""

    __tablename__ = "indicator_counts"
    __table_args__ = (UniqueConstraint("pcode", "disease", "iso_year", "iso_week", "source"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    pcode: Mapped[str] = mapped_column(ForeignKey("org_units.pcode"), index=True)
    disease: Mapped[str] = mapped_column(String(50), index=True)
    iso_year: Mapped[int] = mapped_column(Integer)
    iso_week: Mapped[int] = mapped_column(Integer)
    suspected: Mapped[Optional[int]] = mapped_column(Integer)
    confirmed: Mapped[Optional[int]] = mapped_column(Integer)  # e.g. measles IgM positive
    deaths: Mapped[Optional[int]] = mapped_column(Integer)
    reports_expected: Mapped[Optional[int]] = mapped_column(Integer)
    reports_received: Mapped[Optional[int]] = mapped_column(Integer)
    source: Mapped[str] = mapped_column(String(50), default="dhis2")  # dhis2 | simulated | manual
    reported_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))


class Immunization(Base):
    """Monthly measles vaccination for one unit."""

    __tablename__ = "immunization"
    __table_args__ = (UniqueConstraint("pcode", "year", "month", "source"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    pcode: Mapped[str] = mapped_column(ForeignKey("org_units.pcode"), index=True)
    year: Mapped[int] = mapped_column(Integer)
    month: Mapped[int] = mapped_column(Integer)
    mcv1_doses: Mapped[Optional[int]] = mapped_column(Integer)
    mcv2_doses: Mapped[Optional[int]] = mapped_column(Integer)
    births: Mapped[Optional[int]] = mapped_column(Integer)
    mcv1_coverage: Mapped[Optional[float]] = mapped_column(Float)  # 0–1
    mcv2_coverage: Mapped[Optional[float]] = mapped_column(Float)  # 0–1
    source: Mapped[str] = mapped_column(String(50), default="dhis2")


class Campaign(Base):
    """A supplementary immunization activity (SIA) or outbreak-response campaign."""

    __tablename__ = "campaigns"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    pcode: Mapped[str] = mapped_column(ForeignKey("org_units.pcode"), index=True)
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[Optional[date]] = mapped_column(Date)
    vaccine: Mapped[str] = mapped_column(String(50), default="measles")
    age_min_months: Mapped[Optional[int]] = mapped_column(Integer)
    age_max_months: Mapped[Optional[int]] = mapped_column(Integer)
    coverage: Mapped[Optional[float]] = mapped_column(Float)  # 0–1, administrative or survey
    source: Mapped[Optional[str]] = mapped_column(String(100))


# --- Event-based surveillance, alerts, models ------------------------------------

class Signal(TimestampMixin, Base):
    """One reported event: a submitted report, an upload, a field trigger or a bulletin
    item. The id is the session_id the frontend already uses."""

    __tablename__ = "signals"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    source_type: Mapped[str] = mapped_column(String(20), index=True)  # report | upload | intake | bulletin | reliefweb | legacy
    raw_text: Mapped[str] = mapped_column(Text, default="")
    location_text: Mapped[Optional[str]] = mapped_column(String(300))
    disease: Mapped[Optional[str]] = mapped_column(String(100))
    cases: Mapped[Optional[int]] = mapped_column(Integer)
    classification: Mapped[Optional[str]] = mapped_column(String(20))  # Suspected | Probable | Confirmed
    # Extraction output as returned to the frontend (location, symptoms, cases, date, ...).
    extracted: Mapped[dict[str, Any]] = mapped_column(default=dict)
    # Language-model output: validation, risk opinions, consensus, alert, context research.
    analysis: Mapped[dict[str, Any]] = mapped_column(default=dict)
    analysis_failed: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    # Geocoding (M2 geocoder): resolved unit, confidence, and whether a human must choose.
    pcode: Mapped[Optional[str]] = mapped_column(ForeignKey("org_units.pcode"), index=True)
    geocode_confidence: Mapped[Optional[float]] = mapped_column(Float)
    geocode_ambiguous: Mapped[bool] = mapped_column(Boolean, default=False)
    geocode_candidates: Mapped[list[Any]] = mapped_column(default=list)
    cluster_id: Mapped[Optional[str]] = mapped_column(String(36), index=True)
    # Review: pending | approved | rejected | duplicate | dismissed
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    reviewed_by: Mapped[Optional[str]] = mapped_column(String(200))
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    submitted_by: Mapped[Optional[str]] = mapped_column(String(200))


class Alert(TimestampMixin, Base):
    """A tiered alert for one unit, disease and week (fusion ladder, M5)."""

    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    pcode: Mapped[str] = mapped_column(ForeignKey("org_units.pcode"), index=True)
    disease: Mapped[str] = mapped_column(String(50))
    iso_year: Mapped[int] = mapped_column(Integer)
    iso_week: Mapped[int] = mapped_column(Integer)
    tier: Mapped[str] = mapped_column(String(10), index=True)  # RED | ORANGE | YELLOW
    evidence: Mapped[dict[str, Any]] = mapped_column(default=dict)
    status: Mapped[str] = mapped_column(String(20), default="open")  # open | verified | dismissed | closed
    verdict: Mapped[Optional[str]] = mapped_column(String(20))
    reviewed_by: Mapped[Optional[str]] = mapped_column(String(200))


class RiskScore(Base):
    """Monthly measles ignition-risk inputs and index for one unit (M3)."""

    __tablename__ = "risk_scores"
    __table_args__ = (UniqueConstraint("pcode", "year", "month", "model_version"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    pcode: Mapped[str] = mapped_column(ForeignKey("org_units.pcode"), index=True)
    year: Mapped[int] = mapped_column(Integer)
    month: Mapped[int] = mapped_column(Integer)
    susceptibles: Mapped[Optional[float]] = mapped_column(Float)
    reporting_rate: Mapped[Optional[float]] = mapped_column(Float)  # rho
    p_eff: Mapped[Optional[float]] = mapped_column(Float)
    importation_pressure: Mapped[Optional[float]] = mapped_column(Float)  # lambda
    risk_index: Mapped[Optional[float]] = mapped_column(Float)
    factors: Mapped[dict[str, Any]] = mapped_column(default=dict)  # top contributors, for explanations
    model_version: Mapped[str] = mapped_column(String(20), default="v1")


class Evaluation(Base):
    """One run of the evaluation harness (M3)."""

    __tablename__ = "evaluations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    name: Mapped[str] = mapped_column(String(100))
    params: Mapped[dict[str, Any]] = mapped_column(default=dict)
    metrics: Mapped[dict[str, Any]] = mapped_column(default=dict)
    report_path: Mapped[Optional[str]] = mapped_column(String(300))
