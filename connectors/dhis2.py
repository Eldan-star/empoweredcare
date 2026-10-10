"""
DHIS2 Web API client: organisation units (metadata) and aggregate data values
(PHEM weekly, EPI monthly), mapped onto our tables.

Settings (.env):
    DHIS2_URL            e.g. https://play.im.dhis2.org/stable-2-41-4  (the public demo)
    DHIS2_TOKEN          personal access token (preferred), or
    DHIS2_USERNAME / DHIS2_PASSWORD
    DHIS2_PULL_APPROVED  must be "true" to pull data values from any server other than
                         the public demo. Ethiopian data is pulled only after EPHI
                         approves it in writing.

Data-element mapping (which DHIS2 data element is measles suspected cases, etc.) is
configuration, given to `to_indicator_counts`, because it differs between instances.
"""

import os
import re
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Iterable, Optional
from urllib.parse import urlparse

import httpx

DEMO_HOSTS = re.compile(r"(^|\.)play(\.im)?\.dhis2\.org$")


class DHIS2Error(RuntimeError):
    pass


class PullNotApproved(DHIS2Error):
    """Data pulls from a real (non-demo) DHIS2 need DHIS2_PULL_APPROVED=true."""


def weekly_period(year: int, week: int) -> str:
    return f"{year}W{week}"


def monthly_period(year: int, month: int) -> str:
    return f"{year}{month:02d}"


def parse_period(period: str) -> tuple[str, int, int]:
    """'2026W40' -> ('weekly', 2026, 40); '202609' -> ('monthly', 2026, 9)."""
    if m := re.fullmatch(r"(\d{4})W(\d{1,2})", period):
        return "weekly", int(m[1]), int(m[2])
    if m := re.fullmatch(r"(\d{4})(\d{2})", period):
        return "monthly", int(m[1]), int(m[2])
    raise ValueError(f"Unsupported DHIS2 period {period!r} (expected e.g. 2026W40 or 202609)")


def iso_weeks(start: date, end: date) -> list[str]:
    """DHIS2 weekly periods (ISO weeks, Monday start) covering start..end."""
    out, d = [], start - timedelta(days=start.weekday())
    while d <= end:
        y, w, _ = d.isocalendar()
        out.append(weekly_period(y, w))
        d += timedelta(days=7)
    return out


@dataclass
class DHIS2OrgUnit:
    uid: str
    name: str
    level: int
    parent_uid: Optional[str]
    code: Optional[str] = None


class DHIS2Client:
    def __init__(self, url: str = None, token: str = None, username: str = None, password: str = None,
                 pull_approved: bool = None, transport: httpx.BaseTransport = None, timeout: float = 60):
        self.url = (url or os.getenv("DHIS2_URL", "")).rstrip("/")
        if not self.url:
            raise DHIS2Error("Set DHIS2_URL in .env (for testing, the public demo server)")
        token = token or os.getenv("DHIS2_TOKEN")
        username = username or os.getenv("DHIS2_USERNAME")
        password = password or os.getenv("DHIS2_PASSWORD")
        if pull_approved is None:
            pull_approved = os.getenv("DHIS2_PULL_APPROVED", "false").lower() == "true"
        self.is_demo = bool(DEMO_HOSTS.search(urlparse(self.url).hostname or ""))
        self.pull_approved = pull_approved
        headers = {"Accept": "application/json"}
        auth = None
        if token:
            headers["Authorization"] = f"ApiToken {token}"
        elif username and password:
            auth = (username, password)
        self.http = httpx.Client(base_url=self.url + "/api", headers=headers, auth=auth,
                                 timeout=timeout, transport=transport)

    def _get(self, path: str, params: dict = None) -> dict:
        try:
            r = self.http.get(path, params=params)
        except httpx.TransportError as e:
            raise DHIS2Error(f"Could not reach DHIS2 at {self.url} ({e}). Check DHIS2_URL and your internet connection.") from e
        if r.status_code == 401:
            raise DHIS2Error("DHIS2 rejected the credentials (401). Check DHIS2_TOKEN or username/password.")
        if r.status_code == 403:
            raise DHIS2Error(f"This DHIS2 account may not read {path} (403).")
        r.raise_for_status()
        return r.json()

    def system_info(self) -> dict:
        return self._get("/system/info")

    def org_units(self, max_level: int = 3) -> list[DHIS2OrgUnit]:
        data = self._get("/organisationUnits", {
            "fields": "id,name,code,level,parent[id]",
            "filter": f"level:le:{max_level}",
            "paging": "false",
        })
        return [DHIS2OrgUnit(uid=o["id"], name=o["name"], level=o["level"],
                             parent_uid=(o.get("parent") or {}).get("id"), code=o.get("code"))
                for o in data.get("organisationUnits", [])]

    def data_values(self, data_set: str, periods: Iterable[str], org_unit: str, children: bool = True) -> list[dict]:
        """Aggregate data values for a data set, periods and an org unit (and its subtree)."""
        if not (self.is_demo or self.pull_approved):
            raise PullNotApproved(
                f"Refusing to pull data from {self.url}: set DHIS2_PULL_APPROVED=true only once the "
                "data owner (EPHI) has approved access in writing. Metadata reads are allowed."
            )
        params = [("dataSet", data_set), ("orgUnit", org_unit), ("children", str(children).lower())]
        params += [("period", p) for p in periods]
        return self._get("/dataValueSets", params).get("dataValues", [])


