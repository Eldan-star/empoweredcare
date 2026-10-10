"""Weekly count series for one unit and disease, with ISO-week arithmetic."""

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Iterable, Optional


@dataclass
class WeekCount:
    iso_year: int
    iso_week: int
    suspected: Optional[int] = None  # None = no report (not zero)
    confirmed: Optional[int] = None
    deaths: Optional[int] = None
    reports_expected: Optional[int] = None
    reports_received: Optional[int] = None

    @property
    def key(self) -> tuple[int, int]:
        return (self.iso_year, self.iso_week)

    @property
    def reported(self) -> bool:
        return self.suspected is not None or self.confirmed is not None


def monday(year: int, week: int) -> date:
    return date.fromisocalendar(year, week, 1)


def shift(year: int, week: int, weeks: int) -> tuple[int, int]:
    y, w, _ = (monday(year, week) + timedelta(weeks=weeks)).isocalendar()
    return y, w


def complete(weeks: Iterable[WeekCount], start: Optional[tuple[int, int]] = None,
             end: Optional[tuple[int, int]] = None) -> list[WeekCount]:
    """Sort by week and insert empty (unreported) weeks so the series has no gaps."""
    by_key = {w.key: w for w in weeks}
    if not by_key and not (start and end):
        return []
    start = start or min(by_key)
    end = end or max(by_key)
    out, cur = [], start
    while cur <= end:
        out.append(by_key.get(cur) or WeekCount(*cur))
        cur = shift(*cur, 1)
    return out


def value(w: WeekCount, field: str = "suspected") -> int:
    """Count for sums and statistics; an unreported week counts as 0 here, and callers
    track missingness separately."""
    return getattr(w, field) or 0
