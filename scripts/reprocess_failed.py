"""
Re-run stored outbreak reports whose AI analysis failed (for example because the
Gemini model they used was retired, or the quota ran out), and replace the failed
analysis in place.

    python scripts/reprocess_failed.py --dry-run   # list what would change
    python scripts/reprocess_failed.py             # reprocess and save

The backend can keep running: records live in the database now.

For each failed report the original text goes through the same pipeline as
/outbreak/process. The report keeps its session_id, dates and review status; its
extracted data, validation, risk opinions, consensus and alert are replaced.
If the text now yields several records (one per location), the one matching the
report's location replaces it; when the old location was "Unknown", the first new
location replaces it and the others are added as new pending reports, skipping any
location that already has a report from the same text. A report whose re-run fails
again is left untouched. When the AI quota runs out the script stops; finished
reports are kept and the rest can be retried later.
"""

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from services.gemini_service import AIQuotaExhausted  # noqa: E402
from services.signal_store import SignalStore, analysis_failed  # noqa: E402


def norm(location) -> str:
    return str(location or "").strip().casefold()


def is_failed_result(r: dict) -> bool:
    plain = {k: (v.model_dump(mode="json") if hasattr(v, "model_dump") else v) for k, v in r.items()}
    analysis = {k: plain.get(k) for k in ("validation", "risk_analysis", "consensus", "alert")}
    return analysis_failed(analysis, plain.get("extracted_data") or {})


async def reprocess(store: SignalStore, failed: list, super_agent, history: str) -> tuple:
    updated, added, still_failing, skipped = 0, [], [], []
    for record in failed:
        sid = record["session_id"]
        raw = (record.get("raw_report") or "").strip()
        if not raw:
            skipped.append((sid, "no original report text"))
            continue
        print(f"→ {sid[:8]}  {record['extracted_data'].get('location')} … ", end="", flush=True)
        try:
            results = await super_agent.process_outbreak_parallel(raw, history)
        except AIQuotaExhausted as e:
            print("stopped")
            print(f"\n{e}\nReports finished so far are kept; run the script again later for the rest.")
            break
        except Exception as e:
            still_failing.append((sid, str(e)))
            print("failed")
            continue
        results = [r for r in results if not is_failed_result(r)]
        if not results:
            still_failing.append((sid, "the AI analysis failed again"))
            print("failed again")
            continue

        def loc(r):
            ex = r["extracted_data"]
            return norm(ex.location if hasattr(ex, "location") else ex.get("location"))

        old_loc = norm(record["extracted_data"].get("location"))
        if old_loc and old_loc != "unknown":
            match = [r for r in results if loc(r) == old_loc] or (results if len(results) == 1 else [])
            if not match:
                skipped.append((sid, f"re-run found {len(results)} locations, none named {old_loc!r}"))
                print("skipped")
                continue
            primary, extra = match[0], []
        else:
            # Skip locations another report already holds for this same text.
            taken = {norm(r["extracted_data"].get("location")) for r in store.all_records()
                     if r["session_id"] != sid and (r.get("raw_report") or "").strip() == raw}
            fresh = [r for r in results if loc(r) not in taken]
            if not fresh:
                skipped.append((sid, "every location in this report already has its own record"))
                print("skipped (duplicate)")
                continue
            primary, extra = fresh[0], fresh[1:]

        store.replace_analysis(sid, primary)
        updated += 1
        for r in extra:
            added.append(store.add(
                r["extracted_data"], raw_text=raw, source_type=record.get("source_type") or "report",
                validation=r.get("validation"), risk_analysis=r.get("risk_analysis"),
                consensus=r.get("consensus"), context_research=r.get("context_research"), alert=r.get("alert"),
            ))
        level = getattr(primary["consensus"], "final_risk_level", None) or (primary["consensus"] or {}).get("final_risk_level")
        print(f"done ({level})" + (f", +{len(extra)} new" if extra else ""))
    return updated, added, still_failing, skipped


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dry-run", action="store_true", help="list failed reports without changing anything")
    args = parser.parse_args()

    from db.session import SessionLocal
    store = SignalStore(SessionLocal)
    failed = store.failed_records()
    print(f"{store.count()} reports, {len(failed)} with a failed analysis:\n")
    for r in failed:
        print(f"  {r['session_id'][:8]}  {r.get('status', 'pending'):9}  {r['extracted_data'].get('location')}")
    if args.dry_run or not failed:
        return

    from services.gemini_service import GeminiService
    from services.llm import get_llm
    from services.agents import SuperAgent, DataAssistantAgent

    llm = get_llm(GeminiService())
    history = DataAssistantAgent(llm, store).get_historical_context()
    print("\nReprocessing (about 4 AI calls per report)…")
    updated, added, still_failing, skipped = asyncio.run(reprocess(store, failed, SuperAgent(llm), history))

    print(f"\nReplaced: {updated}   New reports from multi-location texts: {len(added)}")
    for label, items in (("Still failing", still_failing), ("Skipped", skipped)):
        for sid, why in items:
            print(f"{label}: {sid[:8]} — {why}")
    reviewed = [r["session_id"][:8] for r in failed if r.get("status") != "pending"]
    if reviewed and updated:
        print(f"\nNote: these were already approved/rejected before reprocessing; review them again: {', '.join(reviewed)}")


if __name__ == "__main__":
    main()
