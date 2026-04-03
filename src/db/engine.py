"""SQLAlchemy engine setup for SQLite persistence."""

from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

_engine: Engine | None = None
_SessionLocal: sessionmaker[Session] | None = None


def _enable_wal(dbapi_conn: object, _connection_record: object) -> None:
    """Enable WAL mode and foreign keys for SQLite connections."""
    cursor = dbapi_conn.cursor()  # type: ignore[union-attr]
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


def get_engine(db_url: str | None = None) -> Engine:
    """Return the singleton SQLAlchemy engine.

    Uses *db_url* if provided, else the ``DATABASE_URL`` env var, else a
    default SQLite file at ``data/cot-explorer.db``.
    """
    global _engine
    if _engine is not None:
        return _engine

    url = db_url or os.environ.get("DATABASE_URL", "sqlite:///data/cot-explorer.db")
    _engine = create_engine(
        url,
        echo=False,
        future=True,
        connect_args={"check_same_thread": False} if url.startswith("sqlite") else {},
    )

    if url.startswith("sqlite"):
        event.listen(_engine, "connect", _enable_wal)

    return _engine


def get_session() -> sessionmaker[Session]:
    """Return the SessionLocal factory (creates one if needed)."""
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(
            bind=get_engine(),
            autocommit=False,
            autoflush=False,
            expire_on_commit=False,
        )
    return _SessionLocal


def session_scope() -> Generator[Session, None, None]:
    """Context manager that yields a transactional session and auto-commits."""
    factory = get_session()
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


@contextmanager
def session_ctx() -> Generator[Session, None, None]:
    """Context manager for DB sessions — use with ``with`` statement.

    Same lifecycle as ``session_scope`` (auto-commit, rollback on error)
    but wrapped with ``@contextmanager`` for ``with`` blocks in routes.
    """
    factory = get_session()
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def init_db(db_url: str | None = None) -> None:
    """Create all tables defined in :mod:`src.db.models`."""
    from src.db.models import Base  # noqa: F811 — deferred to avoid circular import

    engine = get_engine(db_url)
    Base.metadata.create_all(bind=engine)
