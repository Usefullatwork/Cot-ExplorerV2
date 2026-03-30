"""Integration tests for /api/v1/prices endpoints."""

from __future__ import annotations

import json

import pytest


@pytest.fixture(autouse=True)
def _clear_prices_cache():
    """Clear the TTL macro cache between tests so /prices/live is fresh."""
    from src.api.middleware.cache import macro_cache

    macro_cache.clear()
    yield
    macro_cache.clear()


async def test_live_prices_returns_200(app_client):
    """GET /api/v1/prices/live returns 200 with items list."""
    r = await app_client.get("/api/v1/prices/live")
    assert r.status_code == 200
    body = r.json()
    assert "items" in body
    assert isinstance(body["items"], list)
    await app_client.aclose()


async def test_live_prices_empty_without_data(app_client, tmp_path, monkeypatch):
    """Prices returns empty items when DB and macro JSON are both empty."""
    from src.api.routes import prices as prices_mod

    monkeypatch.setattr(prices_mod, "_DATA_DIR", tmp_path)
    r = await app_client.get("/api/v1/prices/live")
    body = r.json()
    assert body["items"] == []
    await app_client.aclose()


async def test_live_prices_fallback_to_macro_json(app_client, tmp_path, monkeypatch):
    """Prices falls back to data/macro/latest.json when DB has no prices."""
    from src.api.routes import prices as prices_mod

    macro_dir = tmp_path / "macro"
    macro_dir.mkdir()
    sample = {
        "prices": {
            "EURUSD": {"price": 1.0850, "chg1d": 0.12, "chg5d": -0.05},
            "Gold": {"price": 2340.50, "chg1d": 0.80, "chg5d": 1.20},
        }
    }
    (macro_dir / "latest.json").write_text(json.dumps(sample))
    monkeypatch.setattr(prices_mod, "_DATA_DIR", tmp_path)

    r = await app_client.get("/api/v1/prices/live")
    body = r.json()
    assert len(body["items"]) >= 1
    instruments = [item["instrument"] for item in body["items"]]
    assert "EURUSD" in instruments or "Gold" in instruments
    await app_client.aclose()


async def test_live_prices_item_shape(app_client, tmp_path, monkeypatch):
    """Each price item has instrument, name, group, price, chg_1d, chg_5d."""
    from src.api.routes import prices as prices_mod

    macro_dir = tmp_path / "macro"
    macro_dir.mkdir()
    sample = {
        "prices": {
            "SPX": {"price": 5200.0, "chg1d": 0.5, "chg5d": 1.2},
        }
    }
    (macro_dir / "latest.json").write_text(json.dumps(sample))
    monkeypatch.setattr(prices_mod, "_DATA_DIR", tmp_path)

    r = await app_client.get("/api/v1/prices/live")
    body = r.json()
    assert len(body["items"]) >= 1
    item = body["items"][0]
    assert "instrument" in item
    assert "name" in item
    assert "group" in item
    assert "price" in item
    assert "chg_1d" in item
    assert "chg_5d" in item
    await app_client.aclose()


async def test_price_history_known_instrument(app_client):
    """GET /api/v1/prices/EURUSD/history returns 200 (may be empty without data)."""
    r = await app_client.get("/api/v1/prices/EURUSD/history")
    assert r.status_code == 200
    body = r.json()
    assert body["instrument"] == "EURUSD"
    assert isinstance(body["items"], list)
    await app_client.aclose()


async def test_price_history_empty_items(app_client):
    """Price history returns empty items list when DB has no price data."""
    r = await app_client.get("/api/v1/prices/Gold/history")
    assert r.status_code == 200
    body = r.json()
    assert body["instrument"] == "Gold"
    assert body["items"] == []
    await app_client.aclose()


async def test_price_history_unknown_instrument(app_client):
    """GET /api/v1/prices/INVALID/history returns 404."""
    r = await app_client.get("/api/v1/prices/INVALID/history")
    assert r.status_code == 404
    body = r.json()
    assert "detail" in body
    await app_client.aclose()
