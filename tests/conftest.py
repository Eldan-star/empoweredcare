"""
Shared test fixtures.

Database tests use TEST_DATABASE_URL when it is set (point it at an empty PostgreSQL
database to test against the real thing) and an in-memory SQLite database otherwise.
"""

import os
import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
# config.py refuses to start outside development without these; tests never call Gemini.
os.environ.setdefault("APP_ENV", "development")
os.environ.setdefault("GEMINI_API_KEY", "test-key-not-used")

from db.models import Base  # noqa: E402

TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL", "sqlite://")


@pytest.fixture
def engine():
    eng = create_engine(TEST_DATABASE_URL, future=True)
    if eng.dialect.name == "sqlite":
        # SQLite ignores foreign keys unless asked, PostgreSQL always enforces them.
        event.listen(eng, "connect", lambda conn, _: conn.execute("PRAGMA foreign_keys=ON"))
    Base.metadata.drop_all(eng)
    Base.metadata.create_all(eng)
    yield eng
    Base.metadata.drop_all(eng)
    eng.dispose()


@pytest.fixture
def db(engine):
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    yield session
    session.rollback()
    session.close()
