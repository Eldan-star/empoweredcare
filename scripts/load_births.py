"""
Estimate annual births per woreda and zone and store them (demographics table).

Source: OCHA's 2023 sex- and age-disaggregated population table for Ethiopia (CSA
projection), on the same HDX page as the 2026 table:
    https://data.humdata.org/dataset/cod-ps-eth  ->  eth_admpop_2023.xlsx
It gives each woreda's population aged 0-4. Births per year are estimated as

    births = (population aged 0-4 / 5) x survival adjustment

where the adjustment (default 1.025) adds back the children who died before being
counted (under-5 mortality about 47 per 1,000, UN IGME 2022, spread over the five years).
The rate per 1,000 is then applied to each unit's CURRENT (2026) population, so births
stay consistent with the population the rest of the model uses.

The 2023 table uses pre-2023 woreda codes; units whose code no longer exists take their
zone's, then their region's, then the national average rate. Note: within a region the
CSA projection gives every woreda the same age pattern, so this captures differences
between regions (Addis Ababa about 15 per 1,000, Somali about 36), not between woredas
of one region. WorldPop births and DHIS2 expected births can refine this later.

    python scripts/load_births.py --table data/boundaries/eth_admpop_2023.xlsx --dry-run
"""

import argparse
import sys
from collections import defaultdict
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from sqlalchemy import select  # noqa: E402

from db.models import Demographics, OrgUnit  # noqa: E402
from db.session import session_scope  # noqa: E402

SURVIVAL_ADJUSTMENT = 1.025
SOURCE = "OCHA COD-PS 2023 under-5 (CSA)"


def read_rates(path: Path, adjustment: float = SURVIVAL_ADJUSTMENT) -> dict:
    """{"woreda": {admin3 P-code: (rate, region name)}, "region": {region name: rate}},
    rates in births per 1,000 per year."""
    import pandas as pd
    sheets = pd.read_excel(path, sheet_name=None)
    sheet = next((df for name, df in sheets.items() if "adm3" in name.lower()), None)
    if sheet is None:
        raise ValueError(f"{path.name}: no admin-3 sheet (expected e.g. ETH_admpop_adm3_2023)")
    code = next(c for c in sheet.columns if str(c).lower().startswith("admin3pcode"))
    region_col = next((c for c in sheet.columns if str(c).lower().startswith("admin1name")), None)
    woreda, sums = {}, defaultdict(lambda: [0.0, 0.0])
    for _, r in sheet.iterrows():
        total, u5 = r.get("Total"), r.get("T_00_04")
        if pd.notna(total) and pd.notna(u5) and total > 0:
            region = str(r[region_col]).strip() if region_col else ""
            woreda[str(r[code]).strip()] = (float(u5) / 5 / float(total) * 1000 * adjustment, region)
            sums[region][0] += float(u5)
            sums[region][1] += float(total)
    regions = {name: u5 / 5 / tot * 1000 * adjustment for name, (u5, tot) in sums.items() if tot}
    return {"woreda": woreda, "region": regions}


def _norm(name: Optional[str]) -> str:
    return " ".join((name or "").lower().replace("region", "").replace("-", " ").split())


def _same_name(a: str, b: str) -> bool:
    """Region names are spelled differently between OCHA tables ("Benishangul Gumz" vs
    "Benishangul-Gumuz"), so compare approximately."""
    from rapidfuzz import fuzz
    return fuzz.ratio(_norm(a), _norm(b)) >= 85


