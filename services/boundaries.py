"""
Read OCHA administrative boundaries (COD-AB) and turn them into org_units rows plus
an adjacency table.

Accepted inputs: a zipped shapefile (as downloaded from HDX), a .shp file, or a
GeoJSON file, one per admin level. Column names are matched case-insensitively and
cover both COD-AB styles: ADM2_PCODE / ADM2_EN and adm2_pcode / adm2_name.
"""

import io
import json
import math
import zipfile
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Iterable, Optional

from shapely.geometry import shape
from shapely.geometry.base import BaseGeometry
from shapely.strtree import STRtree

LEVEL_NAMES = {1: "region", 2: "zone", 3: "woreda", 4: "kebele"}
KM_PER_DEG_LAT = 110.57
KM_PER_DEG_LON_AT_EQUATOR = 111.32


@dataclass
class Unit:
    pcode: str
    name: str
    level: int
    parent_pcode: Optional[str]
    geometry: BaseGeometry
    aliases: list = field(default_factory=list)
    valid_from: Optional[date] = None


def _features_from_shapefile(path: Path) -> Iterable[tuple[dict, dict]]:
    import shapefile  # pyshp

    if path.suffix.lower() == ".zip":
        with zipfile.ZipFile(path) as z:
            shp = [n for n in z.namelist() if n.lower().endswith(".shp")]
            if len(shp) != 1:
                raise ValueError(f"{path.name}: expected one .shp inside the zip, found {shp or 'none'}")
            stem = shp[0][:-4]
            parts = {ext: io.BytesIO(z.read(stem + ext)) for ext in (".shp", ".shx", ".dbf")
                     if stem + ext in z.namelist()}
            reader = shapefile.Reader(shp=parts[".shp"], shx=parts.get(".shx"), dbf=parts[".dbf"],
                                      encoding="utf-8", encodingErrors="replace")
    else:
        reader = shapefile.Reader(str(path), encoding="utf-8", encodingErrors="replace")
    for sr in reader.shapeRecords():
        yield sr.record.as_dict(), sr.shape.__geo_interface__


def _features_from_geojson(path: Path) -> Iterable[tuple[dict, dict]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    for f in data.get("features", []):
        yield f.get("properties") or {}, f["geometry"]


def read_features(path: Path) -> list[tuple[dict, BaseGeometry]]:
    path = Path(path)
    suffix = path.suffix.lower()
    if suffix in (".zip", ".shp"):
        raw = _features_from_shapefile(path)
    elif suffix in (".geojson", ".json"):
        raw = _features_from_geojson(path)
    else:
        raise ValueError(f"{path.name}: use a zipped shapefile, a .shp or a GeoJSON file")
    out = []
    for props, geom in raw:
        g = shape(geom)
        if not g.is_valid:
            g = g.buffer(0)  # repairs self-intersections common in admin boundary files
        out.append((props, g))
    return out


def _pick(props: dict, *candidates: str) -> Optional[str]:
    lower = {k.lower(): v for k, v in props.items()}
    for c in candidates:
        v = lower.get(c.lower())
        if v not in (None, ""):
            return str(v).strip()
    return None


def _parse_date(value) -> Optional[date]:
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def units_from_features(features: list[tuple[dict, BaseGeometry]], level: int) -> list[Unit]:
    units = []
    for props, geom in features:
        pcode = _pick(props, f"ADM{level}_PCODE", f"adm{level}_pcode")
        name = _pick(props, f"ADM{level}_EN", f"adm{level}_name", f"ADM{level}_NAME", f"adm{level}_name_en")
        if not pcode or not name:
            raise ValueError(
                f"Level {level}: a feature has no ADM{level}_PCODE / ADM{level}_EN column "
                f"(columns found: {sorted(props)})"
            )
        parent = _pick(props, f"ADM{level - 1}_PCODE", f"adm{level - 1}_pcode") if level > 1 else None
        aliases = [a for a in (
            _pick(props, f"ADM{level}_REF", f"adm{level}_ref"),
            _pick(props, f"ADM{level}ALT1EN", f"adm{level}_alt1en"),
            _pick(props, f"ADM{level}ALT2EN", f"adm{level}_alt2en"),
            _pick(props, f"ADM{level}_AM", f"adm{level}_name1"),  # Amharic names where provided
        ) if a and a != name]
        units.append(Unit(pcode=pcode, name=name, level=level, parent_pcode=parent, geometry=geom,
                          aliases=sorted(set(aliases)),
                          valid_from=_parse_date(_pick(props, "validOn", "valid_on", "date"))))
    return units


def _km_xy(geom: BaseGeometry, lat0: float) -> BaseGeometry:
    """Degrees -> approximate kilometres around latitude lat0 (equirectangular). Ethiopia
    spans about 3–15°N, so this is accurate to a few percent for border lengths."""
    from shapely.ops import transform
    kx = KM_PER_DEG_LON_AT_EQUATOR * math.cos(math.radians(lat0))
    return transform(lambda x, y, z=None: (x * kx, y * KM_PER_DEG_LAT), geom)


def haversine_km(lat1, lon1, lat2, lon2) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def adjacency(units: list[Unit], min_border_km: float = 0.1) -> list[tuple[str, str, float, float]]:
    """(a_pcode, b_pcode, shared_border_km, centroid_distance_km) for units at the same
    level whose borders touch along more than `min_border_km` (corner contacts excluded)."""
    if not units:
        return []
    geoms = [u.geometry for u in units]
    tree = STRtree(geoms)
    pairs = []
    for i, u in enumerate(units):
        for j in tree.query(u.geometry):
            j = int(j)
            if j <= i:
                continue
            v = units[j]
            if not u.geometry.intersects(v.geometry):
                continue
            border = u.geometry.boundary.intersection(v.geometry.boundary)
            lat0 = (u.geometry.centroid.y + v.geometry.centroid.y) / 2
            length = _km_xy(border, lat0).length if not border.is_empty else 0.0
            if length < min_border_km:
                continue
            cu, cv = u.geometry.representative_point(), v.geometry.representative_point()
            a, b = sorted((u.pcode, v.pcode))
            pairs.append((a, b, round(length, 2), round(haversine_km(cu.y, cu.x, cv.y, cv.x), 2)))
    return pairs
