import asyncio
import importlib.util
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from sqlalchemy.orm import sessionmaker

from models.schemas import ConsensusResult, OutbreakReport, RiskAnalysis
from services.signal_store import SignalStore

ROOT = Path(__file__).resolve().parent.parent


def load_script(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def store(engine):
    return SignalStore(sessionmaker(bind=engine, expire_on_commit=False))


def risk(level="HIGH", disease="Measles", reason="ok"):
    return RiskAnalysis(risk_level=level, confidence="80%", possible_disease=disease, reason=reason)


def add(store, location="Jinka", disease="Measles", **kw):
    return store.add(
        OutbreakReport(location=location, symptoms=["rash", "fever"], cases=12),
        risk_analysis=risk(disease=disease),
        consensus=ConsensusResult(final_risk_level="HIGH", average_confidence=80, consensus_reached=True,
                                  agent_opinions=[risk(disease=disease)], final_reasoning="r"),
        alert={"title": "t"}, raw_text=f"{location} report", **kw,
    )


def test_record_shape_matches_the_old_json_api(store):
    rec = add(store, session_id="abc", submitted_by="officer@example.org")
    for key in ("session_id", "extracted_data", "validation", "risk_analysis", "consensus",
                "context_research", "alert", "status", "created_at", "timestamp", "raw_report"):
        assert key in rec
    assert rec["session_id"] == "abc" and rec["status"] == "pending"
    assert rec["extracted_data"]["symptoms"] == ["rash", "fever"]
    assert rec["consensus"]["agent_opinions"][0]["possible_disease"] == "Measles"
    assert rec["analysis_failed"] is False


def test_newest_first_and_status_update(store):
    old = add(store, location="Jimma", created_at=datetime.now(timezone.utc) - timedelta(days=3))
    new = add(store, location="Gondar")
    assert [r["session_id"] for r in store.all_records()] == [new["session_id"], old["session_id"]]
    assert store.set_status(old["session_id"], "approved", reviewer="admin@example.org")
    assert store.get(old["session_id"])["status"] == "approved"
    assert store.set_status("missing", "approved") is False


def test_same_place_and_disease_within_14_days_share_a_cluster(store):
    a = add(store, location="Jinka", created_at=datetime.now(timezone.utc) - timedelta(days=5))
    b = add(store, location="jinka")  # case differences don't matter
    c = add(store, location="Jinka", disease="Cholera")
    d = add(store, location="Arba Minch")
    assert a["cluster_id"] == b["cluster_id"]
    assert len({b["cluster_id"], c["cluster_id"], d["cluster_id"]}) == 3
    assert store.count() == 4  # nothing merged away


def test_old_report_outside_window_starts_a_new_cluster(store):
    a = add(store, location="Jinka", created_at=datetime.now(timezone.utc) - timedelta(days=30))
    b = add(store, location="Jinka")
    assert a["cluster_id"] != b["cluster_id"]


def test_failed_analysis_is_flagged_and_can_be_replaced(store):
    bad = store.add(OutbreakReport(location="Unknown", cases=0),
                    risk_analysis=risk("UNKNOWN", "Unknown", "Analysis failed: 404 model retired"),
                    raw_text="Jinka: 12 suspected measles")
    assert bad["analysis_failed"] and [r["session_id"] for r in store.failed_records()] == [bad["session_id"]]
    store.replace_analysis(bad["session_id"], {
        "extracted_data": OutbreakReport(location="Jinka", cases=12), "validation": None,
        "risk_analysis": risk(), "consensus": None, "alert": {"title": "t"},
    })
    fixed = store.get(bad["session_id"])
    assert not fixed["analysis_failed"] and fixed["extracted_data"]["location"] == "Jinka"
    assert store.failed_records() == []


def test_migrating_the_real_json_file_is_complete_and_repeatable(store):
    migrate_json = load_script("migrate_json")
    records = json.loads((ROOT / "models" / "outbreak_data.json").read_text(encoding="utf-8"))
    copied, skipped = migrate_json.migrate(records, store)
    assert (copied, skipped) == (len(records), 0)
    assert migrate_json.migrate(records, store) == (0, len(records))  # second run copies nothing
    assert store.count() == len(records)
    sample = records[0]
    got = store.get(sample["session_id"])
    assert got["status"] == sample["status"] and got["raw_report"] == sample["raw_report"]
    assert got["extracted_data"] == sample["extracted_data"]
    assert got["source_type"] == "legacy"
    # The records whose stored analysis is an error message are flagged for reprocessing.
    assert len(store.failed_records()) == sum(
        any(m in json.dumps(r) for m in ("Analysis failed", "cognitive engine", "generation failed")) for r in records)


def test_reprocess_replaces_failed_reports_and_stops_on_quota(store):
    reprocess_failed = load_script("reprocess_failed")
    from services.gemini_service import AIQuotaExhausted

    first = store.add(OutbreakReport(location="Unknown", cases=0), raw_text="text one",
                      risk_analysis=risk("UNKNOWN", "Unknown", "Analysis failed: x"))
    second = store.add(OutbreakReport(location="Unknown", cases=0), raw_text="text two",
                       risk_analysis=risk("UNKNOWN", "Unknown", "Analysis failed: x"))
    calls = []

    class FakeSuperAgent:
        async def process_outbreak_parallel(self, text, history):
            calls.append(text)
            if len(calls) > 1:
                raise AIQuotaExhausted("AI quota reached: test")
            return [{"extracted_data": OutbreakReport(location=loc, cases=3), "validation": None,
                     "risk_analysis": risk(), "consensus": None, "alert": {"title": "t"}}
                    for loc in ("Arba Minch", "Jinka")]

    failed = store.failed_records()
    updated, added, still, skipped = asyncio.run(reprocess_failed.reprocess(store, failed, FakeSuperAgent(), ""))
    assert updated == 1 and len(added) == 1 and len(calls) == 2  # stopped at the quota, no third call
    remaining = {r["session_id"] for r in store.failed_records()}
    assert len(remaining) == 1 and remaining <= {first["session_id"], second["session_id"]}
    assert store.count() == 3
