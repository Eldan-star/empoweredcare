"""
Check a DHIS2 connection and link its organisation units to our P-codes.

    python scripts/dhis2_check.py                 # server version and unit counts
    python scripts/dhis2_check.py --link          # propose DHIS2 -> P-code links (saves nothing)
    python scripts/dhis2_check.py --link --apply  # store confident links in org_units.dhis2_uid

Uses DHIS2_URL and DHIS2_TOKEN (or DHIS2_USERNAME/DHIS2_PASSWORD) from .env. Only
metadata is read here; no data values are pulled.
"""

import argparse
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from connectors.dhis2 import DHIS2Client, DHIS2Error, match_org_units  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--max-level", type=int, default=4, help="deepest DHIS2 level to read (default 4)")
    parser.add_argument("--level-offset", type=int, default=1,
                        help="DHIS2 level minus our level (1 when the DHIS2 root is the country)")
    parser.add_argument("--link", action="store_true", help="match DHIS2 units to loaded OCHA boundaries")
    parser.add_argument("--apply", action="store_true", help="with --link: save confident matches")
    args = parser.parse_args()

    client = DHIS2Client()
    info = client.system_info()
    print(f"Connected to {client.url}: DHIS2 {info.get('version')}"
          + (" (public demo)" if client.is_demo else ""))
    units = client.org_units(max_level=args.max_level)
    print("Organisation units by level: " + ", ".join(f"level {k}: {v}" for k, v in sorted(Counter(u.level for u in units).items())))
    if not args.link:
        return

    from db.models import OrgUnit
    from db.session import SessionLocal
    from services.geocoder import Geocoder
    with SessionLocal() as session:
        geocoder = Geocoder.from_db(session)
        if not geocoder.units:
            sys.exit("No boundaries in the database. Run scripts/load_boundaries.py first.")
        m = match_org_units(units, geocoder, args.level_offset)
        print(f"Matched: {len(m['matched'])}   Ambiguous: {len(m['ambiguous'])}   Unmatched: {len(m['unmatched'])}")
        names = {u.uid: u.name for u in units}
        for uid, cands in list(m["ambiguous"].items())[:15]:
            print(f"  ambiguous: {names[uid]} -> " + "; ".join(c["path"] for c in cands))
        for uid in m["unmatched"][:15]:
            print(f"  unmatched: {names[uid]}")
        if args.apply:
            for uid, pcode in m["matched"].items():
                session.get(OrgUnit, pcode).dhis2_uid = uid
            session.commit()
            print(f"Saved {len(m['matched'])} links.")


if __name__ == "__main__":
    try:
        main()
    except DHIS2Error as e:
        sys.exit(str(e))
