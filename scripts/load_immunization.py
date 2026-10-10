"""
Load measles vaccination coverage (and optionally births and campaigns) from CSV files.

Coverage CSV, one row per place and period. Columns (case-insensitive):
    pcode  or  name      the place; a name is matched with the geocoder (region/zone
                         hint columns "region", "zone" help). "ET" or "Ethiopia" = national.
    year                 e.g. 2023
    month                optional; leave empty or 0 for an annual estimate
    mcv1                 coverage, as 0-1 or a percentage (e.g. 62 or 0.62)
    mcv2                 optional, same format
    births               optional, births in that period (monthly if month is given)
    source               optional; else --source

A national or regional row is applied to every zone inside it (stored per zone, with the
source saying so), so zone-level estimates can be added later without changing the model.

Campaign CSV (--campaigns): pcode or name, start_date (YYYY-MM-DD), end_date,
age_min_months, age_max_months, coverage (0-1 or %), source.

Sources: IHME subnational MCV1 estimates (zone/admin-2), WUENIC (national MCV1/MCV2), DHS
(regional), EPHI/WHO campaign reports. See docs/EVALUATION.md.

    python scripts/load_immunization.py --coverage data/coverage.csv --dry-run
    python scripts/load_immunization.py --coverage data/coverage.csv --campaigns data/campaigns.csv
"""

import argparse
import csv
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select  # noqa: E402

from db.models import Campaign, Immunization, OrgUnit  # noqa: E402
from db.session import session_scope  # noqa: E402

NATIONAL = {"et", "eth", "ethiopia", "national"}


def fraction(value) -> float | None:
    if value is None or str(value).strip() == "":
        return None
    v = float(str(value).replace("%", "").strip())
    v = v / 100 if v > 1.0 else v
    if not 0 <= v <= 1:
        raise ValueError(f"coverage {value!r} is not a share or percentage")
    return v


def read_csv(path: Path) -> list[dict]:
    with open(path, newline="", encoding="utf-8-sig") as f:
        return [{(k or "").strip().lower(): (v or "").strip() for k, v in row.items()} for row in csv.DictReader(f)]


class Places:
    """Turns a row's pcode or name into P-codes, and expands national/regional rows to the
    zones inside them."""

    def __init__(self, session, zone_level: int = 2):
        self.units = {u.pcode: u for u in session.scalars(select(OrgUnit))}
        self.zone_level = zone_level
        self.geocoder = None
        self.session = session

    def resolve(self, row: dict) -> tuple[str | None, str]:
        pcode, name = row.get("pcode", ""), row.get("name", "")
        if pcode.lower() in NATIONAL or name.lower() in NATIONAL:
            return "ET", "national"
        if pcode:
            return (pcode, "pcode") if pcode in self.units else (None, f"unknown P-code {pcode}")
        if not name:
            return None, "no pcode or name"
        if self.geocoder is None:
            from services.geocoder import Geocoder
            self.geocoder = Geocoder.from_db(self.session)
        hints = [row[h] for h in ("region", "zone") if row.get(h)]
        r = self.geocoder.resolve(name, hints)
        if r.pcode and not r.ambiguous:
            return r.pcode, f"matched '{name}' -> {r.name}"
        return None, f"could not match '{name}'" + (" (ambiguous)" if r.ambiguous else "")

    def zones_within(self, pcode: str) -> list[str]:
        if pcode == "ET":
            return [p for p, u in self.units.items() if u.level == self.zone_level]
        unit = self.units[pcode]
        if unit.level >= self.zone_level:
            return [pcode]
        return [p for p, u in self.units.items() if u.level == self.zone_level and p.startswith(pcode)]


def load_coverage(session, rows: list[dict], default_source: str, zone_level: int = 2) -> dict:
    places = Places(session, zone_level)
    existing = {(r.pcode, r.year, r.month, r.source): r for r in session.scalars(select(Immunization))}
    report = {"rows": len(rows), "stored": 0, "skipped": []}
    for n, row in enumerate(rows, start=2):  # line numbers as in a spreadsheet
        pcode, how = places.resolve(row)
        if not pcode:
            report["skipped"].append(f"line {n}: {how}")
            continue
        try:
            year = int(row["year"])
            month = int(row.get("month") or 0)
            mcv1, mcv2 = fraction(row.get("mcv1")), fraction(row.get("mcv2"))
        except (KeyError, ValueError) as e:
            report["skipped"].append(f"line {n}: {e}")
            continue
        births = float(row["births"]) if row.get("births") else None
        source = row.get("source") or default_source
        zones = places.zones_within(pcode)
        for z in zones:
            src = source if z == pcode else f"{source} ({'national' if pcode == 'ET' else pcode} applied to zone)"
            rec = existing.get((z, year, month, src)) or Immunization(pcode=z, year=year, month=month, source=src)
            rec.mcv1_coverage, rec.mcv2_coverage = mcv1, mcv2
            # Births are for the place in the row; split across zones by population.
            if births is not None and len(zones) > 1:
                total = sum(places.units[x].population or 0 for x in zones) or 1
                rec.births = round(births * (places.units[z].population or 0) / total)
            elif births is not None:
                rec.births = round(births)
            session.add(rec)
            existing[(z, year, month, src)] = rec
            report["stored"] += 1
    return report


def load_campaigns(session, rows: list[dict], default_source: str) -> dict:
    places = Places(session)
    report = {"rows": len(rows), "stored": 0, "skipped": []}
    for n, row in enumerate(rows, start=2):
        pcode, how = places.resolve(row)
        if not pcode:
            report["skipped"].append(f"line {n}: {how}")
            continue
        try:
            start = date.fromisoformat(row["start_date"])
            end = date.fromisoformat(row["end_date"]) if row.get("end_date") else None
        except (KeyError, ValueError) as e:
            report["skipped"].append(f"line {n}: bad date ({e})")
            continue
        targets = [p for p, u in places.units.items() if u.level == 1] if pcode == "ET" else [pcode]
        for p in targets:
            session.add(Campaign(pcode=p, start_date=start, end_date=end, vaccine=row.get("vaccine") or "measles",
                                 age_min_months=int(row["age_min_months"]) if row.get("age_min_months") else None,
                                 age_max_months=int(row["age_max_months"]) if row.get("age_max_months") else None,
                                 coverage=fraction(row.get("coverage")), source=row.get("source") or default_source))
            report["stored"] += 1
    return report


def main(argv=None):
    ap = argparse.ArgumentParser(description="Load measles vaccination coverage and campaigns.")
    ap.add_argument("--coverage", type=Path)
    ap.add_argument("--campaigns", type=Path)
    ap.add_argument("--source", help="source label when the file has no source column")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)
    if not (args.coverage or args.campaigns):
        ap.error("give --coverage and/or --campaigns")
    with session_scope() as s:
        for label, path, fn in (("Coverage", args.coverage, load_coverage), ("Campaigns", args.campaigns, load_campaigns)):
            if not path:
                continue
            rep = fn(s, read_csv(path), args.source or path.name)
            print(f"{label}: {rep['rows']} rows read, {rep['stored']} records stored, {len(rep['skipped'])} skipped")
            for line in rep["skipped"][:20]:
                print("  -", line)
        if args.dry_run:
            s.rollback()
            print("Dry run: nothing saved.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
