"""Integration test overrides — use StaticPool for in-memory SQLite.

The root conftest.py creates a plain :memory: engine, but sync FastAPI routes
run in a thread-pool, which opens new connections.  In-memory SQLite gives
each connection its own database, so the route threads would see empty tables.

This file overrides ``db_engine`` with a ``StaticPool`` engine so that every
connection (including those in worker threads) shares a single underlying
DBAPI connection and therefore sees the same data.
"""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from src.db.models import Base


@pytest.fixture()
def db_engine():
    """In-memory SQLite engine with StaticPool for cross-thread visibility."""
    eng = create_engine(
        "sqlite:///:memory:",
        echo=False,
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=eng)
    yield eng
    Base.metadata.drop_all(bind=eng)
    eng.dispose()
