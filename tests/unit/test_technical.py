"""Unit tests for src.analysis.technical — calc_atr, calc_ema, to_4h."""

import pytest

from src.analysis.technical import calc_atr, calc_ema, to_4h
from src.core.models import OhlcBar


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _row(h: float, l: float, c: float) -> tuple[float, float, float]:
    return (h, l, c)


def _ohlc(h: float, l: float, c: float) -> OhlcBar:
    return OhlcBar(high=h, low=l, close=c)


# ===== calc_atr =============================================================

class TestCalcAtr:

    def test_basic_15_rows(self):
        """15 rows with n=14 (minimum for default) should return a float."""
        rows = [_row(100 + i, 90 + i, 95 + i) for i in range(15)]
        result = calc_atr(rows, n=14)
        assert isinstance(result, float)
        assert result > 0

    def test_exact_n_plus_1_rows(self):
        """Exactly n+1 rows should still produce a result."""
        rows = [_row(100 + i, 90 + i, 95 + i) for i in range(15)]
        result = calc_atr(rows, n=14)
        assert result is not None

    def test_insufficient_rows(self):
        """14 rows for n=14 (needs 15) -> None."""
        rows = [_row(100 + i, 90 + i, 95 + i) for i in range(14)]
        result = calc_atr(rows, n=14)
        assert result is None

    def test_empty_rows(self):
        result = calc_atr([], n=14)
        assert result is None

    def test_one_row(self):
        result = calc_atr([_row(10, 8, 9)], n=14)
        assert result is None

    def test_custom_n_5(self):
        rows = [_row(100 + i, 90 + i, 95 + i) for i in range(6)]
        result = calc_atr(rows, n=5)
        assert isinstance(result, float)

    def test_known_values(self):
        """Hand-calculated: 3 rows, n=2.
        Row0: (10,8,9)
        Row1: (11,7,10) -> TR = max(11-7, |11-9|, |7-9|) = max(4,2,2) = 4
        Row2: (12,6,11) -> TR = max(12-6, |12-10|, |6-10|) = max(6,2,4) = 6
        ATR(2) = (4+6)/2 = 5.0
        """
        rows = [_row(10, 8, 9), _row(11, 7, 10), _row(12, 6, 11)]
        result = calc_atr(rows, n=2)
        assert result == pytest.approx(5.0)

    def test_ohlcbar_compat(self):
        """Should also work with OhlcBar objects."""
        rows = [_ohlc(100 + i, 90 + i, 95 + i) for i in range(15)]
        result = calc_atr(rows, n=14)
        assert isinstance(result, float)
        assert result > 0


# ===== calc_ema =============================================================

class TestCalcEma:

    def test_basic_10_plus_values(self):
        """10+ values with default n=9 should return a float."""
        closes = [float(100 + i) for i in range(12)]
        result = calc_ema(closes, n=9)
        assert isinstance(result, float)

    def test_insufficient_values(self):
        """Fewer than n+1 values -> None."""
        closes = [float(100 + i) for i in range(9)]  # need 10 for n=9
        result = calc_ema(closes, n=9)
        assert result is None

    def test_empty(self):
        result = calc_ema([], n=9)
        assert result is None

    def test_known_values(self):
        """Seed = mean of first n values, then k=2/(n+1).
        n=3, closes=[10, 20, 30, 40]
        seed = (10+20+30)/3 = 20.0
        k = 2/(3+1) = 0.5
        EMA = 40*0.5 + 20.0*0.5 = 30.0
        """
        closes = [10.0, 20.0, 30.0, 40.0]
        result = calc_ema(closes, n=3)
        assert result == pytest.approx(30.0)

    def test_exactly_n_plus_1_values(self):
        """Exactly n+1 should work (seed from first n, one EMA step)."""
        closes = [10.0, 20.0, 30.0, 40.0]  # n=3, 4 values = n+1
        result = calc_ema(closes, n=3)
        assert result is not None


# ===== to_4h ================================================================

class TestTo4h:

    def test_basic_8_rows_gives_2_bars(self):
        """8 1h rows -> 2 4h bars."""
        rows = [_row(100 + i, 90 + i, 95 + i) for i in range(8)]
        result = to_4h(rows)
        assert len(result) == 2

    def test_correct_grouping(self):
        """h = max of highs, l = min of lows, c = last close in group."""
        rows = [
            _row(10, 2, 5),
            _row(15, 3, 7),
            _row(12, 1, 6),
            _row(11, 4, 8),
        ]
        result = to_4h(rows)
        assert len(result) == 1
        bar = result[0]
        assert bar[0] == 15   # max high
        assert bar[1] == 1    # min low
        assert bar[2] == 8    # last close

    def test_remainder_dropped(self):
        """9 rows -> 2 bars (remainder 1 dropped)."""
        rows = [_row(100 + i, 90 + i, 95 + i) for i in range(9)]
        result = to_4h(rows)
        assert len(result) == 2

    def test_less_than_4_rows_empty(self):
        """Fewer than 4 rows -> no bars."""
        rows = [_row(10, 8, 9), _row(11, 7, 10), _row(12, 6, 11)]
        result = to_4h(rows)
        assert len(result) == 0

    def test_ohlcbar_input(self):
        """Should work with OhlcBar objects too."""
        rows = [_ohlc(100 + i, 90 + i, 95 + i) for i in range(8)]
        result = to_4h(rows)
        assert len(result) == 2
