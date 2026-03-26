"""Unit tests for src.data.providers.yahoo — YahooProvider and module-level fetch_yahoo."""

from __future__ import annotations

import json
import urllib.error
from unittest.mock import MagicMock, patch

from src.core.models import OhlcBar
from src.data.providers.yahoo import YahooProvider, fetch_yahoo

# ---------------------------------------------------------------------------
# Helpers — reusable Yahoo JSON response builders
# ---------------------------------------------------------------------------


def _make_yahoo_json(
    highs: list,
    lows: list,
    closes: list,
    timestamps: list | None = None,
) -> bytes:
    """Build a minimal Yahoo Finance v8 JSON response as bytes."""
    if timestamps is None:
        timestamps = list(range(len(highs)))
    payload = {
        "chart": {
            "result": [
                {
                    "timestamp": timestamps,
                    "indicators": {"quote": [{"high": highs, "low": lows, "close": closes}]},
                }
            ],
            "error": None,
        }
    }
    return json.dumps(payload).encode()


def _mock_urlopen(data: bytes):
    """Return a context-manager mock that yields .read() -> data."""
    cm = MagicMock()
    cm.__enter__ = MagicMock(return_value=cm)
    cm.__exit__ = MagicMock(return_value=False)
    cm.read.return_value = data
    return cm


# ---------------------------------------------------------------------------
# YahooProvider instantiation
# ---------------------------------------------------------------------------


class TestYahooProviderInit:
    """Basic construction and availability."""

    def test_name_is_yahoo(self):
        p = YahooProvider()
        assert p.name == "yahoo"

    def test_is_always_available(self):
        p = YahooProvider()
        assert p.is_available() is True


# ---------------------------------------------------------------------------
# OHLC parsing
# ---------------------------------------------------------------------------


class TestOhlcParsing:
    """_fetch correctly parses Yahoo JSON into OhlcBar objects."""

    @patch("src.data.providers.yahoo.urllib.request.urlopen")
    def test_basic_ohlc_parse(self, mock_urlopen):
        """Three valid bars produce three OhlcBar objects with correct values."""
        data = _make_yahoo_json(
            highs=[1.10, 1.12, 1.15],
            lows=[1.05, 1.08, 1.09],
            closes=[1.07, 1.11, 1.14],
        )
        mock_urlopen.return_value = _mock_urlopen(data)

        p = YahooProvider()
        bars = p._fetch("EURUSD=X", "1d", "1y")

        assert len(bars) == 3
        assert all(isinstance(b, OhlcBar) for b in bars)
        assert bars[0].high == 1.10
        assert bars[0].low == 1.05
        assert bars[0].close == 1.07
        assert bars[2].high == 1.15

    @patch("src.data.providers.yahoo.urllib.request.urlopen")
    def test_none_values_filtered(self, mock_urlopen):
        """Bars with None in high/low/close are skipped."""
        data = _make_yahoo_json(
            highs=[1.10, None, 1.15],
            lows=[1.05, 1.08, None],
            closes=[1.07, 1.11, 1.14],
        )
        mock_urlopen.return_value = _mock_urlopen(data)

        p = YahooProvider()
        bars = p._fetch("EURUSD=X", "1d", "5d")

        assert len(bars) == 1
        assert bars[0].high == 1.10

    @patch("src.data.providers.yahoo.urllib.request.urlopen")
    def test_zero_values_filtered(self, mock_urlopen):
        """Bars where any of h/l/c is 0 are filtered (falsy check)."""
        data = _make_yahoo_json(
            highs=[1.10, 0, 1.15],
            lows=[1.05, 1.08, 1.09],
            closes=[1.07, 1.11, 1.14],
        )
        mock_urlopen.return_value = _mock_urlopen(data)

        p = YahooProvider()
        bars = p._fetch("EURUSD=X", "1d", "1y")

        # Second bar has high=0, which is falsy -> filtered
        assert len(bars) == 2

    @patch("src.data.providers.yahoo.urllib.request.urlopen")
    def test_as_tuple(self, mock_urlopen):
        """OhlcBar.as_tuple returns (h, l, c)."""
        data = _make_yahoo_json(
            highs=[100.0],
            lows=[90.0],
            closes=[95.0],
        )
        mock_urlopen.return_value = _mock_urlopen(data)

        p = YahooProvider()
        bars = p._fetch("GC=F", "1d", "1y")

        assert bars[0].as_tuple() == (100.0, 90.0, 95.0)


# ---------------------------------------------------------------------------
# Empty / edge-case data
# ---------------------------------------------------------------------------


class TestEmptyData:
    """Behaviour when Yahoo returns empty or minimal data."""

    @patch("src.data.providers.yahoo.urllib.request.urlopen")
    def test_empty_arrays(self, mock_urlopen):
        """Empty high/low/close arrays -> empty bar list."""
        data = _make_yahoo_json(highs=[], lows=[], closes=[])
        mock_urlopen.return_value = _mock_urlopen(data)

        p = YahooProvider()
        bars = p._fetch("^GSPC", "1d", "1y")
        assert bars == []

    @patch("src.data.providers.yahoo.urllib.request.urlopen")
    def test_all_none_values(self, mock_urlopen):
        """All bars are None -> empty list."""
        data = _make_yahoo_json(
            highs=[None, None],
            lows=[None, None],
            closes=[None, None],
        )
        mock_urlopen.return_value = _mock_urlopen(data)

        p = YahooProvider()
        bars = p._fetch("EURUSD=X", "1d", "1y")
        assert bars == []


