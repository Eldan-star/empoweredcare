"""DHIS2 connector against a fake server that answers in the DHIS2 Web API format."""

import json
from datetime import date

import httpx
import pytest

from connectors.dhis2 import (DHIS2Client, DHIS2Error, PullNotApproved, iso_weeks, match_org_units,
                              parse_period, to_indicator_counts)
from services.geocoder import Geocoder, UnitInfo

ORG_UNITS = {"organisationUnits": [
    {"id": "ETH00000001", "name": "Ethiopia", "level": 1},
    {"id": "ORO00000001", "name": "Oromia Region", "level": 2, "parent": {"id": "ETH00000001"}},
    {"id": "JIM00000001", "name": "Jimma Zone", "level": 3, "parent": {"id": "ORO00000001"}},
    {"id": "SEK00000001", "name": "Seka Chekorsa Woreda", "level": 4, "parent": {"id": "JIM00000001"}},
    {"id": "DER00000001", "name": "Dera", "level": 4, "parent": {"id": "JIM00000001"}},
]}
DATA_VALUES = {"dataValues": [
    {"dataElement": "MEASLES_SUS", "period": "2026W40", "orgUnit": "SEK00000001", "categoryOptionCombo": "lt5", "value": "4"},
    {"dataElement": "MEASLES_SUS", "period": "2026W40", "orgUnit": "SEK00000001", "categoryOptionCombo": "ge5", "value": "3"},
    {"dataElement": "MEASLES_IGM", "period": "2026W40", "orgUnit": "SEK00000001", "categoryOptionCombo": "x", "value": "2"},
    {"dataElement": "MEASLES_SUS", "period": "2026W41", "orgUnit": "SEK00000001", "categoryOptionCombo": "x", "value": "1"},
    {"dataElement": "OTHER", "period": "2026W40", "orgUnit": "SEK00000001", "categoryOptionCombo": "x", "value": "9"},
    {"dataElement": "MEASLES_SUS", "period": "2026W40", "orgUnit": "UNKNOWN0001", "categoryOptionCombo": "x", "value": "5"},
    {"dataElement": "MEASLES_SUS", "period": "202609", "orgUnit": "SEK00000001", "categoryOptionCombo": "x", "value": "5"},
]}


def fake_server(seen):
    def handler(request: httpx.Request):
        seen.append(request)
        if request.headers.get("Authorization") != "ApiToken good-token":
            return httpx.Response(401)
        if request.url.path.endswith("/api/system/info"):
            return httpx.Response(200, json={"version": "2.41.4"})
        if request.url.path.endswith("/api/organisationUnits"):
            return httpx.Response(200, json=ORG_UNITS)
        if request.url.path.endswith("/api/dataValueSets"):
            return httpx.Response(200, json=DATA_VALUES)
        return httpx.Response(404)
    return httpx.MockTransport(handler)


def client(url="https://play.im.dhis2.org/stable-2-41-4", token="good-token", approved=False, seen=None):
    return DHIS2Client(url=url, token=token, pull_approved=approved, transport=fake_server(seen if seen is not None else []))


def test_periods():
    assert parse_period("2026W40") == ("weekly", 2026, 40)
    assert parse_period("202609") == ("monthly", 2026, 9)
    with pytest.raises(ValueError):
        parse_period("2026Q3")
    # 2026-12-28 is in ISO week 53 of 2026; 2027-01-04 starts week 1 of 2027.
    assert iso_weeks(date(2026, 12, 24), date(2027, 1, 5)) == ["2026W52", "2026W53", "2027W1"]


def test_token_auth_and_metadata():
    seen = []
    c = client(seen=seen)
    assert c.is_demo and c.system_info()["version"] == "2.41.4"
    units = c.org_units(max_level=4)
    assert [u.uid for u in units][:2] == ["ETH00000001", "ORO00000001"]
    assert units[3].parent_uid == "JIM00000001"
    assert seen[-1].url.params["paging"] == "false"
    with pytest.raises(DHIS2Error, match="401"):
        client(token="wrong").system_info()


def test_real_servers_need_explicit_approval_for_data_but_not_metadata():
    ministry = client(url="https://dhis.moh.gov.et")
    assert not ministry.is_demo
    assert len(ministry.org_units()) == 5  # metadata is allowed
    with pytest.raises(PullNotApproved):
        ministry.data_values("PHEM_WEEKLY", ["2026W40"], "ETH00000001")
    assert client(url="https://dhis.moh.gov.et", approved=True).data_values("PHEM_WEEKLY", ["2026W40"], "ETH00000001")


def test_data_values_become_weekly_indicator_rows():
    seen = []
    values = client(seen=seen).data_values("PHEM_WEEKLY", ["2026W40", "2026W41"], "ETH00000001")
    assert seen[-1].url.params.get_list("period") == ["2026W40", "2026W41"]
    rows, skipped = to_indicator_counts(values, {"MEASLES_SUS": "suspected", "MEASLES_IGM": "confirmed"},
                                        {"SEK00000001": "ET040712"}, disease="measles")
    by_week = {r["iso_week"]: r for r in rows}
    assert by_week[40]["suspected"] == 7 and by_week[40]["confirmed"] == 2  # age groups summed
    assert by_week[41]["suspected"] == 1 and by_week[41]["confirmed"] is None
    assert skipped == {"unmapped_element": 1, "unmapped_org_unit": 1, "not_weekly": 1, "not_a_number": 0}


def test_matching_dhis2_units_to_pcodes():
    geo = Geocoder([
        UnitInfo("ET04", "Oromia", 1, None), UnitInfo("ET0407", "Jimma", 2, "ET04"),
        UnitInfo("ET040712", "Seka Chekorsa", 3, "ET0407"),
        UnitInfo("ET03", "Amhara", 1, None), UnitInfo("ET0302", "South Gondar", 2, "ET03"),
        UnitInfo("ET030201", "Dera", 3, "ET0302"),
    ])
    units = client().org_units(max_level=4)
    m = match_org_units(units, geo)
    assert m["matched"]["SEK00000001"] == "ET040712"
    assert m["matched"]["ORO00000001"] == "ET04" and m["matched"]["JIM00000001"] == "ET0407"
    # DHIS2 says this "Dera" is in Jimma; ours is in South Gondar: not linked automatically.
    assert "DER00000001" not in m["matched"]
    assert "ETH00000001" not in m["matched"] and "ETH00000001" not in m["unmatched"]


def test_unreachable_server_gives_a_plain_message():
    def down(request):
        raise httpx.ConnectError("connection refused")
    c = DHIS2Client(url="https://dhis.example.org", token="t", transport=httpx.MockTransport(down))
    with pytest.raises(DHIS2Error, match="Could not reach DHIS2"):
        c.system_info()
