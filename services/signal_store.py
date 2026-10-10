"""
Outbreak reports ("signals") in PostgreSQL.

Records go in and out in the same dictionary shape the old outbreak_data.json used
(session_id, extracted_data, validation, risk_analysis, consensus, alert, status,
created_at, timestamp, raw_report), so the API and frontend are unchanged.
"""

import json
import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from db.models import Signal

logger = logging.getLogger(__name__)

# Reports for the same place and disease within this window share a cluster_id.
CLUSTER_WINDOW = timedelta(days=14)
# Text the pipeline leaves in a record when the AI step failed (old and current wording).
FAILURE_MARKERS = (
    "Analysis failed",
    "generation failed",
    "Gemini failed",
    "scan failed",
    "cognitive engine",
    "is no longer available",
    "is not found for API version",
)


def _plain(value: Any) -> Any:
    """Pydantic models and dates -> JSON-safe dicts and strings."""
    if value is None:
        return None
    if hasattr(value, "model_dump"):
        value = value.model_dump(mode="json")
    return json.loads(json.dumps(value, default=str))


def analysis_failed(analysis: dict, extracted: dict) -> bool:
    text = json.dumps([analysis, extracted], default=str)
    return any(m in text for m in FAILURE_MARKERS)


def to_record(s: Signal) -> dict:
    a = s.analysis or {}
    return {
        "session_id": s.id,
        "extracted_data": s.extracted or {},
        "validation": a.get("validation"),
        "risk_analysis": a.get("risk_analysis") or {},
        "consensus": a.get("consensus"),
        "context_research": a.get("context_research"),
        "alert": a.get("alert") or {},
        "status": s.status,
        "created_at": s.created_at.isoformat() if s.created_at else None,
        "timestamp": (s.updated_at or s.created_at).isoformat() if (s.updated_at or s.created_at) else None,
        "raw_report": s.raw_text,
        "source_type": s.source_type,
        "cluster_id": s.cluster_id,
        "pcode": s.pcode,
        "analysis_failed": s.analysis_failed,
    }


class SignalStore:
    def __init__(self, session_factory: Callable[[], Session]):
        self._session_factory = session_factory

    def add(
        self,
        extracted: Any,
        *,
        session_id: Optional[str] = None,
        raw_text: str = "",
        source_type: str = "report",
        validation: Any = None,
        risk_analysis: Any = None,
        consensus: Any = None,
        context_research: Any = None,
        alert: Any = None,
        submitted_by: Optional[str] = None,
        created_at: Optional[datetime] = None,
        status: str = "pending",
    ) -> dict:
        extracted = _plain(extracted) or {}
        analysis = {
            "validation": _plain(validation),
            "risk_analysis": _plain(risk_analysis) or {},
            "consensus": _plain(consensus),
            "context_research": _plain(context_research),
            "alert": _plain(alert) or {},
        }
        disease = (analysis["risk_analysis"] or {}).get("possible_disease")
        location = extracted.get("location")
        cases = extracted.get("cases")
        with self._session_factory() as db:
            signal = Signal(
                id=session_id or str(uuid.uuid4()),
                source_type=source_type,
                raw_text=raw_text or "",
                location_text=location,
                disease=disease,
                cases=cases if isinstance(cases, int) else None,
                classification=extracted.get("classification"),
                extracted=extracted,
                analysis=analysis,
                analysis_failed=analysis_failed(analysis, extracted),
                status=status,
                submitted_by=submitted_by,
                cluster_id=self._cluster_for(db, location, disease, created_at),
            )
            if created_at is not None:
                signal.created_at = signal.updated_at = created_at
            db.add(signal)
            db.commit()
            db.refresh(signal)
            return to_record(signal)

    @staticmethod
    def _cluster_for(db: Session, location, disease, when: Optional[datetime]) -> str:
        """Join the cluster of a recent report with the same location and disease, or
        start a new one. Replaces the old behaviour of merging such reports into one
        record, which lost the individual reports. Location matching is by text until
        the geocoder assigns P-codes."""
        if not location or location == "Unknown" or not disease or disease == "Unknown":
            return str(uuid.uuid4())
        since = (when or datetime.now(timezone.utc)) - CLUSTER_WINDOW
        if db.get_bind().dialect.name == "sqlite":  # SQLite stores naive UTC timestamps
            since = since.astimezone(timezone.utc).replace(tzinfo=None) if since.tzinfo else since
        existing = db.scalars(
            select(Signal.cluster_id)
            .where(func.lower(Signal.location_text) == location.lower())
            .where(func.lower(Signal.disease) == disease.lower())
            .where(Signal.created_at >= since)
            .order_by(Signal.created_at.desc())
            .limit(1)
        ).first()
        return existing or str(uuid.uuid4())

    def all_records(self, limit: Optional[int] = None) -> list[dict]:
        """Newest first."""
        with self._session_factory() as db:
            q = select(Signal).order_by(Signal.created_at.desc(), Signal.id)
            if limit:
                q = q.limit(limit)
            return [to_record(s) for s in db.scalars(q)]

    def get(self, session_id: str) -> Optional[dict]:
        with self._session_factory() as db:
            s = db.get(Signal, session_id)
            return to_record(s) if s else None

    def exists(self, session_id: str) -> bool:
        with self._session_factory() as db:
            return db.get(Signal, session_id) is not None

    def set_status(self, session_id: str, status: str, reviewer: Optional[str] = None) -> bool:
        with self._session_factory() as db:
            s = db.get(Signal, session_id)
            if s is None:
                return False
            s.status = status
            s.reviewed_by = reviewer
            s.reviewed_at = datetime.now(timezone.utc)
            db.commit()
            return True

    def replace_analysis(self, session_id: str, result: dict) -> bool:
        """Overwrite a record's extraction and analysis (used when reprocessing)."""
        with self._session_factory() as db:
            s = db.get(Signal, session_id)
            if s is None:
                return False
            extracted = _plain(result["extracted_data"]) or {}
            analysis = {k: _plain(result.get(k)) for k in ("validation", "risk_analysis", "consensus", "context_research", "alert")}
            s.extracted, s.analysis = extracted, analysis
            s.location_text = extracted.get("location")
            s.disease = (analysis.get("risk_analysis") or {}).get("possible_disease")
            s.cases = extracted.get("cases") if isinstance(extracted.get("cases"), int) else None
            s.classification = extracted.get("classification")
            s.analysis_failed = analysis_failed(analysis, extracted)
            db.commit()
            return True

    def failed_records(self) -> list[dict]:
        with self._session_factory() as db:
            q = select(Signal).where(Signal.analysis_failed.is_(True)).order_by(Signal.created_at.desc())
            return [to_record(s) for s in db.scalars(q)]

    def count(self) -> int:
        with self._session_factory() as db:
            return db.scalar(select(func.count()).select_from(Signal)) or 0
