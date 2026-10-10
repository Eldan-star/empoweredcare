"""
Attach P-codes to stored reports, after boundaries have been loaded (or updated).

    python scripts/geocode_signals.py          # reports that have no P-code yet
    python scripts/geocode_signals.py --all    # every report again

Ambiguous places (a name that fits several units) are flagged, not guessed.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from db.session import SessionLocal  # noqa: E402
from services.geocoder import Geocoder  # noqa: E402
from services.signal_store import SignalStore  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--all", action="store_true", help="re-geocode every report, not only those without a P-code")
    args = parser.parse_args()
    with SessionLocal() as session:
        geocoder = Geocoder.from_db(session)
    if not geocoder.units:
        sys.exit("No boundaries in the database. Run scripts/load_boundaries.py first.")
    counts = SignalStore(SessionLocal, geocoder).regeocode(only_missing=not args.all)
    print(f"Resolved: {counts['resolved']}   Ambiguous (needs a person): {counts['ambiguous']}   "
          f"No match: {counts['unmatched']}")


if __name__ == "__main__":
    main()
