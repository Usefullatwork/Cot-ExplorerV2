"""Unit tests for src.trading.bot.entry_logic — zone proximity, candle confirmation, entry orchestration."""

from __future__ import annotations

from src.trading.bot.entry_logic import (
    EntryResult,
    check_candle_confirmation,
    check_ema9_filter,
    check_zone_proximity,
    evaluate_entry,
)


# ===== Zone proximity =========================================================


class TestZoneProximity:
    """check_zone_proximity tests."""

    def test_zone_proximity_inside(self):
        """Price within tolerance band returns True."""
        # weight 3 -> 0.45x ATR. ATR=10 -> tolerance=4.5. distance=3 -> inside
        assert check_zone_proximity(103.0, 100.0, atr_15m=10.0, weight=3) is True

    def test_zone_proximity_outside(self):
        """Price outside tolerance band returns False."""
        # weight 3 -> tolerance=4.5. distance=5 -> outside
        assert check_zone_proximity(105.0, 100.0, atr_15m=10.0, weight=3) is False

    def test_zone_proximity_weight_1(self):
        """Weight <= 1 uses tighter 0.30x ATR tolerance."""
        # 0.30 * 10 = 3.0. distance=2.5 -> inside
        assert check_zone_proximity(102.5, 100.0, atr_15m=10.0, weight=1) is True
        # distance=3.5 -> outside
        assert check_zone_proximity(103.5, 100.0, atr_15m=10.0, weight=1) is False

    def test_zone_proximity_weight_2(self):
        """Weight == 2 uses 0.35x ATR tolerance."""
        # 0.35 * 10 = 3.5. distance=3 -> inside
        assert check_zone_proximity(103.0, 100.0, atr_15m=10.0, weight=2) is True
        # distance=4 -> outside
        assert check_zone_proximity(104.0, 100.0, atr_15m=10.0, weight=2) is False

    def test_zone_proximity_weight_3(self):
        """Weight >= 3 uses wider 0.45x ATR tolerance."""
        # 0.45 * 10 = 4.5. distance=4 -> inside
        assert check_zone_proximity(104.0, 100.0, atr_15m=10.0, weight=3) is True

    def test_zone_proximity_zero_atr(self):
        """Zero ATR returns False (division protection)."""
        assert check_zone_proximity(100.0, 100.0, atr_15m=0.0, weight=3) is False

    def test_zone_proximity_negative_atr(self):
        """Negative ATR returns False."""
        assert check_zone_proximity(100.0, 100.0, atr_15m=-5.0, weight=3) is False

    def test_zone_proximity_exact_boundary(self):
        """Price exactly at tolerance boundary returns True (<=)."""
        # 0.45 * 10 = 4.5. distance=4.5 -> exactly on boundary
        assert check_zone_proximity(104.5, 100.0, atr_15m=10.0, weight=3) is True


# ===== Candle confirmation =====================================================


class TestCandleConfirmation:
    """check_candle_confirmation tests."""

    def test_candle_confirmation_bull(self):
        """Green candle (close > open) confirms bull."""
        candles = [{"open": 1.0, "close": 1.5}]
        assert check_candle_confirmation(candles, "bull") is True

    def test_candle_confirmation_bear(self):
        """Red candle (close < open) confirms bear."""
        candles = [{"open": 1.5, "close": 1.0}]
        assert check_candle_confirmation(candles, "bear") is True

    def test_candle_confirmation_timeout(self):
        """No confirmation within max_candles returns False."""
        # All red candles for a bull signal
        candles = [{"open": 2.0, "close": 1.0}] * 6
        assert check_candle_confirmation(candles, "bull", max_candles=6) is False

    def test_candle_confirmation_empty_list(self):
        """Empty candle list returns False."""
        assert check_candle_confirmation([], "bull") is False

    def test_candle_confirmation_doji(self):
        """Doji candle (open == close) confirms neither direction."""
        candles = [{"open": 1.0, "close": 1.0}]
        assert check_candle_confirmation(candles, "bull") is False
        assert check_candle_confirmation(candles, "bear") is False


# ===== EMA9 filter =============================================================


