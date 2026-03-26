"""Unit tests for src.trading.scrapers — all 7 data scrapers.

Tests mock urllib.request.urlopen to avoid real HTTP calls.
Each scraper returns tuples, floats, dicts, or None depending on the endpoint.
"""

from __future__ import annotations

import json
import os
import urllib.error
from unittest.mock import MagicMock, patch


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mock_urlopen(data: bytes):
    """Return a context-manager mock that yields .read() -> data."""
    cm = MagicMock()
    cm.__enter__ = MagicMock(return_value=cm)
    cm.__exit__ = MagicMock(return_value=False)
    cm.read.return_value = data
    return cm


def _mock_urlopen_text(text: str):
    """Return a context-manager mock for text-based responses (CSV)."""
    cm = MagicMock()
    inner = MagicMock()
    inner.read.return_value = text.encode()
    cm.__enter__ = MagicMock(return_value=inner)
    cm.__exit__ = MagicMock(return_value=False)
    return cm


# ===========================================================================
# 1. Yahoo Finance — fetch_ohlc, fetch_price_changes
# ===========================================================================


class TestYahooFinanceScraper:
    """Tests for src.trading.scrapers.yahoo_finance."""

    def _make_yahoo_json(self, highs, lows, closes):
        payload = {
            "chart": {
                "result": [
                    {
                        "timestamp": list(range(len(highs))),
                        "indicators": {
                            "quote": [{"high": highs, "low": lows, "close": closes}]
                        },
                    }
                ],
                "error": None,
            }
        }
        return json.dumps(payload).encode()

    @patch("src.trading.scrapers.yahoo_finance.urllib.request.urlopen")
    def test_fetch_ohlc_success(self, mock_urlopen):
        """Valid JSON with 3 bars returns 3 (h, l, c) tuples."""
        data = self._make_yahoo_json(
            highs=[1.10, 1.12, 1.15],
            lows=[1.05, 1.08, 1.09],
            closes=[1.07, 1.11, 1.14],
        )
        mock_urlopen.return_value = _mock_urlopen(data)

        from src.trading.scrapers.yahoo_finance import fetch_ohlc

        rows = fetch_ohlc("EURUSD=X", "1d", "1y")
        assert len(rows) == 3
        assert rows[0] == (1.10, 1.05, 1.07)
        assert rows[2] == (1.15, 1.09, 1.14)

    @patch("src.trading.scrapers.yahoo_finance.urllib.request.urlopen")
    def test_fetch_ohlc_network_error(self, mock_urlopen):
        """Network error returns empty list."""
        mock_urlopen.side_effect = urllib.error.URLError("no network")

        from src.trading.scrapers.yahoo_finance import fetch_ohlc

        result = fetch_ohlc("EURUSD=X")
        assert result == []

    @patch("src.trading.scrapers.yahoo_finance.urllib.request.urlopen")
    def test_fetch_ohlc_empty_quotes(self, mock_urlopen):
        """Response with empty quote arrays returns empty list."""
        data = self._make_yahoo_json(highs=[], lows=[], closes=[])
        mock_urlopen.return_value = _mock_urlopen(data)

        from src.trading.scrapers.yahoo_finance import fetch_ohlc

        result = fetch_ohlc("^GSPC")
        assert result == []

    @patch("src.trading.scrapers.yahoo_finance.urllib.request.urlopen")
    def test_fetch_ohlc_none_values_filtered(self, mock_urlopen):
        """Bars with None in h/l/c are filtered out."""
        data = self._make_yahoo_json(
            highs=[1.10, None, 1.15],
            lows=[1.05, 1.08, None],
            closes=[1.07, 1.11, 1.14],
        )
        mock_urlopen.return_value = _mock_urlopen(data)

        from src.trading.scrapers.yahoo_finance import fetch_ohlc

        rows = fetch_ohlc("EURUSD=X")
        assert len(rows) == 1
        assert rows[0] == (1.10, 1.05, 1.07)

    @patch("src.trading.scrapers.yahoo_finance.urllib.request.urlopen")
    def test_fetch_price_changes_success(self, mock_urlopen):
        """fetch_price_changes returns dict with price and change percentages."""
        closes = [100.0] * 21 + [102.0]  # 22 data points
        payload = {
            "chart": {
                "result": [
                    {
                        "timestamp": list(range(len(closes))),
                        "indicators": {
                            "quote": [
                                {
                                    "high": closes,
                                    "low": closes,
                                    "close": closes,
                                }
                            ]
                        },
                    }
                ],
                "error": None,
            }
        }
        mock_urlopen.return_value = _mock_urlopen(json.dumps(payload).encode())

        from src.trading.scrapers.yahoo_finance import fetch_price_changes

        result = fetch_price_changes("GC=F")
        assert result is not None
        assert "price" in result
        assert "chg1d" in result
        assert "chg5d" in result
        assert "chg20d" in result
        assert result["price"] == 102.0

    @patch("src.trading.scrapers.yahoo_finance.urllib.request.urlopen")
    def test_fetch_price_changes_error(self, mock_urlopen):
        """Network error in fetch_price_changes returns None."""
        mock_urlopen.side_effect = OSError("timeout")

        from src.trading.scrapers.yahoo_finance import fetch_price_changes

        result = fetch_price_changes("GC=F")
        assert result is None


