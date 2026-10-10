"""
Hierarchical geocoder: free-text place -> OCHA P-code (docs/SYSTEM_SPEC.md section 4).

    "Jimma zone, Seka Chekorsa woreda"  ->  ET040712 (woreda), confidence 1.0

Rules:
1. Split the text into parts ("Jimma zone", "Seka Chekorsa woreda") and drop generic
   words (zone, woreda, town, region, ...).
2. Match each part exactly against unit names and aliases. If nothing matches exactly,
   fuzzy-match (rapidfuzz), restricted to the subtree of any unit already identified.
3. Keep the deepest match whose ancestors agree with the other parts and any hints.
4. If a name still fits more than one unit (Ethiopia has repeated woreda names across
   regions), never guess: return the closest common ancestor, ambiguous=True, and the
   candidates for a person to choose from.
"""

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Iterable, Optional

from rapidfuzz import fuzz, process

GENERIC_WORDS = {
    "zone", "zonal", "woreda", "wereda", "district", "region", "regional", "state", "kebele",
    "town", "city", "administration", "admin", "special", "sub", "city", "area", "surroundings",
    "surrounding", "near", "around", "the", "of", "rural", "urban", "and",
}
FUZZY_MIN_SCORE = 88  # 0–100; below this a fuzzy match is ignored
FUZZY_TIE_MARGIN = 3  # candidates within this many points of the best are treated as ties


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).lower()
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = re.sub(r"[^\w\s]", " ", text)
    words = [w for w in text.split() if w not in GENERIC_WORDS]
    return " ".join(words)


def split_parts(text: str) -> list[str]:
    parts = [normalize(p) for p in re.split(r"[,;/()\n]| - ", text or "")]
    return [p for p in parts if p]


@dataclass
class UnitInfo:
    pcode: str
    name: str
    level: int
    parent_pcode: Optional[str]
    aliases: list = field(default_factory=list)


@dataclass
class GeocodeResult:
    pcode: Optional[str]
    name: Optional[str] = None
    level: Optional[int] = None
    confidence: float = 0.0
    ambiguous: bool = False
    candidates: list = field(default_factory=list)  # [{"pcode", "name", "path"}] when ambiguous
    method: str = "none"  # exact | fuzzy | conflict | none


