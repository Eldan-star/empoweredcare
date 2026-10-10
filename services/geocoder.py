"""
Hierarchical geocoder: free-text place -> OCHA P-code (docs/SYSTEM_SPEC.md section 4).

    "Jimma zone, Seka Chekorsa woreda"  ->  ET040409 (woreda), confidence 1.0

Rules:
1. Split the text into parts ("Jimma zone", "Seka Chekorsa woreda"). In each part, words
   like zone/woreda/region and town/city are kept as hints, not as names; facility words
   (hospital, health post, camp, port, ...) are dropped; "surroundings"/"rural" mean the
   Zuria woreda around a town (Arba Minch surroundings -> Arba Minch Zuria).
2. Match each part exactly against unit names and aliases (OCHA's "Kersa (Jimma)" also
   answers to "Kersa"). If nothing matches exactly, fuzzy-match (rapidfuzz), restricted
   to the subtree of any unit already identified.
3. Use the hints: "zone" picks the zone over a same-named town, "town" the reverse. When
   one candidate sits inside another, a different kind of place (Jimma zone vs Jimma
   town) resolves to the outer one, which is true either way; the same place at two
   levels (Hawassa town Admin vs Hawassa town) resolves to the more precise one.
4. Parts must agree. Old names from before boundary changes (SNNPR; South Omo before
   Ari zone was carved out) count as agreeing with the units that replaced them. A part
   that contradicts the others is set aside and the result flagged.
5. If a name still fits more than one unit (repeated woreda names across regions),
   never guess: return the closest common ancestor, ambiguous=True, and the candidates.
"""

import csv
import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Optional

from rapidfuzz import fuzz, process

LEVEL_WORDS = {"region": 1, "regional": 1, "state": 1, "zone": 2, "zonal": 2,
               "woreda": 3, "wereda": 3, "district": 3, "kebele": 4}
TOWN_WORDS = {"town", "city"}
ZURIA_WORDS = {"zuria", "surroundings", "surrounding", "environs", "rural"}
NOISE_WORDS = {
    "hospital", "general", "referral", "primary", "health", "post", "center", "centre", "clinic",
    "camp", "camps", "displacement", "idp", "idps", "port", "plantation", "market", "school",
    "farm", "area", "near", "around", "the", "of", "and", "admin", "administration", "special",
    "sub", "urban", "unknown",
}
FUZZY_MIN_SCORE = 88  # 0–100; below this a fuzzy match is ignored
FUZZY_TIE_MARGIN = 3  # candidates within this many points of the best are treated as ties
HISTORICAL_FILE = Path(__file__).resolve().parent.parent / "data" / "historical_units.csv"


@dataclass
class Part:
    key: str                       # normalised name, e.g. "arba minch zuria"
    level: Optional[int] = None    # from zone/woreda/region words
    town: bool = False             # "town" or "city" was said


def _words(text: str) -> list[str]:
    text = unicodedata.normalize("NFKD", text).lower()
    text = "".join(c for c in text if not unicodedata.combining(c))
    return re.sub(r"[^\w\s]", " ", text).split()


def parse_part(text: str) -> Part:
    words = _words(text)
    level = next((LEVEL_WORDS[w] for w in words if w in LEVEL_WORDS), None)
    town = any(w in TOWN_WORDS for w in words)
    zuria = any(w in ZURIA_WORDS for w in words)
    kept = [w for w in words if w not in LEVEL_WORDS and w not in TOWN_WORDS
            and w not in ZURIA_WORDS and w not in NOISE_WORDS]
    if zuria and kept:
        kept.append("zuria")
    return Part(" ".join(kept), level, town)


def normalize(text: str) -> str:
    return parse_part(text).key


def split_parts(text: str) -> list[str]:
    return [p.key for p in _split(text)]


def _split(text: str) -> list[Part]:
    parts = [parse_part(p) for p in re.split(r"[,;/()\n]| - ", text or "")]
    return [p for p in parts if p.key]


@dataclass
class UnitInfo:
    pcode: str
    name: str
    level: int
    parent_pcode: Optional[str]
    aliases: list = field(default_factory=list)


@dataclass
class HistoricalUnit:
    """A unit that no longer exists, mapped to the current units that replaced it."""
    name: str
    level: int
    current: list


@dataclass
class GeocodeResult:
    pcode: Optional[str]
    name: Optional[str] = None
    level: Optional[int] = None
    confidence: float = 0.0
    ambiguous: bool = False
    candidates: list = field(default_factory=list)  # [{"pcode", "name", "path"}] when ambiguous
    method: str = "none"  # exact | fuzzy | conflict | none


