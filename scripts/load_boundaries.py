"""
Load OCHA administrative boundaries (COD-AB) for Ethiopia into the database: regions,
zones and woredas with their P-codes, plus which units share a border.

1. Download into the project's data/boundaries folder (see docs/DATABASE_SETUP.md):
   https://data.humdata.org/dataset/cod-ab-eth  -> eth_admin_boundaries.shp.zip
   https://data.humdata.org/dataset/cod-ps-eth  -> table_eth_codps_2026.xlsx
2. Check, then load:

    python scripts/load_boundaries.py --boundaries data/boundaries/eth_admin_boundaries.shp.zip \
        --population data/boundaries/table_eth_codps_2026.xlsx --dry-run
    (then the same without --dry-run)

Running it again updates units in place (by P-code) and rebuilds the adjacency table.
"""

import argparse
import csv
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from sqlalchemy import delete, select  # noqa: E402

from db.models import OrgUnit, OrgUnitAdjacency  # noqa: E402
from services.boundaries import (  # noqa: E402
    LEVEL_NAMES, adjacency, read_features, shapefile_levels_in_zip, units_from_features,
)

POP_COLUMNS = ("T_TL", "Total", "total", "population", "pop", "Pop_Total")
PCODE_COLUMN = re.compile(r"adm(?:in)?(\d)_?pcod(?:e)?$", re.I)  # adm3_pcode, admin3Pcode, admin3_pcod


def _pcode_columns(columns) -> list:
    """P-code columns, deepest level last."""
    found = [(int(PCODE_COLUMN.match(str(c))[1]), c) for c in columns if PCODE_COLUMN.match(str(c))]
    return [c for _, c in sorted(found)]


def read_population(path: Path, column: str = None) -> dict:
    """{P-code: total population} from an OCHA COD-PS table (.xlsx or .csv). In a
    workbook, the sheet with the most detailed P-codes is used (e.g. COD_PS)."""
    path = Path(path)
    if path.suffix.lower() in (".xlsx", ".xls"):
        import pandas as pd
        sheets = pd.read_excel(path, sheet_name=None, dtype=str)
        tables = [df for df in sheets.values() if _pcode_columns(df.columns)]
        if not tables:
            raise ValueError(f"{path.name}: no sheet has a P-code column (e.g. admin3_pcod)")
        df = max(tables, key=lambda d: (int(PCODE_COLUMN.match(str(_pcode_columns(d.columns)[-1]))[1]), len(d)))
        rows = df.fillna("").to_dict("records")
    else:
        with open(path, newline="", encoding="utf-8-sig") as f:
            rows = list(csv.DictReader(f))
    if not rows:
        return {}
    cols = list(rows[0])
    pcode_cols = _pcode_columns(cols)
    if not pcode_cols:
        raise ValueError(f"{path.name}: no P-code column (columns: {cols})")
    pop_col = column or next((c for c in POP_COLUMNS if c in cols), None)
    if not pop_col:
        raise ValueError(f"{path.name}: say which column holds total population with --pop-column (columns: {cols})")
    out = {}
    for r in rows:
        pcode = str(r[pcode_cols[-1]] or "").strip()
        if not pcode or pcode.lower() == "nan":  # total rows have no P-code
            continue
        try:
            out[pcode] = int(float(str(r[pop_col]).replace(",", "")))
        except (TypeError, ValueError):
            continue
    return out


def read_aliases(path: Path) -> dict:
    """{P-code: [alias, ...]} from data/place_aliases.csv (columns: pcode, alias, note)."""
    out: dict = {}
    if path and Path(path).exists():
        with open(path, newline="", encoding="utf-8-sig") as f:
            for r in csv.DictReader(f):
                if r.get("pcode") and r.get("alias"):
                    out.setdefault(r["pcode"].strip(), []).append(r["alias"].strip())
    return out


def load(session, level_files: dict, population: dict, source: str, aliases: dict = None):
    """Upsert units level by level, then rebuild adjacency. Returns a summary dict."""
    summary = {"units": {}, "adjacent_pairs": {}, "orphans": [], "population_matched": 0, "aliases_added": 0}
    aliases = aliases or {}
    known = set(session.scalars(select(OrgUnit.pcode)))
    for level in sorted(level_files):
        path, member = level_files[level] if isinstance(level_files[level], tuple) else (level_files[level], None)
        units = units_from_features(read_features(path, member), level)
        for u in units:
            if u.parent_pcode and u.parent_pcode not in known:
                summary["orphans"].append(f"{u.pcode} {u.name} (parent {u.parent_pcode} not loaded)")
                continue
            pt = u.geometry.representative_point()
            row = session.get(OrgUnit, u.pcode) or OrgUnit(pcode=u.pcode)
            row.name, row.level, row.level_name = u.name, level, LEVEL_NAMES.get(level)
            row.parent_pcode = u.parent_pcode
            extra = aliases.get(u.pcode, [])
            summary["aliases_added"] += len(extra)
            row.aliases = sorted(set((row.aliases or []) + u.aliases + extra))
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
    parser.add_argument("--boundaries", type=Path,
                        help="the all-levels zip from HDX (eth_admin_boundaries.shp.zip); levels 1-3 are picked automatically")
    for n in (1, 2, 3, 4):
        parser.add_argument(f"--adm{n}", type=Path, help=f"boundary file for admin level {n} (instead of --boundaries)")
    parser.add_argument("--population", type=Path, help="COD-PS population table, .xlsx or .csv (optional)")
    parser.add_argument("--aliases", type=Path, default=ROOT / "data" / "place_aliases.csv",
                        help="extra spellings to attach (default: data/place_aliases.csv)")
    parser.add_argument("--pop-column", help="population column name, if not detected")
    parser.add_argument("--source", default="OCHA COD-AB", help="label stored with each unit")
    parser.add_argument("--dry-run", action="store_true", help="read and check everything, save nothing")
    args = parser.parse_args()

    level_files = {n: getattr(args, f"adm{n}") for n in (1, 2, 3, 4) if getattr(args, f"adm{n}")}
    if args.boundaries:
        found = shapefile_levels_in_zip(args.boundaries)
        level_files.update({n: (args.boundaries, stem) for n, stem in found.items() if n in (1, 2, 3)})
    if not level_files:
        parser.error("give --boundaries (the HDX zip) or at least --adm1")
    population = read_population(args.population, args.pop_column) if args.population else {}

    from db.session import SessionLocal
    with SessionLocal() as session:
        summary = load(session, level_files, population, args.source, read_aliases(args.aliases))
        if args.dry_run:
            session.rollback()
        else:
            session.commit()

    print(("Checked (nothing saved): " if args.dry_run else "Loaded: ")
          + ", ".join(f"{n} {k}s" for k, n in summary["units"].items()))
    print("Neighbouring pairs: " + ", ".join(f"{n} between {k}s" for k, n in summary["adjacent_pairs"].items()))
    if population:
        print(f"Population matched for {summary['population_matched']} units.")
    if summary["aliases_added"]:
        print(f"Extra spellings attached from {args.aliases.name}: {summary['aliases_added']}.")
    if summary["orphans"]:
        print(f"\n{len(summary['orphans'])} units skipped because their parent is missing (load the parent level too):")
        for o in summary["orphans"][:20]:
            print("  " + o)


if __name__ == "__main__":
    main()
