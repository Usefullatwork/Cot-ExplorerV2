"""Unit tests for src.data.providers.stooq — CSV parsing, date range, error handling."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from src.core.models import OhlcBar
from src.data.providers.stooq import STOOQ_DAYS, STOOQ_MAP, StooqProvider

# ===== StooqProvider basics ===================================================


class TestStooqProviderBasics:
    """Initialization and availability."""

    def test_name(self):
        p = StooqProvider()
        assert p.name == "stooq"

    def test_is_available(self):
        """No API key required — always available."""
        p = StooqProvider()
        assert p.is_available() is True


# ===== STOOQ_MAP =============================================================


class TestStooqMap:
    """Verify the symbol lookup table is well-formed."""

    def test_known_symbols_present(self):
        assert "EURUSD=X" in STOOQ_MAP
        assert "GC=F" in STOOQ_MAP
        assert "^VIX" in STOOQ_MAP

    def test_unknown_symbol_missing(self):
        assert "FAKE=X" not in STOOQ_MAP


# ===== _fetch — CSV parsing ===================================================


class TestFetchCsvParsing:
    """Mock urlopen to inject CSV payloads and verify OhlcBar parsing."""

    def _make_provider(self) -> StooqProvider:
        p = StooqProvider()
        # Reset circuit breaker so retries don't interfere
        p.circuit_breaker._failure_count = 0
        p.circuit_breaker._state = "closed"
        return p

    def _mock_urlopen(self, csv_text: str):
        """Return a context-manager mock for urllib.request.urlopen."""
        cm = MagicMock()
        cm.__enter__ = MagicMock(return_value=MagicMock(read=MagicMock(return_value=csv_text.encode())))
        cm.__exit__ = MagicMock(return_value=False)
        return cm

    @patch("src.data.providers.stooq.urllib.request.urlopen")
    def test_valid_csv_returns_bars(self, mock_urlopen):
        csv = (
            "Date,Open,High,Low,Close,Volume\n"
            "2024-01-02,1.10,1.12,1.09,1.11,1000\n"
            "2024-01-03,1.11,1.13,1.10,1.12,2000\n"
        )
        mock_urlopen.return_value = self._mock_urlopen(csv)
        p = self._make_provider()
        bars = p._fetch("EURUSD=X", "1y")
        assert len(bars) == 2
        assert isinstance(bars[0], OhlcBar)
        assert bars[0].high == 1.12
        assert bars[0].low == 1.09
        assert bars[0].close == 1.11
        assert bars[1].high == 1.13

    @patch("src.data.providers.stooq.urllib.request.urlopen")
    def test_header_only_returns_empty(self, mock_urlopen):
        """CSV with only a header row should produce no bars."""
        csv = "Date,Open,High,Low,Close,Volume\n"
        mock_urlopen.return_value = self._mock_urlopen(csv)
        p = self._make_provider()
        bars = p._fetch("EURUSD=X", "1y")
        assert bars == []

    @patch("src.data.providers.stooq.urllib.request.urlopen")
    def test_malformed_rows_skipped(self, mock_urlopen):
        """Rows with fewer than 5 columns or non-numeric values are skipped."""
        csv = "Date,Open,High,Low,Close,Volume\nbad_row\n2024-01-02,1.10,1.12,1.09,1.11,1000\n2024-01-03,x,y,z,w,0\n"
        mock_urlopen.return_value = self._mock_urlopen(csv)
        p = self._make_provider()
        bars = p._fetch("EURUSD=X", "1y")
        assert len(bars) == 1
        assert bars[0].close == 1.11

    @patch("src.data.providers.stooq.urllib.request.urlopen")
    def test_zero_values_skipped(self, mock_urlopen):
        """Rows where h, l, or c is zero are skipped (falsy check)."""
        csv = "Date,Open,High,Low,Close,Volume\n2024-01-02,1.10,0,1.09,1.11,1000\n2024-01-03,1.10,1.12,1.09,1.11,500\n"
        mock_urlopen.return_value = self._mock_urlopen(csv)
        p = self._make_provider()
        bars = p._fetch("EURUSD=X", "1y")
        assert len(bars) == 1
        assert bars[0].high == 1.12

    def test_unknown_symbol_returns_empty(self):
        """If the symbol is not in STOOQ_MAP, _fetch returns [] without network."""
        p = self._make_provider()
        bars = p._fetch("UNKNOWN_SYMBOL", "1y")
        assert bars == []


# ===== Date range mapping =====================================================


class TestDateRange:
    """Verify STOOQ_DAYS mapping and default fallback."""

    def test_1y_days(self):
        assert STOOQ_DAYS["1y"] == 400

    def test_30d_days(self):
        assert STOOQ_DAYS["30d"] == 35

    def test_5d_days(self):
        assert STOOQ_DAYS["5d"] == 7

    @patch("src.data.providers.stooq.urllib.request.urlopen")
    def test_unknown_range_defaults_to_400(self, mock_urlopen):
        """An unrecognized range_ key falls back to 400 days (same as 1y)."""
        csv = "Date,Open,High,Low,Close,Volume\n2024-01-02,1.10,1.12,1.09,1.11,1000\n"
        cm = MagicMock()
        cm.__enter__ = MagicMock(return_value=MagicMock(read=MagicMock(return_value=csv.encode())))
        cm.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = cm
        p = StooqProvider()
        bars = p._fetch("EURUSD=X", "99y")
        # Should succeed (uses default 400 days)
        assert len(bars) == 1


# ===== fetch_stooq — retry/error wrapping ====================================


class TestFetchStooqPublic:
    """Test the public fetch_stooq method that wraps _fetch with retry."""

    @patch("src.data.providers.stooq.urllib.request.urlopen")
    def test_network_error_returns_empty(self, mock_urlopen):
        """On network failure, fetch_stooq catches and returns []."""
        mock_urlopen.side_effect = OSError("Connection refused")
        p = StooqProvider()
        result = p.fetch_stooq("EURUSD=X", "1y")
        assert result == []

    @patch("src.data.providers.stooq.urllib.request.urlopen")
    def test_successful_fetch(self, mock_urlopen):
        csv = "Date,Open,High,Low,Close,Volume\n2024-01-02,1.10,1.12,1.09,1.11,1000\n"
        cm = MagicMock()
        cm.__enter__ = MagicMock(return_value=MagicMock(read=MagicMock(return_value=csv.encode())))
        cm.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = cm
        p = StooqProvider()
        bars = p.fetch_stooq("EURUSD=X", "1y")
        assert len(bars) == 1
        assert bars[0].close == 1.11


# ===== Module-level convenience function ======================================


class TestModuleLevelFunction:
    """Test the drop-in fetch_stooq() module function."""

    @patch("src.data.providers.stooq.urllib.request.urlopen")
    def test_module_function_delegates(self, mock_urlopen):
        csv = "Date,Open,High,Low,Close,Volume\n2024-06-01,100.0,105.0,99.0,103.0,5000\n"
        cm = MagicMock()
        cm.__enter__ = MagicMock(return_value=MagicMock(read=MagicMock(return_value=csv.encode())))
        cm.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = cm
        from src.data.providers.stooq import fetch_stooq

        bars = fetch_stooq("GC=F", "30d")
        assert len(bars) == 1
        assert bars[0].high == 105.0
