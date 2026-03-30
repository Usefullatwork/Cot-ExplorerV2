"""Integration tests for /api/v1/crypto endpoints."""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _clear_crypto_cache():
    """Clear the TTL macro cache between tests so crypto endpoints re-fetch."""
    from src.api.middleware.cache import macro_cache

    macro_cache.clear()
    yield
    macro_cache.clear()


# ---------------------------------------------------------------------------
# /crypto/market
# ---------------------------------------------------------------------------


async def test_crypto_market_returns_200(app_client):
    """GET /api/v1/crypto/market returns 200 even without CoinGecko data."""
    r = await app_client.get("/api/v1/crypto/market")
    assert r.status_code == 200
    await app_client.aclose()


async def test_crypto_market_response_shape(app_client):
    """GET /api/v1/crypto/market response has coins, total_market_cap, btc_dominance, fetched_at."""
    r = await app_client.get("/api/v1/crypto/market")
    assert r.status_code == 200
    body = r.json()
    assert "coins" in body
    assert "total_market_cap" in body
    assert "btc_dominance" in body
    assert "fetched_at" in body
    assert isinstance(body["coins"], list)
    await app_client.aclose()


# ---------------------------------------------------------------------------
# /crypto/fear-greed
# ---------------------------------------------------------------------------


async def test_crypto_fear_greed_returns_200(app_client):
    """GET /api/v1/crypto/fear-greed returns 200 even without external API."""
    r = await app_client.get("/api/v1/crypto/fear-greed")
    assert r.status_code == 200
    await app_client.aclose()


async def test_crypto_fear_greed_response_shape(app_client):
    """GET /api/v1/crypto/fear-greed response has value, label, timestamp, fetched_at."""
    r = await app_client.get("/api/v1/crypto/fear-greed")
    assert r.status_code == 200
    body = r.json()
    assert "value" in body
    assert "label" in body
    assert "timestamp" in body
    assert "fetched_at" in body
    assert isinstance(body["value"], int)
    await app_client.aclose()
