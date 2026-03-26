"""Unit tests for src.analysis.technical — calc_atr, calc_ema, to_4h."""

import pytest

from src.analysis.technical import calc_atr, calc_ema, to_4h
from src.core.models import OhlcBar

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _row(h: float, lo: float, c: float) -> tuple[float, float, float]:
    return (h, lo, c)


def _ohlc(h: float, lo: float, c: float) -> OhlcBar:
    return OhlcBar(high=h, low=lo, close=c)


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
        assert bar[0] == 15  # max high
        assert bar[1] == 1  # min low
        assert bar[2] == 8  # last close

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


# ===== Edge case tests added by Agent D3 =====================================


class TestCalcAtrEdgeCases:
    """Edge cases: zero-range bars, single period, all-same prices."""

    def test_zero_range_bars(self):
        """Bars where high==low==close => TR=0 for all => ATR=0."""
        rows = [_row(100, 100, 100) for _ in range(20)]
        result = calc_atr(rows, n=14)
        assert result == pytest.approx(0.0)

    def test_n_equals_1(self):
        """n=1 requires 2 rows, should return the single TR value."""
        rows = [_row(10, 8, 9), _row(12, 6, 11)]
        result = calc_atr(rows, n=1)
        # TR = max(12-6, |12-9|, |6-9|) = max(6, 3, 3) = 6
        assert result == pytest.approx(6.0)

    def test_all_same_close_different_ranges(self):
        """Close always the same but different H/L ranges."""
        rows = [_row(110, 90, 100), _row(115, 85, 100), _row(120, 80, 100)]
        result = calc_atr(rows, n=2)
        # Row1 TR: max(115-85, |115-100|, |85-100|) = max(30, 15, 15) = 30
        # Row2 TR: max(120-80, |120-100|, |80-100|) = max(40, 20, 20) = 40
        assert result == pytest.approx(35.0)

    def test_two_rows_n_1(self):
        """Exactly 2 rows with n=1 (minimum)."""
        rows = [_row(10, 8, 9), _row(11, 7, 10)]
        result = calc_atr(rows, n=1)
        # TR = max(11-7, |11-9|, |7-9|) = max(4, 2, 2) = 4
        assert result == pytest.approx(4.0)

    def test_large_n_requires_many_rows(self):
        """n=100 requires 101 rows — 100 rows should return None."""
        rows = [_row(100 + i, 90 + i, 95 + i) for i in range(100)]
        assert calc_atr(rows, n=100) is None

    def test_large_n_with_enough_rows(self):
        """n=100 with 101 rows should succeed."""
        rows = [_row(100 + i, 90 + i, 95 + i) for i in range(101)]
        result = calc_atr(rows, n=100)
        assert isinstance(result, float)
        assert result > 0


class TestCalcEmaEdgeCases:
    """Edge cases: constant values, single step, n=1."""

    def test_constant_values(self):
        """All same values => EMA == that value."""
        closes = [50.0] * 20
        result = calc_ema(closes, n=9)
        assert result == pytest.approx(50.0)

    def test_n_equals_1(self):
        """n=1 requires 2 values. Seed = first value, k=2/2=1.0, EMA = second value."""
        closes = [10.0, 20.0]
        result = calc_ema(closes, n=1)
        # seed = 10.0/1 = 10.0, k = 2/2 = 1.0
        # EMA = 20*1.0 + 10*(1-1.0) = 20.0
        assert result == pytest.approx(20.0)

    def test_single_value(self):
        """Single value with any n > 0 => None (needs n+1)."""
        assert calc_ema([100.0], n=1) is None
        assert calc_ema([100.0], n=9) is None

    def test_two_values_n_1(self):
        """Two values with n=1 => valid."""
        result = calc_ema([5.0, 15.0], n=1)
        assert isinstance(result, float)

    def test_descending_values(self):
        """Descending sequence — EMA should be less than seed."""
        closes = [100.0, 90.0, 80.0, 70.0, 60.0, 50.0, 40.0, 30.0, 20.0, 10.0]
        result = calc_ema(closes, n=3)
        # seed = (100+90+80)/3 = 90, then EMA chases down
        assert isinstance(result, float)
        assert result < 90.0  # EMA lags below seed for descending

    def test_large_n_insufficient_data(self):
        """n=50 with 50 values => None (needs 51)."""
        closes = [float(i) for i in range(50)]
        assert calc_ema(closes, n=50) is None


class TestTo4hEdgeCases:
    """Edge cases: empty, exact multiples, single group."""

    def test_empty_rows(self):
        """No rows => no 4h bars."""
        assert to_4h([]) == []

    def test_one_row(self):
        """1 row => no complete group."""
        assert to_4h([_row(10, 8, 9)]) == []

    def test_exactly_4_rows(self):
        """4 rows => exactly 1 bar."""
        rows = [_row(10, 2, 5), _row(15, 3, 7), _row(12, 1, 6), _row(11, 4, 8)]
        result = to_4h(rows)
        assert len(result) == 1

    def test_negative_prices(self):
        """Negative prices (e.g., futures spreads) should work."""
        rows = [_row(-5, -15, -10), _row(-3, -12, -8), _row(-4, -14, -9), _row(-2, -11, -7)]
        result = to_4h(rows)
        assert len(result) == 1
        assert result[0][0] == -2  # max high
        assert result[0][1] == -15  # min low
        assert result[0][2] == -7  # last close

    def test_ohlcbar_single_group(self):
        """OhlcBar objects with exactly 4 bars."""
        rows = [_ohlc(10, 2, 5), _ohlc(15, 3, 7), _ohlc(12, 1, 6), _ohlc(11, 4, 8)]
        result = to_4h(rows)
        assert len(result) == 1
        assert result[0] == (15, 1, 8)

    def test_zero_range_bars(self):
        """Bars with h==l==c => grouped bar also has h==l==c."""
        rows = [_row(50, 50, 50)] * 4
        result = to_4h(rows)
        assert len(result) == 1
        assert result[0] == (50, 50, 50)
