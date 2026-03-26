"""Integration tests for /api/v1/macro endpoints."""

from __future__ import annotations

import json

import pytest

from src.db import repository as repo


@pytest.fixture(autouse=True)
def _clear_macro_cache():
    """Clear the TTL macro cache between tests."""
    from src.api.middleware.cache import macro_cache
    macro_cache.clear()
    yield
    macro_cache.clear()


_SAMPLE_MACRO = {
    "date": "2026-03-25",
    "vix_regime": "low",
    "dollar_smile": "risk-on",
    "prices": {
        "HYG": 78.5,
        "TIP": 110.2,
        "TNX": 4.25,
        "IRX": 5.1,
        "Copper": 4.8,
        "EEM": 42.0,
        "SPX": 5200.0,
    },
}


# ---------------------------------------------------------------------------
# /macro — DB first, then fallback to file
# ---------------------------------------------------------------------------

async def test_macro_no_data(app_client, tmp_path, monkeypatch):
    """GET /api/v1/macro returns error dict when no data anywhere."""
    from src.api.routes import macro as macro_mod

    monkeypatch.setattr(macro_mod, "_DATA_DIR", tmp_path)
    r = await app_client.get("/api/v1/macro")
    assert r.status_code == 200
    body = r.json()
    assert "error" in body
    await app_client.aclose()


async def test_macro_from_db(app_client, db_session):
    """GET /api/v1/macro returns data from MacroSnapshot in DB."""
    repo.save_macro_snapshot(
        {"full_json": _SAMPLE_MACRO},
        db=db_session,
    )
    db_session.commit()

    r = await app_client.get("/api/v1/macro")
    body = r.json()
    assert body["vix_regime"] == "low"
    assert body["dollar_smile"] == "risk-on"
    await app_client.aclose()


async def test_macro_fallback_to_file(app_client, tmp_path, monkeypatch):
    """GET /api/v1/macro falls back to latest.json when DB is empty."""
    from src.api.routes import macro as macro_mod

    macro_dir = tmp_path / "macro"
    macro_dir.mkdir()
    (macro_dir / "latest.json").write_text(json.dumps(_SAMPLE_MACRO))
    monkeypatch.setattr(macro_mod, "_DATA_DIR", tmp_path)

    r = await app_client.get("/api/v1/macro")
    body = r.json()
    assert body["vix_regime"] == "low"
    await app_client.aclose()


# ---------------------------------------------------------------------------
# /macro/indicators — subset of prices
# ---------------------------------------------------------------------------

async def test_macro_indicators_from_db(app_client, db_session):
    """GET /api/v1/macro/indicators returns the 6 indicator keys."""
    repo.save_macro_snapshot(
        {"full_json": _SAMPLE_MACRO},
        db=db_session,
    )
    db_session.commit()

    r = await app_client.get("/api/v1/macro/indicators")
    body = r.json()
    assert set(body.keys()) == {"HYG", "TIP", "TNX", "IRX", "Copper", "EEM"}
    assert body["HYG"] == 78.5
    await app_client.aclose()


async def test_macro_indicators_empty(app_client, tmp_path, monkeypatch):
    """GET /api/v1/macro/indicators returns {} when no data."""
    from src.api.routes import macro as macro_mod

    monkeypatch.setattr(macro_mod, "_DATA_DIR", tmp_path)
    r = await app_client.get("/api/v1/macro/indicators")
    body = r.json()
    assert body == {}
    await app_client.aclose()
