"""Unit tests for src.trading.scrapers.comex — COMEX warehouse inventory scraper."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from src.trading.scrapers.comex import (
    REPORT_IDS,
    _calc_stress_index,
    _fetch_metal,
    fetch,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_cme_response(rows: list[dict]) -> bytes:
    """Build a CME-like JSON response."""
    return json.dumps(rows).encode()


# ===== _calc_stress_index ==================================================


class TestCalcStressIndex:
    """Stress index formula: base = (1.0 - registered/total) * 80, capped 0-100."""

    def test_high_stress_low_registered(self):
        """If registered is small fraction of total, stress is high."""
        # registered=1000, total=5000 => ratio=0.2, base=(1-0.2)*80=64.0
        stress = _calc_stress_index(1000, 5000)
        assert stress == 64.0

    def test_low_stress_high_registered(self):
        """If registered is nearly all of total, stress is low."""
        # registered=4900, total=5000 => ratio=0.98, base=(1-0.98)*80=1.6
        stress = _calc_stress_index(4900, 5000)
        assert stress == 1.6

    def test_zero_total_returns_50(self):
        """Edge case: zero total inventory returns neutral 50.0."""
        stress = _calc_stress_index(0, 0)
        assert stress == 50.0

    def test_negative_total_returns_50(self):
        """Edge case: negative total returns neutral 50.0."""
        stress = _calc_stress_index(100, -1)
        assert stress == 50.0

    def test_all_registered_zero_stress(self):
        """If registered == total, stress is 0.0."""
        # registered=5000, total=5000 => ratio=1.0, base=0.0
        stress = _calc_stress_index(5000, 5000)
        assert stress == 0.0

    def test_zero_registered_max_stress_80(self):
        """If registered=0, stress = 80.0 (the formula cap via the ratio)."""
        # registered=0, total=5000 => ratio=0.0, base=80.0
        stress = _calc_stress_index(0, 5000)
        assert stress == 80.0

    def test_stress_capped_at_100(self):
        """Stress is capped at 100.0 even if formula exceeds it (shouldn't normally)."""
        # With the formula (1-ratio)*80, max is 80 when ratio=0
        # This is a guard-rail test
        stress = _calc_stress_index(0, 1)
        assert stress <= 100.0

    def test_stress_never_negative(self):
        """Stress is clamped at 0.0 minimum."""
        # registered > total shouldn't happen, but if it does:
        stress = _calc_stress_index(10000, 5000)
        # ratio = 2.0, base = (1-2.0)*80 = -80 => clamped to 0.0
        assert stress == 0.0


# ===== _fetch_metal ========================================================


class TestFetchMetal:
    """CME data parsing for a single metal."""

    @patch("src.trading.scrapers.comex.urllib.request.urlopen")
    def test_parses_cme_facility_rows(self, mock_urlopen):
        """Parses registered and eligible from CME facility rows."""
        rows = [
            {"registered": "1,000", "eligible": "2,000"},
            {"registered": "500", "eligible": "800"},
        ]
        ctx = MagicMock()
        ctx.__enter__ = lambda s: MagicMock(read=lambda: _make_cme_response(rows))
        ctx.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = ctx

        result = _fetch_metal("gold", 165, "20260327")
        assert result is not None
        assert result["metal"] == "gold"
        assert result["registered"] == 1500
        assert result["eligible"] == 2800
        assert result["total"] == 4300
        # coverage = 1500/4300*100 = 34.88%
        assert abs(result["coverage_pct"] - 34.88) < 0.1

    @patch("src.trading.scrapers.comex.urllib.request.urlopen")
    def test_handles_numeric_values(self, mock_urlopen):
        """Parses numeric (non-string) registered/eligible values."""
        rows = [{"registered": 1000, "eligible": 2000}]
        ctx = MagicMock()
        ctx.__enter__ = lambda s: MagicMock(read=lambda: _make_cme_response(rows))
        ctx.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = ctx

        result = _fetch_metal("silver", 166, "20260327")
        assert result is not None
        assert result["registered"] == 1000
        assert result["eligible"] == 2000

    @patch("src.trading.scrapers.comex.urllib.request.urlopen")
    def test_network_error_returns_none(self, mock_urlopen):
        """Network failures return None."""
        mock_urlopen.side_effect = ConnectionError("timeout")

        result = _fetch_metal("copper", 168, "20260327")
        assert result is None

    @patch("src.trading.scrapers.comex.urllib.request.urlopen")
    def test_empty_response_returns_zero_totals(self, mock_urlopen):
        """Empty response returns zero totals."""
        ctx = MagicMock()
        ctx.__enter__ = lambda s: MagicMock(read=lambda: _make_cme_response([]))
        ctx.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = ctx

        result = _fetch_metal("gold", 165, "20260327")
        assert result is not None
        assert result["registered"] == 0
        assert result["eligible"] == 0
        assert result["total"] == 0
        assert result["coverage_pct"] == 0


# ===== fetch() =============================================================


class TestFetch:
    """Full fetch with all metals."""

    @patch("src.trading.scrapers.comex._fetch_metal")
    def test_aggregates_all_metals(self, mock_fetch_metal):
        """Fetches all three metals and computes aggregate stress."""
        mock_fetch_metal.side_effect = [
            {"metal": "gold", "registered": 1000, "eligible": 2000, "total": 3000, "coverage_pct": 33.33},
            {"metal": "silver", "registered": 2000, "eligible": 1000, "total": 3000, "coverage_pct": 66.67},
            {"metal": "copper", "registered": 500, "eligible": 500, "total": 1000, "coverage_pct": 50.0},
        ]

        result = fetch()
        assert result["gold"] is not None
        assert result["silver"] is not None
        assert result["copper"] is not None
        assert "stress_index" in result
        assert "fetched_at" in result
        # Aggregate: registered=3500, total=7000, stress = (1-0.5)*80 = 40.0
        assert result["stress_index"] == 40.0

    @patch("src.trading.scrapers.comex._fetch_metal")
    def test_partial_failure_still_returns(self, mock_fetch_metal):
        """If one metal fails, others still populate and stress is calculated."""
        mock_fetch_metal.side_effect = [
            {"metal": "gold", "registered": 1000, "eligible": 2000, "total": 3000, "coverage_pct": 33.33},
            None,  # silver fails
            None,  # copper fails
        ]

        result = fetch()
        assert result["gold"] is not None
        assert result["silver"] is None
        assert result["copper"] is None
        assert result["stress_index"] > 0

    @patch("src.trading.scrapers.comex._fetch_metal")
    def test_all_fail_returns_default(self, mock_fetch_metal):
        """If all metals fail, stress_index defaults to 50.0 (zero total)."""
        mock_fetch_metal.return_value = None

        result = fetch()
        assert result["gold"] is None
        assert result["silver"] is None
        assert result["copper"] is None
        assert result["stress_index"] == 50.0