# ===========================================================================
# 2. Stooq — fetch_ohlc
# ===========================================================================


class TestStooqScraper:
    """Tests for src.trading.scrapers.stooq."""

    @patch("src.trading.scrapers.stooq.urllib.request.urlopen")
    def test_fetch_ohlc_success(self, mock_urlopen):
        """Valid CSV with 2 rows returns 2 (h, l, c) tuples."""
        csv = (
            "Date,Open,High,Low,Close,Volume\n"
            "2024-01-02,1.10,1.12,1.09,1.11,1000\n"
            "2024-01-03,1.11,1.13,1.10,1.12,2000\n"
        )
        mock_urlopen.return_value = _mock_urlopen_text(csv)

        from src.trading.scrapers.stooq import fetch_ohlc

        rows = fetch_ohlc("EURUSD=X", "1y")
        assert len(rows) == 2
        assert rows[0] == (1.12, 1.09, 1.11)
        assert rows[1] == (1.13, 1.10, 1.12)

    @patch("src.trading.scrapers.stooq.urllib.request.urlopen")
    def test_unknown_symbol_still_works(self, mock_urlopen):
        """Unknown symbol passes through as-is (no mapping)."""
        csv = (
            "Date,Open,High,Low,Close,Volume\n"
            "2024-01-02,50.0,55.0,49.0,53.0,3000\n"
        )
        mock_urlopen.return_value = _mock_urlopen_text(csv)

        from src.trading.scrapers.stooq import fetch_ohlc

        rows = fetch_ohlc("UNKNOWN_SYM", "30d")
        assert len(rows) == 1
        assert rows[0] == (55.0, 49.0, 53.0)

    @patch("src.trading.scrapers.stooq.urllib.request.urlopen")
    def test_malformed_csv_handled(self, mock_urlopen):
        """Rows with fewer columns or non-numeric data are skipped."""
        csv = (
            "Date,Open,High,Low,Close,Volume\n"
            "bad_row\n"
            "2024-01-02,1.10,1.12,1.09,1.11,1000\n"
            "2024-01-03,x,y,z,w,0\n"
        )
        mock_urlopen.return_value = _mock_urlopen_text(csv)

        from src.trading.scrapers.stooq import fetch_ohlc

        rows = fetch_ohlc("EURUSD=X")
        assert len(rows) == 1
        assert rows[0][2] == 1.11

    @patch("src.trading.scrapers.stooq.urllib.request.urlopen")
    def test_network_error_returns_empty(self, mock_urlopen):
        """Network error returns empty list."""
        mock_urlopen.side_effect = OSError("Connection refused")

        from src.trading.scrapers.stooq import fetch_ohlc

        result = fetch_ohlc("EURUSD=X")
        assert result == []


