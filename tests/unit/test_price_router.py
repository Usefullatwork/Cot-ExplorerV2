"""Unit tests for src.data.price_router — priority waterfall, fallback chain, rate limiting."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from src.core.models import OhlcBar


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _bar(h: float = 1.1, l: float = 1.0, c: float = 1.05) -> OhlcBar:
    """Create a minimal OhlcBar."""
    return OhlcBar(high=h, low=l, close=c)


def _bars(n: int = 5) -> list[OhlcBar]:
    """Create a list of n simple OhlcBars."""
    return [_bar(h=1.0 + i * 0.01, l=1.0 + i * 0.005, c=1.0 + i * 0.008) for i in range(n)]


# ---------------------------------------------------------------------------
# Module-level patches — we reload the module to control env vars
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _isolate_module(monkeypatch):
    """Ensure env vars are clean and module-level provider instances are mocked."""
    monkeypatch.delenv("TWELVEDATA_API_KEY", raising=False)
    monkeypatch.delenv("FINNHUB_API_KEY", raising=False)


# ===== Priority waterfall tests ============================================

class TestPriorityWaterfall:
    """Twelvedata -> Stooq -> Yahoo (v1 fallback order)."""

    @patch("src.data.price_router._fetch_twelvedata")
    @patch("src.data.price_router._stooq")
    @patch("src.data.price_router._yahoo")
    @patch("src.data.price_router._fetch_finnhub_quote", return_value=None)
    def test_twelvedata_first_for_forex_symbol(self, mock_fh, mock_yahoo, mock_stooq, mock_td):
        """When TD has an API key and symbol is in TD_FREE_SYMBOLS, TD is used first."""
        from src.data import price_router

        bars = _bars(10)
        mock_td.return_value = bars

        with patch.object(price_router, "TWELVEDATA_API_KEY", "fake-key"):
            result = price_router.fetch_prices("EURUSD=X", "1d", "1y")

        mock_td.assert_called_once()
        mock_stooq.fetch_stooq.assert_not_called()
        mock_yahoo.fetch_yahoo.assert_not_called()
        assert result == bars

    @patch("src.data.price_router._fetch_twelvedata")
    @patch("src.data.price_router._stooq")
    @patch("src.data.price_router._yahoo")
    @patch("src.data.price_router._fetch_finnhub_quote", return_value=None)
    def test_stooq_second_for_daily_non_td_symbol(self, mock_fh, mock_yahoo, mock_stooq, mock_td):
        """For daily data on a non-TD symbol, Stooq is tried before Yahoo."""
        from src.data import price_router

        bars = _bars(5)
        mock_stooq.fetch_stooq.return_value = bars

        with patch.object(price_router, "TWELVEDATA_API_KEY", ""):
            result = price_router.fetch_prices("^GSPC", "1d", "1y")

        mock_td.assert_not_called()
        mock_stooq.fetch_stooq.assert_called_once_with("^GSPC", "1y")
        mock_yahoo.fetch_yahoo.assert_not_called()
        assert result == bars

    @patch("src.data.price_router._fetch_twelvedata")
    @patch("src.data.price_router._stooq")
    @patch("src.data.price_router._yahoo")
    @patch("src.data.price_router._fetch_finnhub_quote", return_value=None)
    def test_yahoo_fallback_for_intraday(self, mock_fh, mock_yahoo, mock_stooq, mock_td):
        """Intraday intervals skip Stooq and fall through to Yahoo."""
        from src.data import price_router

        bars = _bars(3)
        mock_yahoo.fetch_yahoo.return_value = bars

        with patch.object(price_router, "TWELVEDATA_API_KEY", ""):
            result = price_router.fetch_prices("AAPL", "15m", "5d")

        mock_td.assert_not_called()
        mock_stooq.fetch_stooq.assert_not_called()
        mock_yahoo.fetch_yahoo.assert_called_once_with("AAPL", "15m", "5d")
        assert result == bars

    @patch("src.data.price_router._fetch_twelvedata")
    @patch("src.data.price_router._stooq")
    @patch("src.data.price_router._yahoo")
    @patch("src.data.price_router._fetch_finnhub_quote", return_value=None)
    def test_td_skipped_when_no_api_key(self, mock_fh, mock_yahoo, mock_stooq, mock_td):
        """Without TWELVEDATA_API_KEY, Twelvedata is skipped entirely."""
        from src.data import price_router

        bars = _bars(5)
        mock_stooq.fetch_stooq.return_value = bars

        with patch.object(price_router, "TWELVEDATA_API_KEY", ""):
            result = price_router.fetch_prices("EURUSD=X", "1d", "1y")

        mock_td.assert_not_called()
        assert result == bars

    @patch("src.data.price_router._fetch_twelvedata")
    @patch("src.data.price_router._stooq")
    @patch("src.data.price_router._yahoo")
    @patch("src.data.price_router._fetch_finnhub_quote", return_value=None)
    def test_td_skipped_for_non_free_symbol(self, mock_fh, mock_yahoo, mock_stooq, mock_td):
        """TD is skipped if symbol is not in TD_FREE_SYMBOLS even with a key."""
        from src.data import price_router

        bars = _bars(5)
        mock_stooq.fetch_stooq.return_value = bars

        with patch.object(price_router, "TWELVEDATA_API_KEY", "fake-key"):
            result = price_router.fetch_prices("^GSPC", "1d", "1y")

        mock_td.assert_not_called()
        mock_stooq.fetch_stooq.assert_called_once()
        assert result == bars


# ===== Fallback chain tests ================================================

class TestFallbackChain:
    """When a higher-priority provider returns empty, the next one is tried."""

    @patch("src.data.price_router._fetch_twelvedata", return_value=[])
    @patch("src.data.price_router._stooq")
    @patch("src.data.price_router._yahoo")
    @patch("src.data.price_router._fetch_finnhub_quote", return_value=None)
    def test_td_empty_falls_to_stooq(self, mock_fh, mock_yahoo, mock_stooq, mock_td):
        """If TD returns empty for a daily symbol, Stooq is tried."""
        from src.data import price_router

        stooq_bars = _bars(8)
        mock_stooq.fetch_stooq.return_value = stooq_bars

        with patch.object(price_router, "TWELVEDATA_API_KEY", "fake-key"):
            result = price_router.fetch_prices("EURUSD=X", "1d", "1y")

        mock_td.assert_called_once()
        mock_stooq.fetch_stooq.assert_called_once()
        assert result == stooq_bars

    @patch("src.data.price_router._fetch_twelvedata", return_value=[])
    @patch("src.data.price_router._stooq")
    @patch("src.data.price_router._yahoo")
    @patch("src.data.price_router._fetch_finnhub_quote", return_value=None)
    def test_td_and_stooq_empty_falls_to_yahoo(self, mock_fh, mock_yahoo, mock_stooq, mock_td):
        """If both TD and Stooq return empty, Yahoo is the final fallback."""
        from src.data import price_router

        yahoo_bars = _bars(3)
        mock_stooq.fetch_stooq.return_value = []
        mock_yahoo.fetch_yahoo.return_value = yahoo_bars

        with patch.object(price_router, "TWELVEDATA_API_KEY", "fake-key"):
            result = price_router.fetch_prices("EURUSD=X", "1d", "1y")

        mock_td.assert_called_once()
        mock_stooq.fetch_stooq.assert_called_once()
        mock_yahoo.fetch_yahoo.assert_called_once_with("EURUSD=X", "1d", "1y")
        assert result == yahoo_bars

    @patch("src.data.price_router._fetch_twelvedata")
    @patch("src.data.price_router._stooq")
    @patch("src.data.price_router._yahoo")
    @patch("src.data.price_router._fetch_finnhub_quote", return_value=None)
    def test_stooq_empty_falls_to_yahoo_daily(self, mock_fh, mock_yahoo, mock_stooq, mock_td):
        """For a non-TD daily symbol, if Stooq returns empty Yahoo is called."""
        from src.data import price_router

        yahoo_bars = _bars(4)
        mock_stooq.fetch_stooq.return_value = []
        mock_yahoo.fetch_yahoo.return_value = yahoo_bars

        with patch.object(price_router, "TWELVEDATA_API_KEY", ""):
            result = price_router.fetch_prices("^GSPC", "1d", "1y")

        mock_stooq.fetch_stooq.assert_called_once()
        mock_yahoo.fetch_yahoo.assert_called_once_with("^GSPC", "1d", "1y")
        assert result == yahoo_bars

    @patch("src.data.price_router._fetch_twelvedata")
    @patch("src.data.price_router._stooq")
    @patch("src.data.price_router._yahoo")
    @patch("src.data.price_router._fetch_finnhub_quote", return_value=None)
    def test_all_providers_empty_returns_empty(self, mock_fh, mock_yahoo, mock_stooq, mock_td):
        """If all providers return empty, fetch_prices returns empty list."""
        from src.data import price_router

        mock_stooq.fetch_stooq.return_value = []
        mock_yahoo.fetch_yahoo.return_value = []

        with patch.object(price_router, "TWELVEDATA_API_KEY", ""):
            result = price_router.fetch_prices("UNKNOWN", "1d", "1y")

        assert result == []


# ===== Finnhub real-time quote overlay =====================================

class TestFinnhubQuoteOverlay:
    """Finnhub quote replaces the last bar on daily data when available."""

    @patch("src.data.price_router._fetch_twelvedata")
    @patch("src.data.price_router._stooq")
    @patch("src.data.price_router._yahoo")
    @patch("src.data.price_router._fetch_finnhub_quote")
    def test_finnhub_replaces_last_bar_on_td_daily(self, mock_fh, mock_yahoo, mock_stooq, mock_td):
        """When TD succeeds with daily data and Finnhub has a quote, last bar is replaced."""
        from src.data import price_router

        bars = _bars(5)
        quote = _bar(h=2.0, l=1.8, c=1.9)
        mock_td.return_value = bars
        mock_fh.return_value = quote

        with patch.object(price_router, "TWELVEDATA_API_KEY", "fake-key"):
            result = price_router.fetch_prices("EURUSD=X", "1d", "1y")

        assert result[-1] == quote
        assert len(result) == 5

    @patch("src.data.price_router._fetch_twelvedata")
    @patch("src.data.price_router._stooq")
    @patch("src.data.price_router._yahoo")
    @patch("src.data.price_router._fetch_finnhub_quote")
    def test_finnhub_replaces_last_bar_on_stooq_daily(self, mock_fh, mock_yahoo, mock_stooq, mock_td):
        """When Stooq succeeds with daily data and Finnhub has a quote, last bar is replaced."""
        from src.data import price_router

        bars = _bars(5)
        quote = _bar(h=3.0, l=2.8, c=2.9)
        mock_stooq.fetch_stooq.return_value = bars
        mock_fh.return_value = quote

        with patch.object(price_router, "TWELVEDATA_API_KEY", ""):
            result = price_router.fetch_prices("^GSPC", "1d", "1y")

        assert result[-1] == quote
        assert len(result) == 5

    @patch("src.data.price_router._fetch_twelvedata")
    @patch("src.data.price_router._stooq")
    @patch("src.data.price_router._yahoo")
    @patch("src.data.price_router._fetch_finnhub_quote", return_value=None)
    def test_finnhub_none_keeps_original_last_bar(self, mock_fh, mock_yahoo, mock_stooq, mock_td):
        """When Finnhub returns None, the last bar is unchanged."""
        from src.data import price_router

        bars = _bars(5)
        original_last = bars[-1]
        mock_stooq.fetch_stooq.return_value = bars

        with patch.object(price_router, "TWELVEDATA_API_KEY", ""):
            result = price_router.fetch_prices("^GSPC", "1d", "1y")

        assert result[-1] == original_last

    @patch("src.data.price_router._fetch_twelvedata")
    @patch("src.data.price_router._stooq")
    @patch("src.data.price_router._yahoo")
    @patch("src.data.price_router._fetch_finnhub_quote")
    def test_no_finnhub_overlay_for_intraday(self, mock_fh, mock_yahoo, mock_stooq, mock_td):
        """Finnhub quote overlay only applies to daily ('1d') data."""
        from src.data import price_router

        bars = _bars(3)
        mock_yahoo.fetch_yahoo.return_value = bars

        with patch.object(price_router, "TWELVEDATA_API_KEY", ""):
            result = price_router.fetch_prices("^GSPC", "15m", "5d")

        mock_fh.assert_not_called()
        assert result == bars


# ===== _fetch_twelvedata unit tests ========================================

class TestFetchTwelvedata:
    """Direct tests for the internal _fetch_twelvedata function."""

    def test_returns_empty_without_api_key(self):
        """No API key => empty list."""
        from src.data.price_router import _fetch_twelvedata

        with patch("src.data.price_router.TWELVEDATA_API_KEY", ""):
            result = _fetch_twelvedata("EURUSD=X", "1d", 365)

        assert result == []

    def test_returns_empty_for_non_free_symbol(self):
        """Symbol not in TD_FREE_SYMBOLS => empty list."""
        from src.data.price_router import _fetch_twelvedata

        with patch("src.data.price_router.TWELVEDATA_API_KEY", "fake-key"):
            result = _fetch_twelvedata("AAPL", "1d", 365)

        assert result == []

    @patch("src.data.price_router.urllib.request.urlopen")
    @patch("src.data.price_router.time.sleep")
    def test_parses_valid_response(self, mock_sleep, mock_urlopen):
        """Valid Twelvedata JSON is parsed into OhlcBars."""
        from src.data.price_router import _fetch_twelvedata

        td_response = {
            "status": "ok",
            "values": [
                {"high": "1.10", "low": "1.05", "close": "1.08"},
                {"high": "1.12", "low": "1.06", "close": "1.09"},
            ],
        }
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps(td_response).encode()
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        with patch("src.data.price_router.TWELVEDATA_API_KEY", "fake-key"):
            result = _fetch_twelvedata("EURUSD=X", "1d", 365)

        assert len(result) == 2
        # reversed() puts the second JSON value first in the output list
        assert result[0].high == 1.12
        assert result[0].close == 1.09
        assert result[1].high == 1.10
        assert result[1].close == 1.08
        mock_sleep.assert_called_once_with(8)  # rate limit sleep

    @patch("src.data.price_router.urllib.request.urlopen")
    def test_returns_empty_on_error_status(self, mock_urlopen):
        """Twelvedata error response returns empty list."""
        from src.data.price_router import _fetch_twelvedata

        td_response = {"status": "error", "message": "API limit reached"}
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps(td_response).encode()
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        with patch("src.data.price_router.TWELVEDATA_API_KEY", "fake-key"):
            result = _fetch_twelvedata("EURUSD=X", "1d", 365)

        assert result == []

    @patch("src.data.price_router.urllib.request.urlopen", side_effect=TimeoutError("timeout"))
    def test_returns_empty_on_timeout(self, mock_urlopen):
        """Network timeout returns empty list (no crash)."""
        from src.data.price_router import _fetch_twelvedata

        with patch("src.data.price_router.TWELVEDATA_API_KEY", "fake-key"):
            result = _fetch_twelvedata("EURUSD=X", "1d", 365)

        assert result == []

    @patch("src.data.price_router.urllib.request.urlopen")
    @patch("src.data.price_router.time.sleep")
    def test_skips_invalid_values(self, mock_sleep, mock_urlopen):
        """Rows with missing/invalid data are skipped, valid ones kept."""
        from src.data.price_router import _fetch_twelvedata

        td_response = {
            "status": "ok",
            "values": [
                {"high": "1.10", "low": "1.05", "close": "1.08"},
                {"high": "not_a_number", "low": "1.06", "close": "1.09"},
                {"high": "1.15", "low": "1.10"},  # missing close
            ],
        }
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps(td_response).encode()
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        with patch("src.data.price_router.TWELVEDATA_API_KEY", "fake-key"):
            result = _fetch_twelvedata("EURUSD=X", "1d", 365)

        assert len(result) == 1
        assert result[0].high == 1.10


# ===== _fetch_finnhub_quote unit tests =====================================

class TestFetchFinnhubQuote:
    """Direct tests for _fetch_finnhub_quote."""

    def test_returns_none_without_api_key(self):
        """No FINNHUB_API_KEY => None."""
        from src.data.price_router import _fetch_finnhub_quote

        with patch("src.data.price_router.FINNHUB_API_KEY", ""):
            result = _fetch_finnhub_quote("^GSPC")

        assert result is None

    def test_returns_none_for_unmapped_symbol(self):
        """Symbol not in FINNHUB_QUOTE_MAP => None."""
        from src.data.price_router import _fetch_finnhub_quote

        with patch("src.data.price_router.FINNHUB_API_KEY", "fake-key"):
            result = _fetch_finnhub_quote("AAPL")

        assert result is None

    @patch("src.data.price_router.urllib.request.urlopen")
    def test_parses_valid_quote(self, mock_urlopen):
        """Valid Finnhub quote response returns an OhlcBar."""
        from src.data.price_router import _fetch_finnhub_quote

        fh_response = {"c": 4500.0, "h": 4520.0, "l": 4480.0, "o": 4490.0}
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps(fh_response).encode()
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        with patch("src.data.price_router.FINNHUB_API_KEY", "fake-key"):
            result = _fetch_finnhub_quote("^GSPC")

        assert result is not None
        assert result.close == 4500.0
        assert result.high == 4520.0
        assert result.low == 4480.0

    @patch("src.data.price_router.urllib.request.urlopen")
    def test_returns_none_on_zero_values(self, mock_urlopen):
        """If c/h/l are 0 (market closed / no data), returns None."""
        from src.data.price_router import _fetch_finnhub_quote

        fh_response = {"c": 0, "h": 0, "l": 0}
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps(fh_response).encode()
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        with patch("src.data.price_router.FINNHUB_API_KEY", "fake-key"):
            result = _fetch_finnhub_quote("^GSPC")

        assert result is None

    @patch("src.data.price_router.urllib.request.urlopen", side_effect=TimeoutError("timeout"))
    def test_returns_none_on_timeout(self, mock_urlopen):
        """Network timeout returns None (no crash)."""
        from src.data.price_router import _fetch_finnhub_quote

        with patch("src.data.price_router.FINNHUB_API_KEY", "fake-key"):
            result = _fetch_finnhub_quote("^GSPC")

        assert result is None


# ===== Rate limiting (Twelvedata 8s sleep) =================================

class TestRateLimiting:
    """Twelvedata free plan enforces an 8-second sleep per request."""

    @patch("src.data.price_router.urllib.request.urlopen")
    @patch("src.data.price_router.time.sleep")
    def test_td_sleeps_8_seconds_after_success(self, mock_sleep, mock_urlopen):
        """After a successful Twelvedata fetch, time.sleep(8) is called."""
        from src.data.price_router import _fetch_twelvedata

        td_response = {
            "status": "ok",
            "values": [{"high": "1.10", "low": "1.05", "close": "1.08"}],
        }
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps(td_response).encode()
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        with patch("src.data.price_router.TWELVEDATA_API_KEY", "fake-key"):
            _fetch_twelvedata("EURUSD=X", "1d", 365)

        mock_sleep.assert_called_once_with(8)

    @patch("src.data.price_router.urllib.request.urlopen")
    def test_td_no_sleep_on_error_status(self, mock_urlopen):
        """On error status response, the 8s sleep is NOT reached."""
        from src.data.price_router import _fetch_twelvedata

        td_response = {"status": "error", "message": "rate limit"}
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps(td_response).encode()
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        with patch("src.data.price_router.TWELVEDATA_API_KEY", "fake-key"), \
             patch("src.data.price_router.time.sleep") as mock_sleep:
            _fetch_twelvedata("EURUSD=X", "1d", 365)

        mock_sleep.assert_not_called()


# ===== Edge cases ==========================================================

class TestEdgeCases:
    """Edge cases: empty symbol, interval mapping, TD_SIZE fallback."""

    @patch("src.data.price_router._fetch_twelvedata")
    @patch("src.data.price_router._stooq")
    @patch("src.data.price_router._yahoo")
    @patch("src.data.price_router._fetch_finnhub_quote", return_value=None)
    def test_empty_symbol_goes_to_yahoo(self, mock_fh, mock_yahoo, mock_stooq, mock_td):
        """An empty string symbol is not in TD_FREE_SYMBOLS, not in Stooq map, falls to Yahoo."""
        from src.data import price_router

        mock_stooq.fetch_stooq.return_value = []
        mock_yahoo.fetch_yahoo.return_value = []

        with patch.object(price_router, "TWELVEDATA_API_KEY", ""):
            result = price_router.fetch_prices("", "1d", "1y")

        mock_yahoo.fetch_yahoo.assert_called_once_with("", "1d", "1y")
        assert result == []

    @patch("src.data.price_router.urllib.request.urlopen")
    @patch("src.data.price_router.time.sleep")
    def test_td_interval_mapping(self, mock_sleep, mock_urlopen):
        """TD_INTERVAL maps '1d' -> '1day', '15m' -> '15min', '60m' -> '1h'."""
        from src.data.price_router import _fetch_twelvedata, TD_INTERVAL

        assert TD_INTERVAL == {"1d": "1day", "15m": "15min", "60m": "1h"}

    def test_td_size_mapping(self):
        """TD_SIZE maps range keys to output sizes."""
        from src.data.price_router import TD_SIZE

        assert TD_SIZE["1y"] == 365
        assert TD_SIZE["5d"] == 500
        assert TD_SIZE["60d"] == 500
        assert TD_SIZE["30d"] == 35

    def test_td_free_symbols_contains_expected(self):
        """TD_FREE_SYMBOLS contains the expected forex/gold/etf symbols."""
        from src.data.price_router import TD_FREE_SYMBOLS

        assert "EURUSD=X" in TD_FREE_SYMBOLS
        assert "GC=F" in TD_FREE_SYMBOLS
        assert "HYG" in TD_FREE_SYMBOLS
        assert "^GSPC" not in TD_FREE_SYMBOLS  # not on free plan

    @patch("src.data.price_router._fetch_twelvedata")
    @patch("src.data.price_router._stooq")
    @patch("src.data.price_router._yahoo")
    @patch("src.data.price_router._fetch_finnhub_quote", return_value=None)
    def test_60m_interval_skips_stooq(self, mock_fh, mock_yahoo, mock_stooq, mock_td):
        """60m interval is intraday — should skip Stooq and go to Yahoo."""
        from src.data import price_router

        bars = _bars(4)
        mock_yahoo.fetch_yahoo.return_value = bars

        with patch.object(price_router, "TWELVEDATA_API_KEY", ""):
            result = price_router.fetch_prices("AAPL", "60m", "5d")

        mock_stooq.fetch_stooq.assert_not_called()
        mock_yahoo.fetch_yahoo.assert_called_once_with("AAPL", "60m", "5d")
        assert result == bars

    @patch("src.data.price_router._fetch_twelvedata")
    @patch("src.data.price_router._stooq")
    @patch("src.data.price_router._yahoo")
    @patch("src.data.price_router._fetch_finnhub_quote")
    def test_td_intraday_success_no_finnhub_overlay(self, mock_fh, mock_yahoo, mock_stooq, mock_td):
        """When TD succeeds for intraday (15m), Finnhub overlay is NOT applied."""
        from src.data import price_router

        bars = _bars(5)
        mock_td.return_value = bars

        with patch.object(price_router, "TWELVEDATA_API_KEY", "fake-key"):
            result = price_router.fetch_prices("EURUSD=X", "15m", "5d")

        mock_fh.assert_not_called()
        assert result == bars

    def test_td_size_unknown_range_defaults_to_365(self):
        """An unknown range key falls back to the dict.get default of 365."""
        from src.data.price_router import TD_SIZE

        assert TD_SIZE.get("99y", 365) == 365

    def test_twelvedata_map_completeness(self):
        """Every TD_FREE_SYMBOLS entry has a corresponding TWELVEDATA_MAP entry."""
        from src.data.price_router import TD_FREE_SYMBOLS, TWELVEDATA_MAP

        for sym in TD_FREE_SYMBOLS:
            assert sym in TWELVEDATA_MAP, f"{sym} missing from TWELVEDATA_MAP"

    def test_finnhub_quote_map_symbols(self):
        """FINNHUB_QUOTE_MAP contains the expected index/commodity symbols."""
        from src.data.price_router import FINNHUB_QUOTE_MAP

        assert "^GSPC" in FINNHUB_QUOTE_MAP
        assert "^VIX" in FINNHUB_QUOTE_MAP
        assert "CL=F" in FINNHUB_QUOTE_MAP
        assert "EURUSD=X" not in FINNHUB_QUOTE_MAP  # forex not in Finnhub map

    @patch("src.data.price_router.urllib.request.urlopen")
    def test_finnhub_partial_zero_returns_none(self, mock_urlopen):
        """If only some of c/h/l are zero, Finnhub returns None (falsy check)."""
        from src.data.price_router import _fetch_finnhub_quote

        fh_response = {"c": 4500.0, "h": 0, "l": 4480.0}
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps(fh_response).encode()
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        with patch("src.data.price_router.FINNHUB_API_KEY", "fake-key"):
            result = _fetch_finnhub_quote("^GSPC")

        assert result is None

    @patch("src.data.price_router.urllib.request.urlopen")
    @patch("src.data.price_router.time.sleep")
    def test_td_empty_values_array_returns_empty(self, mock_sleep, mock_urlopen):
        """Twelvedata response with status ok but empty values returns empty list."""
        from src.data.price_router import _fetch_twelvedata

        td_response = {"status": "ok", "values": []}
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps(td_response).encode()
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        with patch("src.data.price_router.TWELVEDATA_API_KEY", "fake-key"):
            result = _fetch_twelvedata("EURUSD=X", "1d", 365)

        assert result == []
        mock_sleep.assert_called_once_with(8)

    @patch("src.data.price_router.urllib.request.urlopen", side_effect=ConnectionError("refused"))
    def test_finnhub_connection_error_returns_none(self, mock_urlopen):
        """Network connection error on Finnhub returns None gracefully."""
        from src.data.price_router import _fetch_finnhub_quote

        with patch("src.data.price_router.FINNHUB_API_KEY", "fake-key"):
            result = _fetch_finnhub_quote("^GSPC")

        assert result is None

    @patch("src.data.price_router._fetch_twelvedata")
    @patch("src.data.price_router._stooq")
    @patch("src.data.price_router._yahoo")
    @patch("src.data.price_router._fetch_finnhub_quote", return_value=None)
    def test_fetch_prices_default_parameters(self, mock_fh, mock_yahoo, mock_stooq, mock_td):
        """fetch_prices with only symbol uses defaults: interval='1d', range='1y'."""
        from src.data import price_router

        bars = _bars(5)
        mock_stooq.fetch_stooq.return_value = bars

        with patch.object(price_router, "TWELVEDATA_API_KEY", ""):
            result = price_router.fetch_prices("^GSPC")

        mock_stooq.fetch_stooq.assert_called_once_with("^GSPC", "1y")
        assert result == bars
