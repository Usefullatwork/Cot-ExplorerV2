"""Shared test fixtures for unit and integration tests."""

from __future__ import annotations

import os
from typing import AsyncGenerator, Generator

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

import src.db.engine as engine_module
from src.db.models import Base


@pytest.fixture()
def db_engine(tmp_path):
    """Create an in-memory SQLite engine with all tables."""
    eng = create_engine(
        "sqlite:///:memory:",
        echo=False,
        future=True,
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=eng)
    yield eng
    Base.metadata.drop_all(bind=eng)
    eng.dispose()


@pytest.fixture()
def db_session(db_engine) -> Generator[Session, None, None]:
    """Yield a transactional session that rolls back after each test."""
    factory = sessionmaker(
        bind=db_engine,
        autocommit=False,
        autoflush=False,
        expire_on_commit=False,
    )
    session = factory()
    yield session
    session.rollback()
    session.close()


@pytest.fixture()
def patch_db(db_engine, db_session, monkeypatch):
    """Monkeypatch the engine module to use the test DB.

    Patches both the singleton engine and the session factory so that
    any code importing from src.db.engine gets the test database.
    """
    factory = sessionmaker(
        bind=db_engine,
        autocommit=False,
        autoflush=False,
        expire_on_commit=False,
    )
    monkeypatch.setattr(engine_module, "_engine", db_engine)
    monkeypatch.setattr(engine_module, "_SessionLocal", factory)
    return db_session


@pytest.fixture()
def app_client(patch_db, monkeypatch):
    """Async httpx client for testing FastAPI endpoints in public mode."""
    monkeypatch.setenv("SCALP_API_KEY", "")

    # Must import AFTER patching engine
    from httpx import ASGITransport, AsyncClient

    from src.api.app import create_app

    app = create_app()
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")


@pytest.fixture()
def app_client_with_auth(patch_db, monkeypatch):
    """Async httpx client with API key authentication enabled."""
    monkeypatch.setenv("SCALP_API_KEY", "test-secret-key")

    from httpx import ASGITransport, AsyncClient

    from src.api.app import create_app

    app = create_app()
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")


@pytest.fixture()
def seed_instrument(db_session):
    """Insert a minimal EURUSD instrument into the test DB."""
    from src.db.models import Instrument

    inst = Instrument(
        key="EURUSD",
        name="EUR/USD",
        symbol="EURUSD=X",
        label="Valuta",
        category="valuta",
        class_="A",
        session="London",
        active=True,
    )
    db_session.add(inst)
    db_session.commit()
    return inst
