import pytest

from services.geocoder import Geocoder, UnitInfo, normalize, split_parts

# A small made-up hierarchy that reproduces real difficulties: a woreda name used in two
# regions ("Dera" exists in both Amhara and Oromia), a zone and a town with the same
# name, and an Amharic alias.
from services.geocoder import HistoricalUnit

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


def test_zone_word_picks_the_zone_over_a_town_with_the_same_name(geo):
    r = geo.resolve("Jimma zone")
    assert (r.pcode, r.ambiguous) == ("ET0407", False)
    assert geo.resolve("Jimma town").pcode == "ET0499"


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


# --- rules added after testing on the real OCHA boundaries ---------------------------

MORE = UNITS + [
    UnitInfo("ET08", "South Ethiopia", 1, None),
    UnitInfo("ET0802", "Gamo", 2, "ET08"),
    UnitInfo("ET080201", "Arba Minch town", 3, "ET0802"),
    UnitInfo("ET080202", "Arba Minch Zuria", 3, "ET0802"),
    UnitInfo("ET0805", "Ari", 2, "ET08"),
    UnitInfo("ET080506", "Jinka town", 3, "ET0805"),
    UnitInfo("ET0812", "South Omo", 2, "ET08"),
    UnitInfo("ET081207", "Turmi town", 3, "ET0812"),
    UnitInfo("ET0809", "Konso", 2, "ET08"),
    UnitInfo("ET16", "Sidama", 1, None),
    UnitInfo("ET1601", "Hawassa town Admin", 2, "ET16"),
    UnitInfo("ET160101", "Hawassa town", 3, "ET1601", ["Awassa"]),
    UnitInfo("ET041099", "Kersa (North Shewa)", 3, "ET0410"),
]
HISTORY = [HistoricalUnit("South Omo", 2, ["ET0812", "ET0805"]),
           HistoricalUnit("SNNPR", 1, ["ET08", "ET16"])]


@pytest.fixture(scope="module")
def geo2():
    return Geocoder(MORE, HISTORY)


def test_surroundings_means_the_zuria_woreda(geo2):
    assert geo2.resolve("Arba Minch Surroundings").pcode == "ET080202"
    assert geo2.resolve("Arba Minch, Banana plantation").pcode == "ET080201"


def test_facility_words_are_ignored(geo2):
    assert geo2.resolve("Konso Health Post").pcode == "ET0809"


def test_ocha_suffixes_answer_to_the_plain_name(geo2):
    # "Kersa" (Jimma) and "Kersa (North Shewa)": the suffix makes the second findable too.
    r = geo2.resolve("Kersa woreda")
    assert r.ambiguous and {c["pcode"] for c in r.candidates} == {"ET040713", "ET041099"}
    assert geo2.resolve("Kersa, North Shewa").pcode == "ET041099"
    assert geo2.resolve("Kersa, Jimma zone").pcode == "ET040713"


def test_same_place_at_two_levels_resolves_to_the_precise_one(geo2):
    assert geo2.resolve("Hawassa").pcode == "ET160101"
    assert geo2.resolve("Awassa").pcode == "ET160101"


def test_old_zone_names_still_agree_with_their_successors(geo2):
    # Jinka moved from South Omo to the new Ari zone in 2023; reports still say South Omo.
    r = geo2.resolve("Jinka, South Omo Zone")
    assert (r.pcode, r.ambiguous) == ("ET080506", False)
    assert r.confidence == 0.9  # agreement through an old name is not full confirmation
    assert geo2.resolve("Turmi, South Omo region").pcode == "ET081207"
    assert geo2.resolve("Hawassa, SNNPR").pcode == "ET160101"


def test_an_old_region_alone_is_never_resolved_to_one_successor(geo2):
    r = geo2.resolve("SNNPR")
    assert r.ambiguous and r.pcode is None
    assert {c["pcode"] for c in r.candidates} == {"ET08", "ET16"}
