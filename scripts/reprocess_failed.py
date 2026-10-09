"""
Re-run stored outbreak records whose AI analysis failed (for example because the
Gemini model they used was retired), and replace the failed analysis in place.

    python scripts/reprocess_failed.py --dry-run   # list what would change
    python scripts/reprocess_failed.py             # reprocess and save

Stop the backend first: it keeps the records in memory and would overwrite this
script's changes the next time it saves.

For each failed record the original report text (raw_report) goes through the same
pipeline as /outbreak/process. The record keeps its session_id, dates and review
status; extracted data, validation, risk opinions, consensus and alert are replaced.
If the text now yields several records (one per location), the one matching the
record's location replaces it; when the old location was "Unknown", the first
replaces it and the rest are added as new pending records. A record whose re-run
fails again is left untouched. models/outbreak_data.json is backed up before saving.
"""

import argparse
import asyncio
import json
import shutil
import sys
import uuid
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from services.agents import DATA_STORE_PATH  # noqa: E402

FAILURE_MARKERS = (
    "Analysis failed",
    "generation failed",
    "Gemini failed",
    "scan failed",
    "cognitive engine",
    "is no longer available",
    "is not found for API version",
)
ANALYSIS_FIELDS = ("extracted_data", "validation", "risk_analysis", "consensus", "alert")


def is_failed(record: dict) -> bool:
    text = json.dumps([record.get(f) for f in ANALYSIS_FIELDS], default=str)
    return any(m in text for m in FAILURE_MARKERS)


def dump(value):
    return value.model_dump(mode="json") if hasattr(value, "model_dump") else value


def to_fields(result: dict) -> dict:
    return {
        "extracted_data": dump(result["extracted_data"]),
        "validation": dump(result["validation"]),
        "risk_analysis": dump(result["risk_analysis"]),
        "consensus": dump(result["consensus"]),
        "context_research": dump(result.get("context_research")),
        "alert": dump(result["alert"]),
    }


def norm(location) -> str:
    return str(location or "").strip().casefold()


async def reprocess(records: list, failed: list, super_agent, history: str) -> tuple:
    updated, added, still_failing, skipped = 0, [], [], []
    now = str(datetime.now())
    for record in failed:
        sid = record["session_id"]
        raw = (record.get("raw_report") or "").strip()
        if not raw:
            skipped.append((sid, "no original report text"))
            continue
        print(f"→ {sid[:8]}  {record['extracted_data'].get('location')} … ", end="", flush=True)
        try:
            results = [to_fields(r) for r in await super_agent.process_outbreak_parallel(raw, history)]
        except Exception as e:
            still_failing.append((sid, str(e)))
            print("failed")
            continue
        results = [r for r in results if not is_failed(r)]
        if not results:
            still_failing.append((sid, "the AI analysis failed again"))
            print("failed again")
            continue

        old_loc = norm(record["extracted_data"].get("location"))
        if old_loc and old_loc != "unknown":
            match = [r for r in results if norm(r["extracted_data"].get("location")) == old_loc]
            if not match and len(results) == 1:
                match = results
            if not match:
                skipped.append((sid, f"re-run found {len(results)} locations, none named {old_loc!r}"))
                print("skipped")
                continue
            primary, extra = match[0], []
        else:
            # Skip locations another record already holds for this same report text.
            taken = {norm(r["extracted_data"].get("location")) for r in records + added
                     if r is not record and (r.get("raw_report") or "").strip() == raw}
            fresh = [r for r in results if norm(r["extracted_data"].get("location")) not in taken]
            if not fresh:
                skipped.append((sid, "every location in this report already has its own record"))
                print("skipped (duplicate)")
                continue
            primary, extra = fresh[0], fresh[1:]

        record.update(primary)
        record["reprocessed_at"] = now
        updated += 1
        for r in extra:
            added.append({
                "session_id": str(uuid.uuid4()),
                **r,
                "status": "pending",
                "created_at": record.get("created_at", now),
                "timestamp": record.get("timestamp", now),
                "raw_report": raw,
                "split_from": sid,
                "reprocessed_at": now,
            })
        print(f"done ({primary['consensus'].get('final_risk_level')})" + (f", +{len(extra)} new" if extra else ""))
    records.extend(added)
    return updated, added, still_failing, skipped


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dry-run", action="store_true", help="list failed records without changing anything")
    args = parser.parse_args()

    path = Path(DATA_STORE_PATH)
    records = json.loads(path.read_text(encoding="utf-8"))
    failed = [r for r in records if is_failed(r)]
    print(f"{len(records)} records, {len(failed)} with a failed analysis:\n")
    for r in failed:
        print(f"  {r['session_id'][:8]}  {r.get('status', 'pending'):9}  {r['extracted_data'].get('location')}")
    if args.dry_run or not failed:
        return

    from services.gemini_service import GeminiService
    from services.llm import get_llm
    from services.agents import SuperAgent, DataAssistantAgent

    llm = get_llm(GeminiService())
    history = DataAssistantAgent(llm).get_historical_context()
    print("\nReprocessing (about 7 AI calls per record)…")
    updated, added, still_failing, skipped = asyncio.run(reprocess(records, failed, SuperAgent(llm), history))

    if updated or added:
        backup = path.with_name(f"outbreak_data.backup-{datetime.now():%Y%m%d-%H%M%S}.json")
        shutil.copy2(path, backup)
        path.write_text(json.dumps(records, indent=4, default=str), encoding="utf-8")
        print(f"\nSaved. Backup of the previous file: {backup.name}")

    print(f"\nReplaced: {updated}   New records from multi-location reports: {len(added)}")
    for label, items in (("Still failing", still_failing), ("Skipped", skipped)):
        for sid, why in items:
            print(f"{label}: {sid[:8]} — {why}")
    approved = [r["session_id"][:8] for r in failed if r.get("status") != "pending" and r.get("reprocessed_at")]
    if approved:
        print(f"\nNote: these were already approved/rejected before reprocessing; review them again: {', '.join(approved)}")


if __name__ == "__main__":
    main()