def to_indicator_counts(data_values: list[dict], element_map: dict, uid_to_pcode: dict,
                        disease: str, source: str = "dhis2") -> tuple[list[dict], dict]:
    """
    Turn weekly DHIS2 data values into indicator_counts rows.

    element_map:  {"<dataElement uid>": "suspected" | "confirmed" | "deaths", ...}
    uid_to_pcode: {"<orgUnit uid>": "<P-code>"}  (from org_units.dhis2_uid)
    Values for the same unit/week/field are summed across category option combos
    (e.g. age groups). Returns (rows, skipped) where skipped counts unmapped values.
    """
    rows: dict[tuple, dict] = {}
    skipped = {"unmapped_element": 0, "unmapped_org_unit": 0, "not_weekly": 0, "not_a_number": 0}
    for v in data_values:
        field = element_map.get(v.get("dataElement"))
        if not field:
            skipped["unmapped_element"] += 1
            continue
        pcode = uid_to_pcode.get(v.get("orgUnit"))
        if not pcode:
            skipped["unmapped_org_unit"] += 1
            continue
        kind, year, week = parse_period(v["period"])
        if kind != "weekly":
            skipped["not_weekly"] += 1
            continue
        try:
            value = int(float(v.get("value")))
        except (TypeError, ValueError):
            skipped["not_a_number"] += 1
            continue
        key = (pcode, year, week)
        row = rows.setdefault(key, {"pcode": pcode, "disease": disease, "iso_year": year, "iso_week": week,
                                    "suspected": None, "confirmed": None, "deaths": None, "source": source})
        row[field] = (row[field] or 0) + value
    return list(rows.values()), skipped


def match_org_units(dhis2_units: list[DHIS2OrgUnit], geocoder, level_offset: int = 1) -> dict:
    """
    Propose dhis2_uid -> P-code links by geocoding each DHIS2 unit's name together with
    its parents' names. level_offset is DHIS2 level minus our level (1 when the DHIS2
    root is the country, so DHIS2 level 2 = region). Returns {"matched": {uid: pcode},
    "ambiguous": {uid: candidates}, "unmatched": [uid, ...]}; matches below 0.9
    confidence or at the wrong level are left for a person to check.
    """
    by_uid = {u.uid: u for u in dhis2_units}
    out = {"matched": {}, "ambiguous": {}, "unmatched": []}
    for u in dhis2_units:
        expected_level = u.level - level_offset
        if expected_level < 1:
            continue  # the country itself
        parents, cur = [], by_uid.get(u.parent_uid) if u.parent_uid else None
        while cur and cur.level - level_offset >= 1:
            parents.append(cur.name)
            cur = by_uid.get(cur.parent_uid) if cur.parent_uid else None
        r = geocoder.resolve(u.name, hints=parents)
        if r.ambiguous:
            out["ambiguous"][u.uid] = r.candidates
        elif r.pcode and r.confidence >= 0.9 and r.level == expected_level:
            out["matched"][u.uid] = r.pcode
        else:
            out["unmatched"].append(u.uid)
    return out
