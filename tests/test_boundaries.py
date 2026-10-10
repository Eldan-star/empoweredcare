import importlib.util
import json
import zipfile
from pathlib import Path

import shapefile
from sqlalchemy import select

from db.models import OrgUnit, OrgUnitAdjacency, Signal
from services.boundaries import adjacency, read_features, units_from_features
from services.geocoder import Geocoder
from services.signal_store import SignalStore
from models.schemas import OutbreakReport, RiskAnalysis

ROOT = Path(__file__).resolve().parent.parent


def load_script(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def square(x, y, size=0.5):
    return [[x, y], [x, y + size], [x + size, y + size], [x + size, y], [x, y]]


def write_geojson(path, features):
    path.write_text(json.dumps({"type": "FeatureCollection", "features": [
        {"type": "Feature", "properties": props, "geometry": {"type": "Polygon", "coordinates": [ring]}}
        for props, ring in features]}), encoding="utf-8")
    return path


def write_shapefile_zip(path, level, rows):
    """A zipped shapefile like the ones HDX serves, with COD-AB column names."""
    stem = path.with_suffix("")
    w = shapefile.Writer(str(stem))
    w.field(f"ADM{level}_PCODE", "C")
    w.field(f"ADM{level}_EN", "C")
    if level > 1:
        w.field(f"ADM{level - 1}_PCODE", "C")
    for props, ring in rows:
        w.poly([ring])
        w.record(*props)
    w.close()
    with zipfile.ZipFile(path, "w") as z:
        for ext in (".shp", ".shx", ".dbf"):
            z.write(str(stem) + ext, f"eth_adm{level}{ext}")
    return path


def make_files(tmp_path):
    # Region 1 x 1 degree near Jimma; one zone covering it; three woredas: A and B share
    # an edge, C touches B only at a corner (not neighbours).
    adm1 = write_shapefile_zip(tmp_path / "adm1.zip", 1, [(("ET04", "Oromia"), square(36.0, 7.0, 1.0))])
    adm2 = write_geojson(tmp_path / "adm2.geojson", [
        ({"adm2_pcode": "ET0407", "adm2_name": "Jimma", "adm1_pcode": "ET04", "valid_on": "2021-01-01"},
         square(36.0, 7.0, 1.0))])
    adm3 = write_shapefile_zip(tmp_path / "adm3.zip", 3, [
        (("ET040701", "Woreda A", "ET0407"), square(36.0, 7.0)),
        (("ET040702", "Woreda B", "ET0407"), square(36.5, 7.0)),
        (("ET040703", "Woreda C", "ET0407"), square(36.0, 7.5)),  # shares an edge with A only
        (("ET040799", "Orphan", "ET9999"), square(36.5, 7.5)),     # parent not loaded
    ])
    pop = tmp_path / "pop.csv"
    pop.write_text("ADM1_PCODE,ADM3_PCODE,ADM3_EN,T_TL\nET04,ET040701,Woreda A,\"120,500\"\nET04,ET040702,Woreda B,98000\n",
                   encoding="utf-8")
    return adm1, adm2, adm3, pop


def test_reading_both_column_styles(tmp_path):
    adm1, adm2, adm3, _ = make_files(tmp_path)
    u2 = units_from_features(read_features(adm2), 2)[0]
    assert (u2.pcode, u2.name, u2.parent_pcode, str(u2.valid_from)) == ("ET0407", "Jimma", "ET04", "2021-01-01")
    u3 = units_from_features(read_features(adm3), 3)
    assert [u.pcode for u in u3][:2] == ["ET040701", "ET040702"]


def test_adjacency_counts_shared_edges_not_corners(tmp_path):
    _, _, adm3, _ = make_files(tmp_path)
    units = units_from_features(read_features(adm3), 3)
    pairs = {(a, b): (km, d) for a, b, km, d in adjacency(units)}
    assert ("ET040701", "ET040702") in pairs and ("ET040701", "ET040703") in pairs
    assert ("ET040702", "ET040703") not in pairs  # corner contact only
    km, dist = pairs[("ET040701", "ET040702")]
    assert 50 < km < 60      # half a degree of latitude ≈ 55 km
    assert 50 < dist < 60    # centres half a degree of longitude apart at 7°N ≈ 55 km


def test_loading_into_the_database_and_geocoding_a_report(tmp_path, db, engine):
    adm1, adm2, adm3, pop = make_files(tmp_path)
    loader = load_script("load_boundaries")
    population = loader.read_population(pop)
    assert population == {"ET040701": 120500, "ET040702": 98000}

    summary = loader.load(db, {1: adm1, 2: adm2, 3: adm3}, population, "test")
    db.commit()
    assert summary["units"] == {"region": 1, "zone": 1, "woreda": 4}
    assert len(summary["orphans"]) == 1 and summary["population_matched"] == 2
    a = db.get(OrgUnit, "ET040701")
    assert a.parent.name == "Jimma" and a.population == 120500 and 7.0 < a.lat < 7.5
    assert db.get(OrgUnit, "ET040799") is None
    assert len(db.scalars(select(OrgUnitAdjacency)).all()) == 2

    # Loading again updates in place rather than duplicating.
    loader.load(db, {1: adm1, 2: adm2, 3: adm3}, {}, "test")
    db.commit()
    assert len(db.scalars(select(OrgUnit)).all()) == 5

    from sqlalchemy.orm import sessionmaker
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as s:
        store = SignalStore(factory, Geocoder.from_db(s))
    rec = store.add(OutbreakReport(location="Jimma zone, Woreda B", cases=5),
                    risk_analysis=RiskAnalysis(risk_level="HIGH", confidence="80%", possible_disease="Measles", reason="r"))
    assert rec["pcode"] == "ET040702" and rec["geocode_confidence"] == 1.0
    unresolved = store.add(OutbreakReport(location="Somewhere else", cases=1))
    assert unresolved["pcode"] is None
    assert store.regeocode() == {"resolved": 0, "ambiguous": 0, "unmatched": 1}


def test_all_levels_zip_and_excel_population(tmp_path, db):
    """The files as HDX serves them today: one zip with every level, and the 2026 COD-PS
    workbook whose sheet uses admin3_pcod / Total and carries a grand-total row."""
    import pandas as pd
    from services.boundaries import shapefile_levels_in_zip
    adm1, _, adm3, _ = make_files(tmp_path)
    combined = tmp_path / "eth_admin_boundaries.shp.zip"
    with zipfile.ZipFile(combined, "w") as out:
        for src, level in ((adm1, 1), (adm3, 3)):
            with zipfile.ZipFile(src) as z:
                for n in z.namelist():
                    out.writestr(n.replace(f"eth_adm{level}", f"eth_admin{level}"), z.read(n))
        out.writestr("eth_adminlines.shp", b"")  # other layers must be ignored
    levels = shapefile_levels_in_zip(combined)
    assert levels == {1: "eth_admin1", 3: "eth_admin3"}

    book = tmp_path / "table_eth_codps_2026.xlsx"
    with pd.ExcelWriter(book) as w:
        pd.DataFrame({"note": ["read me"]}).to_excel(w, sheet_name="READ ME", index=False)
        pd.DataFrame({"admin3Name": ["Woreda A", "Woreda B", None], "admin3_pcod": ["ET040701", "ET040702", None],
                      "Total": [120500, 98000, 218500]}).to_excel(w, sheet_name="COD_PS", index=False)
    loader = load_script("load_boundaries")
    assert loader.read_population(book) == {"ET040701": 120500, "ET040702": 98000}

    aliases = tmp_path / "aliases.csv"
    aliases.write_text("pcode,alias,note\nET040701,Woreda Alpha,old name\n", encoding="utf-8")
    zone = write_geojson(tmp_path / "z.geojson", [({"adm2_pcode": "ET0407", "adm2_name": "Jimma", "adm1_pcode": "ET04"},
                                                   square(36.0, 7.0, 1.0))])
    loader.load(db, {1: (combined, levels[1]), 2: zone, 3: (combined, levels[3])},
                loader.read_population(book), "test", loader.read_aliases(aliases))
    db.commit()
    assert "Woreda Alpha" in db.get(OrgUnit, "ET040701").aliases
    assert db.get(OrgUnit, "ET040702").population == 98000