def load_historical(path: Path = HISTORICAL_FILE) -> list[HistoricalUnit]:
    if not path.exists():
        return []
    with open(path, newline="", encoding="utf-8-sig") as f:
        return [HistoricalUnit(r["name"].strip(), int(r["level"]),
                               [p.strip() for p in r["current_pcodes"].split(";") if p.strip()])
                for r in csv.DictReader(f) if r.get("name")]


class Geocoder:
    def __init__(self, units: Iterable[UnitInfo], historical: Iterable[HistoricalUnit] = ()):
        self.units = {u.pcode: u for u in units}
        self.historical = {f"H:{h.name}": h for h in historical
                           if any(p in self.units for p in h.current)}
        self.by_name: dict[str, set[str]] = {}
        for u in self.units.values():
            for n in [u.name, *u.aliases]:
                self._index(n, u.pcode)
                if "(" in n:  # OCHA disambiguates repeated names: "Kersa (Jimma)", "Dera (AM)"
                    self._index(re.sub(r"\(.*?\)", " ", n), u.pcode)
        for hid, h in self.historical.items():
            self._index(h.name, hid)
        self._choices = list(self.by_name)

    def _index(self, name: str, uid: str):
        key = normalize(name)
        if key:
            self.by_name.setdefault(key, set()).add(uid)

    @classmethod
    def from_db(cls, session, historical_file: Path = HISTORICAL_FILE) -> "Geocoder":
        from sqlalchemy import select
        from db.models import OrgUnit
        rows = session.execute(select(OrgUnit.pcode, OrgUnit.name, OrgUnit.level, OrgUnit.parent_pcode,
                                      OrgUnit.aliases).where(OrgUnit.valid_to.is_(None)))
        return cls((UnitInfo(p, n, lv, par, al or []) for p, n, lv, par, al in rows),
                   load_historical(historical_file))

    # --- hierarchy helpers -------------------------------------------------------

    def is_town(self, uid: str) -> bool:
        return uid in self.units and any(w in TOWN_WORDS for w in _words(self.units[uid].name))

    def level(self, uid: str) -> int:
        return self.units[uid].level if uid in self.units else self.historical[uid].level

    def ancestors(self, pcode: str) -> list[str]:
        out, cur = [], self.units[pcode].parent_pcode
        while cur and cur in self.units:
            out.append(cur)
            cur = self.units[cur].parent_pcode
        return out

    def path(self, pcode: str) -> str:
        return " › ".join(self.units[p].name for p in [*reversed(self.ancestors(pcode)), pcode])

    def _lineage(self, a: str, b: str) -> bool:
        """Two current units on one line of descent (same, ancestor or descendant)."""
        return a == b or a in self.ancestors(b) or b in self.ancestors(a)

    def _agree(self, a: str, b: str) -> bool:
        """Could both names describe the same place? Historical units agree with the units
        that replaced them and with anything inside or above those."""
        if a in self.historical and b in self.historical:
            return any(self._agree(x, y) for x in self.historical[a].current for y in self.historical[b].current
                       if x in self.units and y in self.units)
        if a in self.historical:
            a, b = b, a
        if b in self.historical:
            return any(self._lineage(a, c) for c in self.historical[b].current if c in self.units)
        return self._lineage(a, b)

    def _common_ancestor(self, pcodes: set[str]) -> Optional[str]:
        chains = [[p, *self.ancestors(p)] for p in pcodes]
        shared = set(chains[0]).intersection(*chains[1:])
        return next((p for p in chains[0] if p in shared), None)

    # --- matching ----------------------------------------------------------------

    def _in_subtree(self, uid: str, within: set[str]) -> bool:
        if uid in self.historical:
            return any(self._in_subtree(c, within) for c in self.historical[uid].current if c in self.units)
        return uid in within or bool(within & set(self.ancestors(uid)))

    def _match_part(self, key: str, within: set[str]) -> tuple[set[str], str, float]:
        exact = self.by_name.get(key, set())
        if within:
            exact = {u for u in exact if self._in_subtree(u, within)} or exact
        if exact:
            return exact, "exact", 100.0
        choices = self._choices
        if within:
            choices = [n for n in self._choices if any(self._in_subtree(u, within) for u in self.by_name[n])]
        hits = [h for h in process.extract(key, choices, scorer=fuzz.token_sort_ratio, limit=5)
                if h[1] >= FUZZY_MIN_SCORE]
        if not hits:
            return set(), "none", 0.0
        best = hits[0][1]
        return set().union(*(self.by_name[h[0]] for h in hits if h[1] >= best - FUZZY_TIE_MARGIN)), "fuzzy", best

    def _apply_hints(self, cands: set[str], part: Part) -> set[str]:
        if part.level:
            at_level = {c for c in cands if self.level(c) == part.level}
            cands = at_level or cands
        real = {c for c in cands if c in self.units}
        if part.town:
            towns = {c for c in real if self.is_town(c)}
            cands = towns or cands
        elif part.level:
            # "Jimma zone": the zone, not the town that shares its name
            non_towns = {c for c in real if not self.is_town(c)}
            if non_towns and non_towns != real:
                cands = non_towns | (cands - real)
        # One candidate inside another: a different kind of place resolves to the outer
        # (true either way); the same kind (Hawassa town Admin / Hawassa town) to the inner.
        keep = set(cands)
        for a in real:
            for b in real:
                if a != b and a in self.ancestors(b) and a in keep and b in keep:
                    keep.discard(b if self.is_town(a) != self.is_town(b) else a)
        return keep

    def resolve(self, text: str, hints: Iterable[str] = ()) -> GeocodeResult:
        parts = _split(text) + [p for h in hints if h for p in _split(h)]
        if not parts or not self.units:
            return GeocodeResult(pcode=None)

        # First pass: unique exact matches anchor the hierarchy; second pass: fuzzy within it.
        first = [self._match_part(p.key, set()) for p in parts]
        anchors = {next(iter(m[0])) for m in first if m[1] == "exact" and len(m[0]) == 1
                   and next(iter(m[0])) in self.units}
        matched = []
        for p, m in zip(parts, first):
            if anchors and m[1] != "exact":
                m = self._match_part(p.key, anchors)
            if m[0]:
                matched.append((self._apply_hints(m[0], p), m[1], m[2]))
        if not matched:
            return GeocodeResult(pcode=None)

        # Set aside parts that contradict the others: repeatedly drop every part tied for
        # the most clashes. One dissenter among agreeing parts goes; two parts that only
        # contradict each other both go, since neither can be preferred.
        sets = [m[0] for m in matched]

        def compatible(a: set, b: set) -> bool:
            return any(self._agree(x, y) for x in a for y in b)

        alive = list(range(len(sets)))
        conflicts: set = set()
        while True:
            clashes = {i: sum(not compatible(sets[i], sets[j]) for j in alive if j != i) for i in alive}
            worst = max(clashes.values(), default=0)
            if worst == 0:
                break
            for i in [i for i, c in clashes.items() if c == worst]:
                conflicts |= sets[i]
                alive.remove(i)

        narrowed = []
        for i in alive:
            others = [sets[j] for j in alive if j != i]
            keep = {c for c in sets[i] if all(any(self._agree(c, o) for o in os) for os in others)}
            narrowed.append(keep or sets[i])  # pairwise-compatible parts can still fail jointly

        def candidates(uids):
            real = sorted(u for u in uids if u in self.units)
            return [{"pcode": p, "name": self.units[p].name, "path": self.path(p)} for p in real]

        used_history = any(u in self.historical for s in narrowed for u in s)
        real_sets = [{u for u in s if u in self.units} for s in narrowed]
        real_sets = [s for s in real_sets if s]

        if conflicts or not real_sets:
            # Only what the agreeing parts support; historical-only parts expand to their successors.
            if real_sets:
                best = max(real_sets, key=lambda s: max(self.units[p].level for p in s))
            else:
                best = {c for s in narrowed for u in s if u in self.historical
                        for c in self.historical[u].current if c in self.units}
            anchor = self._common_ancestor(best) if best else None
            u = self.units.get(anchor) if anchor else None
            flagged = conflicts or best
            return GeocodeResult(
                pcode=anchor, name=u.name if u else None, level=u.level if u else None,
                confidence=0.5 if u else 0.0, ambiguous=True,
                method="conflict" if conflicts else "exact", candidates=candidates(flagged),
            )

        deepest = max(real_sets, key=lambda s: max(self.units[p].level for p in s))
        top = max(self.units[p].level for p in deepest)
        final = {p for p in deepest if self.units[p].level == top}
        method = "fuzzy" if any(m[1] == "fuzzy" for m in matched) else "exact"
        score = min(m[2] for m in matched) / 100

        if len(final) == 1:
            p = final.pop()
            confirmed = len(alive) > 1 and not used_history  # another current unit agrees
            confidence = (1.0 if confirmed else 0.9) * (score if method == "fuzzy" else 1.0)
            u = self.units[p]
            return GeocodeResult(pcode=p, name=u.name, level=u.level, confidence=round(confidence, 2), method=method)

        common = self._common_ancestor(final)
        u = self.units.get(common) if common else None
        return GeocodeResult(
            pcode=common, name=u.name if u else None, level=u.level if u else None,
            confidence=0.5 if u else 0.0, ambiguous=True, method=method, candidates=candidates(final),
        )