# ===========================================================================
# 3. Twelvedata — fetch_ohlc
# ===========================================================================


class TestTwelvedataScraper:
    """Tests for src.trading.scrapers.twelvedata."""

    @patch("src.trading.scrapers.twelvedata.time.sleep")
    @patch("src.trading.scrapers.twelvedata.urllib.request.urlopen")
    @patch("src.trading.scrapers.twelvedata.API_KEY", "test_key_123")
    def test_fetch_ohlc_success(self, mock_urlopen, mock_sleep):
        """Valid JSON with values returns (h, l, c) tuples in chronological order."""
        payload = {
            "status": "ok",
            "values": [
                {"datetime": "2024-01-03", "high": "1.15", "low": "1.09", "close": "1.14"},
                {"datetime": "2024-01-02", "high": "1.12", "low": "1.08", "close": "1.11"},
            ],
        }
        mock_urlopen.return_value = _mock_urlopen(json.dumps(payload).encode())

        from src.trading.scrapers.twelvedata import fetch_ohlc

        rows = fetch_ohlc("EURUSD=X", "1d", 30)
        assert len(rows) == 2
        # Values are reversed (oldest first)
        assert rows[0] == (1.12, 1.08, 1.11)
        assert rows[1] == (1.15, 1.09, 1.14)
        mock_sleep.assert_called_once_with(8)

    @patch("src.trading.scrapers.twelvedata.API_KEY", "")
    def test_no_api_key_returns_empty(self):
        """Without API key, returns empty list immediately."""
        from src.trading.scrapers.twelvedata import fetch_ohlc

        result = fetch_ohlc("EURUSD=X")
        assert result == []

    @patch("src.trading.scrapers.twelvedata.API_KEY", "test_key")
    def test_unsupported_symbol_returns_empty(self):
        """Symbol not in FREE_SYMBOLS returns empty list."""
        from src.trading.scrapers.twelvedata import fetch_ohlc

        result = fetch_ohlc("FAKE_SYMBOL")
        assert result == []

    @patch("src.trading.scrapers.twelvedata.urllib.request.urlopen")
    @patch("src.trading.scrapers.twelvedata.API_KEY", "test_key_123")
    def test_api_error_status(self, mock_urlopen):
        """API returning status='error' returns empty list."""
        payload = {"status": "error", "message": "Rate limit exceeded"}
        mock_urlopen.return_value = _mock_urlopen(json.dumps(payload).encode())

        from src.trading.scrapers.twelvedata import fetch_ohlc

        result = fetch_ohlc("EURUSD=X")
        assert result == []


# ===========================================================================
# 4. Finnhub — fetch_quote
# ===========================================================================


class TestFinnhubScraper:
    """Tests for src.trading.scrapers.finnhub."""

    @patch("src.trading.scrapers.finnhub.urllib.request.urlopen")
    @patch("src.trading.scrapers.finnhub.API_KEY", "test_key_abc")
    def test_fetch_quote_success(self, mock_urlopen):
        """Valid quote JSON returns (h, l, c) tuple."""
        payload = {"c": 5200.50, "h": 5250.00, "l": 5180.00, "o": 5190.00}
        mock_urlopen.return_value = _mock_urlopen(json.dumps(payload).encode())

        from src.trading.scrapers.finnhub import fetch_quote

        result = fetch_quote("^GSPC")
        assert result is not None
        assert result == (5250.00, 5180.00, 5200.50)

    @patch("src.trading.scrapers.finnhub.API_KEY", "")
    def test_no_api_key_returns_none(self):
        """Without API key, returns None immediately."""
        from src.trading.scrapers.finnhub import fetch_quote

        result = fetch_quote("^GSPC")
        assert result is None

    @patch("src.trading.scrapers.finnhub.API_KEY", "test_key")
    def test_unknown_symbol_returns_none(self):
        """Symbol not in QUOTE_MAP returns None."""
        from src.trading.scrapers.finnhub import fetch_quote

        result = fetch_quote("UNKNOWN_SYM")
        assert result is None

    @patch("src.trading.scrapers.finnhub.urllib.request.urlopen")
    @patch("src.trading.scrapers.finnhub.API_KEY", "test_key")
    def test_zero_values_returns_none(self, mock_urlopen):
        """Quote with zero values returns None (falsy check)."""
        payload = {"c": 0, "h": 0, "l": 0, "o": 0}
        mock_urlopen.return_value = _mock_urlopen(json.dumps(payload).encode())

        from src.trading.scrapers.finnhub import fetch_quote

        result = fetch_quote("^GSPC")
        assert result is None


