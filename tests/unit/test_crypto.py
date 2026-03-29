"""Unit tests for crypto scraper and route."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from src.trading.scrapers.crypto import fetch_crypto_market, fetch_fear_greed


# ── Scraper tests ────────────────────────────────────────────────────────────

_COINGECKO_RESPONSE = [
    {
        "id": "bitcoin",
        "symbol": "btc",
        "name": "Bitcoin",
        "current_price": 65000.0,
        "market_cap": 1_300_000_000_000,
        "total_volume": 30_000_000_000,
        "price_change_percentage_24h": 2.5,
        "market_cap_rank": 1,
        "image": "https://example.com/btc.png",
    },
    {
        "id": "ethereum",
        "symbol": "eth",
        "name": "Ethereum",
        "current_price": 3500.0,
        "market_cap": 420_000_000_000,
        "total_volume": 15_000_000_000,
        "price_change_percentage_24h": -1.2,
        "market_cap_rank": 2,
        "image": "https://example.com/eth.png",
    },
]

_FNG_RESPONSE = {
    "data": [
        {
            "value": "25",
            "value_classification": "Extreme Fear",
            "timestamp": "1711843200",
        }
    ]
}


class TestFetchCryptoMarket:
    """Tests for fetch_crypto_market scraper."""

    @patch("src.trading.scrapers.crypto.urllib.request.urlopen")
    def test_success(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps(_COINGECKO_RESPONSE).encode()
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        result = fetch_crypto_market()

        assert result is not None
        assert len(result["coins"]) == 2
        assert result["coins"][0]["symbol"] == "BTC"
        assert result["coins"][0]["price"] == 65000.0
        assert result["total_market_cap"] == 1_720_000_000_000
        assert result["btc_dominance"] == pytest.approx(75.6, abs=0.1)
        assert result["fetched_at"]

    @patch("src.trading.scrapers.crypto.urllib.request.urlopen")
    def test_network_error_returns_none(self, mock_urlopen):
        mock_urlopen.side_effect = TimeoutError("connection timeout")
        assert fetch_crypto_market() is None

    @patch("src.trading.scrapers.crypto.urllib.request.urlopen")
    def test_empty_response_returns_none(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.read.return_value = b"[]"
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        assert fetch_crypto_market() is None


class TestFetchFearGreed:
    """Tests for fetch_fear_greed scraper."""

    @patch("src.trading.scrapers.crypto.urllib.request.urlopen")
    def test_success(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps(_FNG_RESPONSE).encode()
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        result = fetch_fear_greed()

        assert result is not None
        assert result["value"] == 25
        assert result["label"] == "Extreme Fear"
        assert result["timestamp"] == "1711843200"

    @patch("src.trading.scrapers.crypto.urllib.request.urlopen")
    def test_network_error_returns_none(self, mock_urlopen):
        mock_urlopen.side_effect = ConnectionError("refused")
        assert fetch_fear_greed() is None

    @patch("src.trading.scrapers.crypto.urllib.request.urlopen")
    def test_empty_data_returns_none(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({"data": []}).encode()
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        assert fetch_fear_greed() is None


# ── Route tests (via TestClient) ────────────────────────────────────────────


class TestCryptoRoutes:
    """Tests for /api/v1/crypto/* endpoints."""

    @pytest.fixture(autouse=True)
    def _clear_cache(self):
        from src.api.middleware.cache import macro_cache
        macro_cache.clear()

    @patch("src.api.routes.crypto.fetch_crypto_market")
    def test_market_endpoint_success(self, mock_fetch):
        from httpx import ASGITransport, AsyncClient
        from src.api.app import app

        mock_fetch.return_value = {
            "coins": [{"id": "bitcoin", "symbol": "BTC", "name": "Bitcoin",
                        "price": 65000, "market_cap": 1_300_000_000_000,
                        "volume_24h": 30_000_000_000, "change_24h": 2.5,
                        "rank": 1, "image": ""}],
            "total_market_cap": 1_300_000_000_000,
            "btc_dominance": 100.0,
            "fetched_at": "2026-03-29T12:00:00Z",
        }

        import asyncio

        async def _test():
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
                r = await c.get("/api/v1/crypto/market")
                assert r.status_code == 200
                data = r.json()
                assert len(data["coins"]) == 1
                assert data["coins"][0]["symbol"] == "BTC"

        asyncio.run(_test())

    @patch("src.api.routes.crypto.fetch_crypto_market", return_value=None)
    def test_market_endpoint_no_data(self, mock_fetch):
        from httpx import ASGITransport, AsyncClient
        from src.api.app import app

        import asyncio

        async def _test():
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
                r = await c.get("/api/v1/crypto/market")
                assert r.status_code == 200
                assert r.json()["coins"] == []

        asyncio.run(_test())

    @patch("src.api.routes.crypto.fetch_fear_greed")
    def test_fear_greed_endpoint(self, mock_fetch):
        from httpx import ASGITransport, AsyncClient
        from src.api.app import app

        mock_fetch.return_value = {
            "value": 72,
            "label": "Greed",
            "timestamp": "1711843200",
            "fetched_at": "2026-03-29T12:00:00Z",
        }

        import asyncio

        async def _test():
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
                r = await c.get("/api/v1/crypto/fear-greed")
                assert r.status_code == 200
                data = r.json()
                assert data["value"] == 72
                assert data["label"] == "Greed"

        asyncio.run(_test())
