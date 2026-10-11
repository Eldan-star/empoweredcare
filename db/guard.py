"""
Guard against loading test or simulated data into the real database.

Every table that holds data from outside (counts, snapshots, coverage, campaigns, births,
context factors, boundaries) has a `source` column. Before each write, the guard checks
the source of every new or changed row and refuses the whole write when it names test,
simulated or demo data (for example "simulated", "laser-measles", "test", "dhis2-demo").

- It is installed on the application's sessions (db/session.py), so the web app and every
  loader script are covered.
- Tests use their own sessions on a throwaway database and are not guarded.
- A sandbox or demo database can switch it off with ALLOW_TEST_DATA=true in .env. Never
  set this on the database EPHI uses.
"""

import os
import re

from sqlalchemy import event

BLOCKED_SOURCE = re.compile(
    r"\b(simulat\w*|synthetic|laser\w*|test\w*|fake|dummy|mock|demo)\b", re.IGNORECASE)


class TestDataRefused(ValueError):
    """A write would put test, simulated or demo data into the real database."""


def blocked(source) -> bool:
    return isinstance(source, str) and bool(BLOCKED_SOURCE.search(source))


def check(session, flush_context=None, instances=None) -> None:
    if os.getenv("ALLOW_TEST_DATA", "false").lower() == "true":
        return
    bad = sorted({f"{type(obj).__name__} (source {obj.source!r})"
                  for obj in list(session.new) + list(session.dirty)
                  if blocked(getattr(obj, "source", None))})
    if bad:
        raise TestDataRefused(
            "Refusing to save test, simulated or demo data into this database: "
            + ", ".join(bad) + ". Use a test database, or set ALLOW_TEST_DATA=true only on a "
            "sandbox database.")


def install(session_factory) -> None:
    """Run the check before every flush of sessions made by `session_factory`."""
    event.listen(session_factory, "before_flush", check)
