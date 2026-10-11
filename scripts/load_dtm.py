"""
Load IOM Displacement Tracking Matrix (DTM) figures: internally displaced people (IDPs)
present per zone and survey round, into context_factors.

Source (public, no login): HDX "Ethiopia IOM Displacement Tracking Matrix (DTM) from API"
    https://data.humdata.org/dataset/eth-iom-dtm-from-api  -> the admin levels 0-2 CSV
Columns used: adminLevel, admin1Name, admin2Pcode, admin2Name, numPresentIdpInd,
reportingDate, displacementReason.

Two factors per zone and round: idps_hosted (all reasons) and idps_conflict. They enter
the model only through the named pathways (SYSTEM_SPEC 5.6). Zone codes from older rounds
that no longer exist are matched by name within the region, or reported as skipped.

    python scripts/load_dtm.py --csv data/boundaries/eth-iom-dtm-from-api-admin-0-to-2.csv --dry-run
"""

import argparse
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select  # noqa: E402

from db.models import ContextFactor, OrgUnit  # noqa: E402
from db.session import session_scope  # noqa: E402

SOURCE = "IOM DTM (HDX API extract)"


def read_dtm(path: Path) -> list[dict]:
    import pandas as pd
    df = pd.read_csv(path)
    if str(df.iloc[0, 0]).startswith("#"):  # HXL tag row
        df = df.iloc[1:]
    df = df[pd.to_numeric(df["adminLevel"], errors="coerce") == 2]
    rows = []
    for _, r in df.iterrows():
        try:
            n = float(r["numPresentIdpInd"])
            d = pd.to_datetime(r["reportingDate"]).date()
        except (TypeError, ValueError):
            continue
        rows.append({"pcode": str(r["admin2Pcode"]).strip(), "name": str(r["admin2Name"]).strip(),
                     "region": str(r.get("admin1Name", "")).strip(), "idps": n, "date": d,
                     "reason": str(r.get("displacementReason", "")).strip().lower()})
    return rows


def load(session, rows: list[dict], zone_level: int = 2) -> dict:
    units = {u.pcode: u for u in session.scalars(select(OrgUnit))}
    geocoder = None
    totals = defaultdict(lambda: {"idps_hosted": 0.0, "idps_conflict": 0.0})
    skipped = set()
    for r in rows:
        p = r["pcode"] if r["pcode"] in units and units[r["pcode"]].level == zone_level else None
        if p is None:
            if geocoder is None:
                from services.geocoder import Geocoder
                geocoder = Geocoder.from_db(session)
            g = geocoder.resolve(f"{r['name']} zone", [r["region"]])
            p = g.pcode if g.pcode and not g.ambiguous and g.level == zone_level else None
        if p is None:
            skipped.add(f"{r['pcode']} {r['name']} ({r['region']})")
            continue
        key = (p, date(r["date"].year, r["date"].month, 1))
        totals[key]["idps_hosted"] += r["idps"]
        if r["reason"].startswith("conflict"):
            totals[key]["idps_conflict"] += r["idps"]
    existing = {(c.pcode, c.factor, c.period_start): c for c in session.scalars(
        select(ContextFactor).where(ContextFactor.source == SOURCE))}
    n = 0
    for (p, start), vals in totals.items():
        for factor, v in vals.items():
            row = existing.get((p, factor, start)) or ContextFactor(pcode=p, factor=factor, period_start=start, source=SOURCE)
            row.value = v
            session.add(row)
            n += 1
    return {"rows": len(rows), "stored": n, "zones": len({p for p, _ in totals}), "skipped": sorted(skipped)}


def main(argv=None):
    ap = argparse.ArgumentParser(description="Load IOM DTM displacement figures per zone.")
    ap.add_argument("--csv", type=Path, required=True)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)
    with session_scope() as s:
        rep = load(s, read_dtm(args.csv))
        print(f"Zone rows read: {rep['rows']}; factors stored: {rep['stored']} for {rep['zones']} zones; "
              f"zone codes not matched: {len(rep['skipped'])}")
        for line in rep["skipped"][:15]:
            print("  -", line)
        if args.dry_run:
            s.rollback()
            print("Dry run: nothing saved.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