# ---------------------------------------------------------------------------
# URL construction
# ---------------------------------------------------------------------------


class TestUrlConstruction:
    """Verify the correct URL and headers are built."""

    @patch("src.data.providers.yahoo.urllib.request.urlopen")
    @patch("src.data.providers.yahoo.urllib.request.Request")
    def test_url_includes_symbol_interval_range(self, mock_request, mock_urlopen):
        """URL encodes symbol, interval, and range correctly."""
        data = _make_yahoo_json(highs=[1.0], lows=[0.9], closes=[0.95])
        mock_urlopen.return_value = _mock_urlopen(data)
        mock_request.return_value = MagicMock()  # Request object

        p = YahooProvider()
        p._fetch("EURUSD=X", "15m", "5d")

        call_args = mock_request.call_args
        url = call_args[0][0]
        assert "EURUSD%3DX" in url  # = is encoded as %3D
        assert "interval=15m" in url
        assert "range=5d" in url

    @patch("src.data.providers.yahoo.urllib.request.urlopen")
    @patch("src.data.providers.yahoo.urllib.request.Request")
    def test_special_symbol_encoding(self, mock_request, mock_urlopen):
        """Caret in ^GSPC is URL-encoded."""
        data = _make_yahoo_json(highs=[1.0], lows=[0.9], closes=[0.95])
        mock_urlopen.return_value = _mock_urlopen(data)
        mock_request.return_value = MagicMock()

        p = YahooProvider()
        p._fetch("^GSPC", "1d", "1y")

        url = mock_request.call_args[0][0]
        assert "%5EGSPC" in url  # ^ is encoded as %5E


# ---------------------------------------------------------------------------
# Error scenarios
# ---------------------------------------------------------------------------


class TestErrorScenarios:
    """Network failures, bad JSON, and circuit breaker integration."""

    @patch("src.data.providers.yahoo.urllib.request.urlopen")
    def test_network_error_returns_empty(self, mock_urlopen):
        """URLError (no network) -> fetch_yahoo returns [] (retry exhausted)."""
        mock_urlopen.side_effect = urllib.error.URLError("no network")

        p = YahooProvider()
        # Reset circuit breaker to clean state
        p.circuit_breaker._failure_count = 0
        p.circuit_breaker._state = "closed"
        result = p.fetch_yahoo("EURUSD=X")
        assert result == []

    @patch("src.data.providers.yahoo.urllib.request.urlopen")
    def test_http_error_returns_empty(self, mock_urlopen):
        """HTTP 404 -> fetch_yahoo returns []."""
        mock_urlopen.side_effect = urllib.error.HTTPError(
            url="http://x",
            code=404,
            msg="Not Found",
            hdrs={},
            fp=None,
        )

        p = YahooProvider()
        p.circuit_breaker._failure_count = 0
        p.circuit_breaker._state = "closed"
        result = p.fetch_yahoo("INVALID_SYMBOL")
        assert result == []

    @patch("src.data.providers.yahoo.urllib.request.urlopen")
    def test_malformed_json_returns_empty(self, mock_urlopen):
        """Invalid JSON -> fetch_yahoo returns []."""
        cm = _mock_urlopen(b"not valid json at all")
        mock_urlopen.return_value = cm

        p = YahooProvider()
        p.circuit_breaker._failure_count = 0
        p.circuit_breaker._state = "closed"
        result = p.fetch_yahoo("EURUSD=X")
        assert result == []

    @patch("src.data.providers.yahoo.urllib.request.urlopen")
    def test_missing_keys_returns_empty(self, mock_urlopen):
        """JSON with missing 'chart' key -> fetch_yahoo returns []."""
        cm = _mock_urlopen(json.dumps({"data": []}).encode())
        mock_urlopen.return_value = cm

        p = YahooProvider()
        p.circuit_breaker._failure_count = 0
        p.circuit_breaker._state = "closed"
        result = p.fetch_yahoo("EURUSD=X")
        assert result == []


# ---------------------------------------------------------------------------
# Module-level convenience function
# ---------------------------------------------------------------------------


class TestModuleLevelFetchYahoo:
    """The module-level fetch_yahoo delegates to the singleton provider."""

    @patch("src.data.providers.yahoo._provider")
    def test_delegates_to_provider(self, mock_provider):
        """fetch_yahoo() calls _provider.fetch_yahoo with correct args."""
        mock_provider.fetch_yahoo.return_value = [OhlcBar(high=1.1, low=1.0, close=1.05)]
        result = fetch_yahoo("GC=F", interval="60m", range_="1mo")

        mock_provider.fetch_yahoo.assert_called_once_with(
            "GC=F",
            "60m",
            "1mo",
        )
        assert len(result) == 1
        assert result[0].high == 1.1