# ===========================================================================
# 5. FRED — fetch_csv, fetch_api
# ===========================================================================


class TestFredScraper:
    """Tests for src.trading.scrapers.fred."""

    @patch("src.trading.scrapers.fred.urllib.request.urlopen")
    def test_fetch_csv_success(self, mock_urlopen):
        """Valid CSV returns latest non-dot float value."""
        csv = (
            "DATE,DGS10\n"
            "2024-01-02,4.25\n"
            "2024-01-03,4.30\n"
            "2024-01-04,.\n"
        )
        mock_urlopen.return_value = _mock_urlopen_text(csv)

        from src.trading.scrapers.fred import fetch_csv

        result = fetch_csv("DGS10")
        assert result == 4.30

    @patch("src.trading.scrapers.fred.urllib.request.urlopen")
    def test_fetch_csv_all_dots(self, mock_urlopen):
        """CSV where all values are '.' returns None."""
        csv = "DATE,DGS10\n2024-01-02,.\n2024-01-03,.\n"
        mock_urlopen.return_value = _mock_urlopen_text(csv)

        from src.trading.scrapers.fred import fetch_csv

        result = fetch_csv("DGS10")
        assert result is None

    @patch("src.trading.scrapers.fred.urllib.request.urlopen")
    def test_fetch_csv_network_error(self, mock_urlopen):
        """Network error returns None."""
        mock_urlopen.side_effect = OSError("timeout")

        from src.trading.scrapers.fred import fetch_csv

        result = fetch_csv("DGS10")
        assert result is None

    @patch("src.trading.scrapers.fred.urllib.request.urlopen")
    @patch("src.trading.scrapers.fred.API_KEY", "test_fred_key")
    def test_fetch_api_success(self, mock_urlopen):
        """Valid API JSON returns list of (date, float) tuples."""
        payload = {
            "observations": [
                {"date": "2024-01-03", "value": "4.30"},
                {"date": "2024-01-02", "value": "4.25"},
            ]
        }
        mock_urlopen.return_value = _mock_urlopen(json.dumps(payload).encode())

        from src.trading.scrapers.fred import fetch_api

        result = fetch_api("DGS10", limit=2)
        assert len(result) == 2
        # Reversed: oldest first
        assert result[0] == ("2024-01-02", 4.25)
        assert result[1] == ("2024-01-03", 4.30)

    @patch("src.trading.scrapers.fred.API_KEY", "")
    def test_fetch_api_no_key(self):
        """Without API key, fetch_api returns empty list."""
        from src.trading.scrapers.fred import fetch_api

        result = fetch_api("DGS10")
        assert result == []


# ===========================================================================
# 6. CNN Fear & Greed — fetch, classify
# ===========================================================================