class TestEma9Filter:
    """check_ema9_filter tests."""

    def test_ema9_filter_bull_pass(self):
        """Price above EMA9 passes for bull."""
        assert check_ema9_filter(1.10, 1.09, "bull") is True

    def test_ema9_filter_bull_fail(self):
        """Price below EMA9 fails for bull."""
        assert check_ema9_filter(1.08, 1.09, "bull") is False

    def test_ema9_filter_bear_pass(self):
        """Price below EMA9 passes for bear."""
        assert check_ema9_filter(1.08, 1.09, "bear") is True

    def test_ema9_filter_bear_fail(self):
        """Price above EMA9 fails for bear."""
        assert check_ema9_filter(1.10, 1.09, "bear") is False

    def test_ema9_filter_equal_fails(self):
        """Price == EMA9 fails both directions (strict inequality)."""
        assert check_ema9_filter(1.09, 1.09, "bull") is False
        assert check_ema9_filter(1.09, 1.09, "bear") is False


# ===== evaluate_entry orchestration ============================================


def _make_signal(**overrides):
    """Create a signal dict with sensible defaults."""
    base = {
        "entry_price": 100.0,
        "direction": "bull",
        "grade": "A",
        "score": 9,
        "instrument": "EURUSD",
        "entry_weight": 3,
    }
    base.update(overrides)
    return base


def _make_market(**overrides):
    """Create a market_data dict with sensible defaults."""
    base = {
        "price": 100.5,
        "atr_15m": 10.0,
        "ema9_15m": 99.0,
        "candles_5m": [{"open": 100.0, "close": 101.0}],
        "open_positions": 0,
    }
    base.update(overrides)
    return base


def _make_config(**overrides):
    """Create a bot_config dict with sensible defaults."""
    base = {
        "kill_switch_active": False,
        "max_positions": 3,
        "min_grade": "B",
        "min_score": 6,
    }
    base.update(overrides)
    return base


class TestEvaluateEntry:
    """evaluate_entry orchestration tests."""

    def test_evaluate_entry_all_pass(self):
        """All checks pass -> EntryResult(passed=True)."""
        result = evaluate_entry(_make_signal(), _make_market(), _make_config())
        assert result.passed is True
        assert result.reason == "all_checks_passed"

    def test_evaluate_entry_kill_switch_blocks(self):
        """Active kill switch blocks entry."""
        result = evaluate_entry(
            _make_signal(),
            _make_market(),
            _make_config(kill_switch_active=True),
        )
        assert result.passed is False
        assert result.reason == "kill_switch_active"

    def test_evaluate_entry_max_positions(self):
        """At max positions blocks entry."""
        result = evaluate_entry(
            _make_signal(),
            _make_market(open_positions=3),
            _make_config(max_positions=3),
        )
        assert result.passed is False
        assert result.reason == "max_positions_reached"

    def test_evaluate_entry_grade_below_minimum(self):
        """Signal grade below minimum blocks entry."""
        result = evaluate_entry(
            _make_signal(grade="C", score=9),
            _make_market(),
            _make_config(min_grade="B"),
        )
        assert result.passed is False
        assert result.reason == "grade_below_minimum"

    def test_evaluate_entry_score_below_minimum(self):
        """Signal score below minimum blocks entry."""
        result = evaluate_entry(
            _make_signal(score=3),
            _make_market(),
            _make_config(min_score=6),
        )
        assert result.passed is False
        assert result.reason == "score_below_minimum"

    def test_evaluate_entry_zone_fail(self):
        """Price far from entry level blocks entry."""
        result = evaluate_entry(
            _make_signal(entry_price=100.0),
            _make_market(price=120.0, atr_15m=1.0),
            _make_config(),
        )
        assert result.passed is False
        assert result.reason == "price_not_at_zone"

    def test_evaluate_entry_candle_fail(self):
        """No candle confirmation blocks entry."""
        # All red candles for a bull signal
        result = evaluate_entry(
            _make_signal(direction="bull"),
            _make_market(candles_5m=[{"open": 2.0, "close": 1.0}]),
            _make_config(),
        )
        assert result.passed is False
        assert result.reason == "no_candle_confirmation"

    def test_evaluate_entry_ema9_filter_fail(self):
        """EMA9 filter blocks entry when price on wrong side."""
        result = evaluate_entry(
            _make_signal(direction="bull"),
            _make_market(ema9_15m=200.0),  # price 100.5 < ema9 200
            _make_config(),
        )
        assert result.passed is False
        assert result.reason == "ema9_filter_failed"
