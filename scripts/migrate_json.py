"""
Copy outbreak reports from the old models/outbreak_data.json into the database.

    python scripts/migrate_json.py --dry-run      # show what would be copied
    python scripts/migrate_json.py                # copy (safe to run more than once)
    python scripts/migrate_json.py path/to/other.json

Each record keeps its session_id, dates, review status, original text and AI analysis.
Records already in the database (same session_id) are skipped, so running it twice
does not duplicate anything. The JSON file is left untouched.
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from db.session import SessionLocal  # noqa: E402
from services.signal_store import SignalStore  # noqa: E402

DEFAULT_PATH = Path(__file__).resolve().parent.parent / "models" / "outbreak_data.json"


def parse_time(value):
    try:
        return datetime.fromisoformat(str(value)) if value else None
    except ValueError:
        return None


def migrate(records: list, store: SignalStore, dry_run: bool = False) -> tuple:
    copied, skipped = 0, 0
    # Oldest first, so clusters form in the order reports arrived.
    for r in sorted(records, key=lambda r: str(r.get("created_at") or r.get("timestamp") or "")):
        sid = r.get("session_id")
        if not sid or store.exists(sid):
            skipped += 1
            continue
        if not dry_run:
            store.add(
                r.get("extracted_data") or {},
                session_id=sid,
                raw_text=r.get("raw_report") or "",
                source_type="legacy",
                validation=r.get("validation"),
                risk_analysis=r.get("risk_analysis"),
                consensus=r.get("consensus"),
                context_research=r.get("context_research"),
                alert=r.get("alert"),
                status=r.get("status") or "pending",
                created_at=parse_time(r.get("created_at") or r.get("timestamp")),
            )
        copied += 1
    return copied, skipped


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("path", nargs="?", default=str(DEFAULT_PATH))
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    records = json.loads(Path(args.path).read_text(encoding="utf-8"))
    store = SignalStore(SessionLocal)
    copied, skipped = migrate(records, store, args.dry_run)
    verb = "Would copy" if args.dry_run else "Copied"
    print(f"{len(records)} records in {Path(args.path).name}. {verb} {copied}; skipped {skipped} already in the database.")
    if not args.dry_run:
        print(f"The database now holds {store.count()} reports.")


if __name__ == "__main__":
    main()