class TestCnnFearGreedScraper:
    """Tests for src.trading.scrapers.cnn_fear_greed."""

    @patch("src.trading.scrapers.cnn_fear_greed.urllib.request.urlopen")
    def test_fetch_success(self, mock_urlopen):
        """Valid JSON returns dict with score and rating."""
        payload = {
            "fear_and_greed": {
                "score": 62.345,
                "rating": "Greed",
            }
        }
        mock_urlopen.return_value = _mock_urlopen(json.dumps(payload).encode())

        from src.trading.scrapers.cnn_fear_greed import fetch

        result = fetch()
        assert result is not None
        assert result["score"] == 62.3
        assert result["rating"] == "Greed"

    @patch("src.trading.scrapers.cnn_fear_greed.urllib.request.urlopen")
    def test_fetch_error_returns_none(self, mock_urlopen):
        """Network error returns None."""
        mock_urlopen.side_effect = urllib.error.URLError("DNS failed")

        from src.trading.scrapers.cnn_fear_greed import fetch

        result = fetch()
        assert result is None

    def test_classify_extreme_greed(self):
        """Score >= 75 is Extreme Greed."""
        from src.trading.scrapers.cnn_fear_greed import classify

        result = classify(80.0)
        assert result["label"] == "Extreme Greed"
        assert result["color"] == "bear"

    def test_classify_extreme_fear(self):
        """Score < 25 is Extreme Fear."""
        from src.trading.scrapers.cnn_fear_greed import classify

        result = classify(15.0)
        assert result["label"] == "Extreme Fear"
        assert result["color"] == "bull"


# ===========================================================================
# 7. Alpha Vantage — fetch_daily, fetch_forex
# ===========================================================================


class TestAlphaVantageScraper:
    """Tests for src.trading.scrapers.alpha_vantage."""

    @patch("src.trading.scrapers.alpha_vantage.time.sleep")
    @patch("src.trading.scrapers.alpha_vantage.urllib.request.urlopen")
    @patch("src.trading.scrapers.alpha_vantage.API_KEY", "test_av_key")
    def test_fetch_daily_success(self, mock_urlopen, mock_sleep):
        """Valid daily JSON returns (h, l, c) tuples sorted by date."""
        payload = {
            "Time Series (Daily)": {
                "2024-01-02": {
                    "1. open": "150.00",
                    "2. high": "155.00",
                    "3. low": "149.00",
                    "4. close": "153.00",
                },
                "2024-01-03": {
                    "1. open": "153.00",
                    "2. high": "158.00",
                    "3. low": "152.00",
                    "4. close": "157.00",
                },
            }
        }
        mock_urlopen.return_value = _mock_urlopen(json.dumps(payload).encode())

        from src.trading.scrapers.alpha_vantage import fetch_daily

        rows = fetch_daily("SPY")
        assert len(rows) == 2
        assert rows[0] == (155.0, 149.0, 153.0)
        assert rows[1] == (158.0, 152.0, 157.0)
        mock_sleep.assert_called_once_with(12)

    @patch("src.trading.scrapers.alpha_vantage.API_KEY", "")
    def test_fetch_daily_no_key(self):
        """Without API key, returns empty list."""
        from src.trading.scrapers.alpha_vantage import fetch_daily

        result = fetch_daily("SPY")
        assert result == []

    @patch("src.trading.scrapers.alpha_vantage.urllib.request.urlopen")
    @patch("src.trading.scrapers.alpha_vantage.API_KEY", "test_av_key")
    def test_fetch_forex_success(self, mock_urlopen):
        """Valid forex JSON returns float rate."""
        payload = {
            "Realtime Currency Exchange Rate": {
                "5. Exchange Rate": "1.0850",
            }
        }
        mock_urlopen.return_value = _mock_urlopen(json.dumps(payload).encode())

        from src.trading.scrapers.alpha_vantage import fetch_forex

        result = fetch_forex("EUR", "USD")
        assert result == 1.085

    @patch("src.trading.scrapers.alpha_vantage.API_KEY", "")
    def test_fetch_forex_no_key(self):
        """Without API key, fetch_forex returns None."""
        from src.trading.scrapers.alpha_vantage import fetch_forex

        result = fetch_forex("EUR", "USD")
        assert result is None

    @patch("src.trading.scrapers.alpha_vantage.time.sleep")
    @patch("src.trading.scrapers.alpha_vantage.urllib.request.urlopen")
    @patch("src.trading.scrapers.alpha_vantage.API_KEY", "test_av_key")
    def test_fetch_daily_network_error(self, mock_urlopen, mock_sleep):
        """Network error returns empty list."""
        mock_urlopen.side_effect = OSError("Connection timed out")

        from src.trading.scrapers.alpha_vantage import fetch_daily

        result = fetch_daily("SPY")
        assert result == []
