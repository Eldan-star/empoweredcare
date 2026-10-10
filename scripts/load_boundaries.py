"""
Load OCHA administrative boundaries (COD-AB) for Ethiopia into the database: regions,
zones and woredas with their P-codes, plus which units share a border.

1. Download the boundaries from HDX in your browser:
   https://data.humdata.org/dataset/cod-ab-eth  (the shapefile zip, or GeoJSON per level)
   Optionally the population table: https://data.humdata.org/dataset/cod-ps-eth
2. Run, pointing at the files for each level:

    python scripts/load_boundaries.py --adm1 eth_admbnda_adm1.zip --adm2 eth_admbnda_adm2.zip \\
        --adm3 eth_admbnda_adm3.zip --population eth_admpop_adm3.csv --dry-run
    (then the same without --dry-run)

Running it again updates units in place (by P-code) and rebuilds the adjacency table.
"""

import argparse
import csv
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import delete, select  # noqa: E402

from db.models import OrgUnit, OrgUnitAdjacency  # noqa: E402
from services.boundaries import LEVEL_NAMES, adjacency, read_features, units_from_features  # noqa: E402

POP_COLUMNS = ("T_TL", "Total", "total", "population", "pop", "Pop_Total")


def read_population(path: Path, column: str = None) -> dict:
    with open(path, newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        return {}
    cols = list(rows[0])
    pcode_cols = sorted((c for c in cols if re.fullmatch(r"adm(\d)_pcode", c, re.I)),
                        key=lambda c: int(re.findall(r"\d", c)[0]))
    if not pcode_cols:
        raise ValueError(f"{path.name}: no ADMn_PCODE column (columns: {cols})")
    pop_col = column or next((c for c in POP_COLUMNS if c in cols), None)
    if not pop_col:
        raise ValueError(f"{path.name}: say which column holds total population with --pop-column (columns: {cols})")
    out = {}
    for r in rows:
        try:
            out[r[pcode_cols[-1]].strip()] = int(float(str(r[pop_col]).replace(",", "")))
        except (TypeError, ValueError):
            continue
    return out


def load(session, level_files: dict, population: dict, source: str):
    """Upsert units level by level, then rebuild adjacency. Returns a summary dict."""
    summary = {"units": {}, "adjacent_pairs": {}, "orphans": [], "population_matched": 0}
    known = set(session.scalars(select(OrgUnit.pcode)))
    for level in sorted(level_files):
        units = units_from_features(read_features(level_files[level]), level)
        for u in units:
            if u.parent_pcode and u.parent_pcode not in known:
                summary["orphans"].append(f"{u.pcode} {u.name} (parent {u.parent_pcode} not loaded)")
                continue
            pt = u.geometry.representative_point()
            row = session.get(OrgUnit, u.pcode) or OrgUnit(pcode=u.pcode)
            row.name, row.level, row.level_name = u.name, level, LEVEL_NAMES.get(level)
            row.parent_pcode = u.parent_pcode
            row.aliases = sorted(set((row.aliases or []) + u.aliases))
            row.lat, row.lon = round(pt.y, 5), round(pt.x, 5)
            row.valid_from, row.source = u.valid_from, source
            if u.pcode in population:
                row.population = population[u.pcode]
                summary["population_matched"] += 1
            session.add(row)
            known.add(u.pcode)
        session.flush()
        pcodes = [u.pcode for u in units]
        session.execute(delete(OrgUnitAdjacency).where(OrgUnitAdjacency.a_pcode.in_(pcodes)))
        pairs = adjacency([u for u in units if u.pcode in known])
        session.add_all(OrgUnitAdjacency(a_pcode=a, b_pcode=b, shared_border_km=km, centroid_distance_km=d)
                        for a, b, km, d in pairs)
        summary["units"][LEVEL_NAMES.get(level, f"level {level}")] = len(units)
        summary["adjacent_pairs"][LEVEL_NAMES.get(level, f"level {level}")] = len(pairs)
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    for n in (1, 2, 3, 4):
        parser.add_argument(f"--adm{n}", type=Path, help=f"boundary file for admin level {n}")
    parser.add_argument("--population", type=Path, help="COD-PS population CSV (optional)")
    parser.add_argument("--pop-column", help="population column name, if not detected")
    parser.add_argument("--source", default="OCHA COD-AB", help="label stored with each unit")
    parser.add_argument("--dry-run", action="store_true", help="read and check everything, save nothing")
    args = parser.parse_args()

    level_files = {n: getattr(args, f"adm{n}") for n in (1, 2, 3, 4) if getattr(args, f"adm{n}")}
    if not level_files:
        parser.error("give at least --adm1")
    population = read_population(args.population, args.pop_column) if args.population else {}

    from db.session import SessionLocal
    with SessionLocal() as session:
        summary = load(session, level_files, population, args.source)
        if args.dry_run:
            session.rollback()
        else:
            session.commit()

    print(("Checked (nothing saved): " if args.dry_run else "Loaded: ")
          + ", ".join(f"{n} {k}s" for k, n in summary["units"].items()))
    print("Neighbouring pairs: " + ", ".join(f"{n} between {k}s" for k, n in summary["adjacent_pairs"].items()))
    if population:
        print(f"Population matched for {summary['population_matched']} units.")
    if summary["orphans"]:
        print(f"\n{len(summary['orphans'])} units skipped because their parent is missing (load the parent level too):")
        for o in summary["orphans"][:20]:
            print("  " + o)


if __name__ == "__main__":
    main()
