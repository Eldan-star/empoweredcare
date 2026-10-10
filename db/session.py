"""Database engine and sessions. DATABASE_URL (in .env) chooses the database."""

from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from config import DATABASE_URL


def make_engine(url: str = DATABASE_URL):
    # pool_pre_ping drops connections the server closed (e.g. after PostgreSQL restarts).
    return create_engine(url, pool_pre_ping=True, future=True)


engine = make_engine()
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


@contextmanager
def session_scope() -> Iterator[Session]:
    """A session that commits on success and rolls back on error."""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_db() -> Iterator[Session]:
    """FastAPI dependency: one session per request."""
    with session_scope() as session:
        yield session