def successor_map(path: Path = ROOT / "data" / "historical_units.csv") -> dict:
    """{old region name: [successor P-codes]} from the historical-units list (SNNPR split)."""
    import csv
    out = {}
    if path.exists():
        with open(path, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                if str(row.get("level", "")).strip() == "1":
                    out[_norm(row["name"])] = [p.strip() for p in row["current_pcodes"].split(";")]
    return out


def assign(units: dict, rates: dict, year: int, woreda_level: int = 3, zone_level: int = 2,
           successors: Optional[dict] = None) -> list[Demographics]:
    """Births for every woreda and zone with a population. A 2023 code is used only when
    its 2023 region is the woreda's current region (or a region it split into), because
    some codes were reused after boundary changes."""
    successors = successor_map() if successors is None else successors
    woredas = {p: u for p, u in units.items() if u.level == woreda_level and u.population}
    zones = {p: u for p, u in units.items() if u.level == zone_level}

    def region_of(p):
        z = units.get(units[p].parent_pcode)
        return units.get(z.parent_pcode) if z else None

    def same_region(old_region: str, region) -> bool:
        if region is None or not old_region:
            return True  # nothing to compare against
        return _same_name(old_region, region.name) or region.pcode in successors.get(_norm(old_region), [])

    direct = {p: rates["woreda"][p][0] for p in woredas
              if p in rates["woreda"] and same_region(rates["woreda"][p][1], region_of(p))}

    def avg(group):
        vals = [(direct[p], woredas[p].population) for p in group if p in direct]
        tot = sum(w for _, w in vals)
        return sum(r * w for r, w in vals) / tot if tot else None

    by_zone, by_region = defaultdict(list), defaultdict(list)
    for p, u in woredas.items():
        by_zone[u.parent_pcode].append(p)
        zone = units.get(u.parent_pcode)
        by_region[zone.parent_pcode if zone else None].append(p)
    zone_rate = {z: avg(ps) for z, ps in by_zone.items()}
    region_rate = {r: avg(ps) for r, ps in by_region.items()}
    # Regions with no matched woreda (created after 2023): the 2023 rate of the region
    # with the same name, or of the region they split from.
    for rp, ru in ((p, u) for p, u in units.items() if u.level == 1):
        if region_rate.get(rp) is None:
            old = next((rate for name, rate in rates["region"].items()
                        if _same_name(name, ru.name) or rp in successors.get(_norm(name), [])), None)
            region_rate[rp] = old
    national = avg(list(woredas))
    if national is None:
        raise ValueError("No woreda in the table matches a loaded P-code; load the OCHA boundaries first")

    out, woreda_births = [], defaultdict(float)
    for p, u in woredas.items():
        zone = units.get(u.parent_pcode)
        for rate, method in ((direct.get(p), "woreda under-5"), (zone_rate.get(u.parent_pcode), "zone average"),
                             (region_rate.get(zone.parent_pcode if zone else None), "region average"),
                             (national, "national average")):
            if rate is not None:
                break
        births = rate * u.population / 1000
        woreda_births[u.parent_pcode] += births
        out.append(Demographics(pcode=p, year=year, births=births, birth_rate=rate, method=method, source=SOURCE))
    zone_pop = defaultdict(int)
    for p, u in woredas.items():
        zone_pop[u.parent_pcode] += u.population
    for z, u in zones.items():
        pop = u.population or zone_pop.get(z)
        births, method = woreda_births.get(z), "sum of woredas"
        if not births and pop:
            births, method = (region_rate.get(u.parent_pcode) or national) * pop / 1000, "region average"
        if births and pop:
            out.append(Demographics(pcode=z, year=year, births=births, birth_rate=births / pop * 1000,
                                    method=method, source=SOURCE))
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description="Estimate births per woreda and zone from OCHA under-5 counts.")
    ap.add_argument("--table", type=Path, required=True, help="eth_admpop_2023.xlsx")
    ap.add_argument("--year", type=int, default=2026, help="population year the births apply to")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)
    rates = read_rates(args.table)
    with session_scope() as s:
        units = {u.pcode: u for u in s.scalars(select(OrgUnit))}
        rows = assign(units, rates, args.year)
        for old in s.scalars(select(Demographics).where(Demographics.source == SOURCE, Demographics.year == args.year)):
            s.delete(old)
        s.flush()
        s.add_all(rows)
        methods = defaultdict(int)
        for r in rows:
            methods[r.method] += 1
        total = sum(r.births for r in rows if units[r.pcode].level == 3)
        print(f"Woreda rates read: {len(rates['woreda'])}. Stored {len(rows)} units: " + ", ".join(f"{k} {v}" for k, v in methods.items()))
        print(f"Estimated births per year (woredas): {total:,.0f}")
        if args.dry_run:
            s.rollback()
            print("Dry run: nothing saved.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