class Geocoder:
    def __init__(self, units: Iterable[UnitInfo]):
        self.units = {u.pcode: u for u in units}
        self.by_name: dict[str, set[str]] = {}
        for u in self.units.values():
            for n in [u.name, *u.aliases]:
                key = normalize(n)
                if key:
                    self.by_name.setdefault(key, set()).add(u.pcode)
        self._choices = list(self.by_name)

    @classmethod
    def from_db(cls, session) -> "Geocoder":
        from sqlalchemy import select
        from db.models import OrgUnit
        rows = session.execute(select(OrgUnit.pcode, OrgUnit.name, OrgUnit.level, OrgUnit.parent_pcode,
                                      OrgUnit.aliases).where(OrgUnit.valid_to.is_(None)))
        return cls(UnitInfo(p, n, lv, par, al or []) for p, n, lv, par, al in rows)

    # --- hierarchy helpers -------------------------------------------------------

    def ancestors(self, pcode: str) -> list[str]:
        out, cur = [], self.units[pcode].parent_pcode
        while cur and cur in self.units:
            out.append(cur)
            cur = self.units[cur].parent_pcode
        return out

    def path(self, pcode: str) -> str:
        return " › ".join(self.units[p].name for p in [*reversed(self.ancestors(pcode)), pcode])

    def _consistent(self, pcode: str, others: set[str]) -> bool:
        """Every other identified unit is this unit, its ancestor, or its descendant."""
        lineage = {pcode, *self.ancestors(pcode)}
        return all(o in lineage or pcode in self.ancestors(o) for o in others)

    def _common_ancestor(self, pcodes: set[str]) -> Optional[str]:
        chains = [[p, *self.ancestors(p)] for p in pcodes]
        shared = set(chains[0]).intersection(*chains[1:])
        return next((p for p in chains[0] if p in shared), None)

    # --- matching ----------------------------------------------------------------

    def _match_part(self, part: str, within: set[str]) -> tuple[set[str], str, float]:
        exact = self.by_name.get(part, set())
        if within:
            exact = {p for p in exact if p in within or within & set(self.ancestors(p))} or exact
        if exact:
            return exact, "exact", 100.0
        choices = self._choices
        if within:
            choices = [n for n in self._choices
                       if any(p in within or within & set(self.ancestors(p)) for p in self.by_name[n])]
        hits = process.extract(part, choices, scorer=fuzz.token_sort_ratio, limit=5)
        hits = [h for h in hits if h[1] >= FUZZY_MIN_SCORE]
        if not hits:
            return set(), "none", 0.0
        best = hits[0][1]
        names = [h[0] for h in hits if h[1] >= best - FUZZY_TIE_MARGIN]
        return set().union(*(self.by_name[n] for n in names)), "fuzzy", best

    def resolve(self, text: str, hints: Iterable[str] = ()) -> GeocodeResult:
        parts = split_parts(text) + [normalize(h) for h in hints if h and normalize(h)]
        if not parts or not self.units:
            return GeocodeResult(pcode=None)

        # First pass: exact matches anchor the hierarchy; second pass: fuzzy within it.
        matched: list[tuple[set[str], str, float]] = []
        anchors: set[str] = set()
        for part in parts:
            m = self._match_part(part, set())
            matched.append(m)
            if m[1] == "exact" and len(m[0]) == 1:
                anchors |= m[0]
        if anchors:
            matched = [self._match_part(part, anchors) if m[1] != "exact" else m for part, m in zip(parts, matched)]
        matched = [m for m in matched if m[0]]
        if not matched:
            return GeocodeResult(pcode=None)

        # Parts that contradict the others (e.g. "Dera" given with parents in another
        # region) are set aside and the result is flagged, never trusted. Repeatedly drop
        # every part tied for the most clashes: one dissenter among agreeing parts goes;
        # two parts that only contradict each other both go, since neither can be preferred.
        sets = [m[0] for m in matched]

        def compatible(a: set, b: set) -> bool:
            return any(self._consistent(x, {y}) for x in a for y in b)

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
            keep = {c for c in sets[i] if all(any(self._consistent(c, {o}) for o in os) for os in others)}
            narrowed.append(keep or sets[i])  # pairwise-compatible parts can still fail jointly
        if conflicts:
            agreed = [n for n in narrowed if n]
            best = max(agreed, key=lambda s: max(self.units[p].level for p in s)) if agreed else set()
            anchor = self._common_ancestor(best) if best else None
            u = self.units.get(anchor) if anchor else None
            return GeocodeResult(
                pcode=anchor, name=u.name if u else None, level=u.level if u else None,
                confidence=0.5 if u else 0.0, ambiguous=True, method="conflict",
                candidates=[{"pcode": p, "name": self.units[p].name, "path": self.path(p)} for p in sorted(conflicts)],
            )

        # The answer is the deepest level reached by any part.
        deepest = max(narrowed, key=lambda s: max(self.units[p].level for p in s))
        top = max(self.units[p].level for p in deepest)
        final = {p for p in deepest if self.units[p].level == top}
        method = "fuzzy" if any(m[1] == "fuzzy" for m in matched) else "exact"
        score = min(m[2] for m in matched) / 100

        if len(final) == 1:
            p = final.pop()
            confirmed = len(matched) > 1  # another part (e.g. the zone) agrees with it
            confidence = (1.0 if confirmed else 0.9) * (score if method == "fuzzy" else 1.0)
            u = self.units[p]
            return GeocodeResult(pcode=p, name=u.name, level=u.level, confidence=round(confidence, 2), method=method)

        common = self._common_ancestor(final)
        u = self.units.get(common) if common else None
        return GeocodeResult(
            pcode=common, name=u.name if u else None, level=u.level if u else None,
            confidence=0.5 if u else 0.0, ambiguous=True, method=method,
            candidates=[{"pcode": p, "name": self.units[p].name, "path": self.path(p)} for p in sorted(final)],
        )
