"""Unit tests for src.analysis.adr_calculator — Average Daily Range."""

from __future__ import annotations

import pytest

from src.analysis.adr_calculator import (
    ADRResult,
    calculate_adr,
    calculate_adr_batch,
    to_dict,
)


class TestCalculateADR:
    """calculate_adr computation tests."""

    def test_basic_calculation(self):
        """Simple 3-day ADR calculation."""
        highs = [1.10, 1.12, 1.11]
        lows = [1.08, 1.09, 1.09]
        result = calculate_adr("EURUSD", highs, lows, 1.10, period=3)
        # Ranges: 0.02, 0.03, 0.02 -> mean = 0.02333
        assert result.instrument == "EURUSD"
        assert abs(result.adr - 0.02333) < 0.001
        assert result.days_used == 3
        assert result.current_price == 1.10

    def test_adr_percentage(self):
        """ADR percentage is correctly calculated."""
        highs = [100.0, 102.0, 101.0]
        lows = [98.0, 99.0, 99.0]
        result = calculate_adr("SPX", highs, lows, 100.0, period=3)
        # Ranges: 2, 3, 2 -> mean = 2.333
        # ADR% = 2.333 / 100 * 100 = 2.33
        assert abs(result.adr_pct - 2.33) < 0.1

    def test_period_truncation(self):
        """Only last N days are used when period < len(data)."""
        highs = [100.0, 110.0, 105.0, 102.0]
        lows = [90.0, 100.0, 100.0, 100.0]
        result = calculate_adr("TEST", highs, lows, 101.0, period=2)
        # Last 2 days: ranges 5, 2 -> mean = 3.5
        assert result.days_used == 2
        assert abs(result.adr - 3.5) < 0.001

    def test_period_larger_than_data(self):
        """Period > data length uses all available data."""
        highs = [100.0, 102.0]
        lows = [98.0, 99.0]
        result = calculate_adr("TEST", highs, lows, 101.0, period=20)
        assert result.days_used == 2

    def test_zero_current_price(self):
        """Zero current price -> adr_pct is 0."""
        result = calculate_adr("TEST", [10.0], [5.0], 0.0, period=1)
        assert result.adr_pct == 0.0
        assert result.adr == 5.0

    def test_empty_raises_valueerror(self):
        """Empty data raises ValueError."""
        with pytest.raises(ValueError, match="No price data"):
            calculate_adr("TEST", [], [], 100.0)

    def test_mismatched_lengths_raises_valueerror(self):
        """Different-length highs/lows raises ValueError."""
        with pytest.raises(ValueError, match="same length"):
            calculate_adr("TEST", [1.0, 2.0], [1.0], 1.5)

    def test_small_forex_pair(self):
        """Forex pair with 5-decimal precision."""
        highs = [1.08500, 1.08700, 1.08600]
        lows = [1.08200, 1.08300, 1.08100]
        result = calculate_adr("EURUSD", highs, lows, 1.08500, period=3)
        # Ranges: 0.003, 0.004, 0.005 -> mean = 0.004
        assert abs(result.adr - 0.004) < 0.0001

    def test_result_is_named_tuple(self):
        """ADRResult has correct fields."""
        result = calculate_adr("GOLD", [2000.0], [1980.0], 1990.0)
        assert isinstance(result, ADRResult)
        assert result.instrument == "GOLD"


class TestCalculateADRBatch:
    """calculate_adr_batch tests."""

    def test_multiple_instruments(self):
        """Batch calculation for multiple instruments."""
        data = [
            {"instrument": "EURUSD", "highs": [1.10, 1.12], "lows": [1.08, 1.09], "current_price": 1.10},
            {"instrument": "GOLD", "highs": [2000.0, 2020.0], "lows": [1980.0, 1990.0], "current_price": 2010.0},
        ]
        results = calculate_adr_batch(data)
        assert len(results) == 2

    def test_sorted_by_adr_pct_descending(self):
        """Results are sorted by ADR% descending."""
        data = [
            {"instrument": "LOW_VOL", "highs": [100.0], "lows": [99.5], "current_price": 100.0},
            {"instrument": "HIGH_VOL", "highs": [100.0], "lows": [90.0], "current_price": 95.0},
        ]
        results = calculate_adr_batch(data)
        assert results[0].instrument == "HIGH_VOL"

    def test_skips_invalid_data(self):
        """Invalid entries are skipped, not errored."""
        data = [
            {"instrument": "GOOD", "highs": [100.0], "lows": [98.0], "current_price": 99.0},
            {"instrument": "BAD", "highs": [], "lows": [], "current_price": 0.0},
        ]
        results = calculate_adr_batch(data)
        assert len(results) == 1
        assert results[0].instrument == "GOOD"

    def test_empty_input(self):
        """Empty input returns empty list."""
        assert calculate_adr_batch([]) == []


class TestToDict:
    """to_dict serialization tests."""

    def test_roundtrip(self):
        result = calculate_adr("TEST", [100.0, 102.0], [98.0, 99.0], 100.0)
        d = to_dict(result)
        assert d["instrument"] == "TEST"
        assert "adr" in d
        assert "adr_pct" in d
        assert "current_price" in d
        assert "days_used" in d
