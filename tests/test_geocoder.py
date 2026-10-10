import pytest

from services.geocoder import Geocoder, UnitInfo, normalize, split_parts

# A small made-up hierarchy that reproduces real difficulties: a woreda name used in two
# regions ("Dera" exists in both Amhara and Oromia), a zone and a town with the same
# name, and an Amharic alias.
UNITS = [
    UnitInfo("ET03", "Amhara", 1, None),
    UnitInfo("ET04", "Oromia", 1, None),
    UnitInfo("ET0302", "South Gondar", 2, "ET03"),
    UnitInfo("ET0407", "Jimma", 2, "ET04"),
    UnitInfo("ET0410", "North Shewa", 2, "ET04"),
    UnitInfo("ET0499", "Jimma Town", 2, "ET04"),
    UnitInfo("ET030201", "Dera", 3, "ET0302"),
    UnitInfo("ET041001", "Dera", 3, "ET0410"),
    UnitInfo("ET040712", "Seka Chekorsa", 3, "ET0407", ["Sekoru Chekorsa", "ሰቃ ጨቆርሳ"]),
    UnitInfo("ET040713", "Kersa", 3, "ET0407"),
]


@pytest.fixture(scope="module")
def geo():
    return Geocoder(UNITS)


def test_normalize_and_split():
    assert normalize("Jimma Zone") == "jimma"
    assert normalize("Séka-Chekorsa woreda") == "seka chekorsa"
    assert split_parts("Jimma zone, Seka Chekorsa woreda") == ["jimma", "seka chekorsa"]


def test_zone_plus_woreda_resolves_to_the_woreda_with_full_confidence(geo):
    r = geo.resolve("Jimma zone, Seka Chekorsa woreda")
    assert (r.pcode, r.level, r.ambiguous, r.method) == ("ET040712", 3, False, "exact")
    assert r.confidence == 1.0


def test_unique_woreda_alone_resolves_with_slightly_lower_confidence(geo):
    r = geo.resolve("Seka Chekorsa")
    assert r.pcode == "ET040712" and r.confidence == 0.9


def test_aliases_including_amharic(geo):
    assert geo.resolve("ሰቃ ጨቆርሳ").pcode == "ET040712"
    assert geo.resolve("Sekoru Chekorsa woreda").pcode == "ET040712"


def test_duplicate_woreda_name_is_never_guessed(geo):
    r = geo.resolve("Dera woreda")
    assert r.ambiguous is True
    assert {c["pcode"] for c in r.candidates} == {"ET030201", "ET041001"}
    assert r.pcode is None  # Amhara and Oromia share no ancestor in this hierarchy
    assert any("South Gondar" in c["path"] for c in r.candidates)


def test_parent_resolves_a_duplicate_name(geo):
    r = geo.resolve("Dera, North Shewa")
    assert (r.pcode, r.ambiguous) == ("ET041001", False)
    assert geo.resolve("Dera woreda", hints=["Amhara"]).pcode == "ET030201"


def test_misspelling_is_matched_within_the_known_zone(geo):
    r = geo.resolve("Jimma zone, Seka Chekorssa")
    assert (r.pcode, r.method) == ("ET040712", "fuzzy")
    assert 0.85 <= r.confidence < 1.0


def test_unknown_place_returns_nothing(geo):
    r = geo.resolve("Haramaya General Hospital")
    assert r.pcode is None and not r.ambiguous and r.confidence == 0.0
    assert geo.resolve("").pcode is None


def test_zone_only(geo):
    r = geo.resolve("Jimma zone")
    # "Jimma" (zone) and "Jimma Town" both normalise to "jimma": two zone-level units.
    assert r.ambiguous and {c["pcode"] for c in r.candidates} == {"ET0407", "ET0499"}
    assert r.pcode == "ET04"  # but both are in Oromia, so the region is certain


def test_parents_that_contradict_the_place_are_flagged_not_trusted(geo):
    # The only "Seka Chekorsa" is in Jimma (Oromia); the text claims South Gondar.
    # Two parts disagree and nothing says which is right: no code, both candidates.
    r = geo.resolve("Seka Chekorsa, South Gondar")
    assert (r.pcode, r.ambiguous, r.method) == (None, True, "conflict")
    assert {c["pcode"] for c in r.candidates} == {"ET040712", "ET0302"}
    # When two parts agree (South Gondar is in Amhara) against one, keep what they support
    # and list the odd one out for a person to check.
    r = geo.resolve("Seka Chekorsa, South Gondar, Amhara")
    assert (r.pcode, r.ambiguous) == ("ET0302", True)
    assert [c["pcode"] for c in r.candidates] == ["ET040712"]
