"""Integration tests for /api/v1/instruments endpoints."""

from __future__ import annotations

import pytest

from src.db import repository as repo


@pytest.fixture(autouse=True)
def _clear_instruments_cache():
    """Clear the module-level instrument cache and TTL cache between tests."""
    from src.api.middleware.cache import instruments_cache
    from src.api.routes import instruments as inst_mod

    inst_mod._INSTRUMENTS_CACHE = None
    instruments_cache.clear()
    yield
    inst_mod._INSTRUMENTS_CACHE = None
    instruments_cache.clear()


async def test_list_instruments(app_client):
    """GET /api/v1/instruments returns a list of 14 instruments."""
    r = await app_client.get("/api/v1/instruments")
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)
    assert len(data) == 14
    await app_client.aclose()


async def test_list_instruments_has_expected_keys(app_client):
    """Each instrument dict has key, name, symbol, label, category."""
    r = await app_client.get("/api/v1/instruments")
    data = r.json()
    for inst in data:
        assert "key" in inst
        assert "name" in inst
        assert "symbol" in inst
        assert "label" in inst
        assert "category" in inst
    await app_client.aclose()


async def test_instrument_detail_found(app_client):
    """GET /api/v1/instruments/EURUSD returns the instrument."""
    r = await app_client.get("/api/v1/instruments/EURUSD")
    assert r.status_code == 200
    body = r.json()
    assert body["key"] == "EURUSD"
    assert body["name"] == "EUR/USD"
    await app_client.aclose()


async def test_instrument_detail_not_found(app_client):
    """GET /api/v1/instruments/NOPE returns 404."""
    r = await app_client.get("/api/v1/instruments/NOPE")
    assert r.status_code == 404
    await app_client.aclose()


async def test_instrument_detail_no_price(app_client):
    """Instrument detail has current_price=null when no prices in DB."""
    r = await app_client.get("/api/v1/instruments/EURUSD")
    body = r.json()
    assert body["current_price"] is None
    await app_client.aclose()


async def test_instrument_detail_with_price(app_client, db_session, seed_instrument):
    """Instrument detail includes current_price when prices exist."""
    repo.save_price_daily(
        instrument="EURUSD",
        date="2026-03-25",
        ohlcv={"high": 1.09, "low": 1.07, "close": 1.085, "source": "test"},
        db=db_session,
    )
    db_session.commit()

    r = await app_client.get("/api/v1/instruments/EURUSD")
    body = r.json()
    assert body["current_price"] is not None
    assert body["current_price"]["close"] == 1.085
    assert body["current_price"]["high"] == 1.09
    assert body["current_price"]["low"] == 1.07
    assert body["current_price"]["date"] == "2026-03-25"
    assert body["current_price"]["source"] == "test"
    await app_client.aclose()
