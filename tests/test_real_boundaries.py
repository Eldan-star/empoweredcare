"""
Regression test on the real OCHA boundaries. Opt-in, because the file is not in git:

    set OCHA_BOUNDARIES_ZIP=data/boundaries/eth_admin_boundaries.shp.zip
    python -m pytest tests/test_real_boundaries.py -q
"""

import os
from pathlib import Path

import pytest

from services.boundaries import read_features, shapefile_levels_in_zip, units_from_features
from services.geocoder import Geocoder, UnitInfo, load_historical

ZIP = os.getenv("OCHA_BOUNDARIES_ZIP")
pytestmark = pytest.mark.skipif(not ZIP or not Path(ZIP).exists(), reason="set OCHA_BOUNDARIES_ZIP to run")

ROOT = Path(__file__).resolve().parent.parent

# The place names in the project's own reports, and what a person would answer.
EXPECTED = {
    "Jimma zone": "ET0404",                       # the zone, not Jimma town
    "Jinka, South Omo Zone": "ET080506",          # Jinka town, now in Ari zone
    "Turmi, South Omo region": "ET081207",
    "Arba Minch Surroundings": "ET080202",        # Arba Minch Zuria
    "Hawassa": "ET160101",
    "Bahir Dar, Lake Tana area": "ET031401",
    "Haramaya General Hospital": "ET041006",      # OCHA: Haro Maya (alias file)
    "Jijiga region, displacement camp": "ET050293",
    "Konso Health Post": "ET0809",
    "Addis Ababa, Mercato area": "ET14",
}


@pytest.fixture(scope="module")
def geo():
    import csv
    aliases = {}
    with open(ROOT / "data" / "place_aliases.csv", newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            aliases.setdefault(r["pcode"], []).append(r["alias"])
    units = []
    for level, stem in shapefile_levels_in_zip(Path(ZIP)).items():
        if level in (1, 2, 3):
            for u in units_from_features(read_features(Path(ZIP), stem), level):
                units.append(UnitInfo(u.pcode, u.name, level, u.parent_pcode, u.aliases + aliases.get(u.pcode, [])))
    return Geocoder(units, load_historical())


@pytest.mark.parametrize("text,pcode", EXPECTED.items())
def test_report_places(geo, text, pcode):
    r = geo.resolve(text)
    assert (r.pcode, r.ambiguous) == (pcode, False), r


def test_repeated_woreda_names_are_flagged(geo):
    r = geo.resolve("Dera woreda")
    assert r.ambiguous and len(r.candidates) >= 2
    assert geo.resolve("Semera Port").pcode is None  # not an OCHA unit: no match, no guess
