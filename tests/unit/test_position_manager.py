"""Unit tests for src.trading.bot.position_manager — T1 hit, EMA9 exit, candle rules, geo spike."""

from __future__ import annotations

from src.trading.bot.position_manager import (
    PositionAction,
    check_candle_rules,
    check_ema9_exit,
    check_geo_spike,
    check_t1_hit,
    manage_position,
)


# ===== check_t1_hit ============================================================


class TestT1Hit:
    """T1 target hit detection."""

    def test_t1_hit_long(self):
        """Bull position: price >= T1 triggers partial close."""
        pos = {"direction": "bull", "entry_price": 100.0, "target_1": 110.0, "t1_hit": False}
        action = check_t1_hit(pos, current_price=110.0)
        assert action is not None
        assert action.action == "partial_close"
        assert action.reason == "t1_hit"
        assert action.close_pct == 0.5
        assert action.new_sl == 100.0  # breakeven

    def test_t1_hit_short(self):
        """Bear position: price <= T1 triggers partial close."""
        pos = {"direction": "bear", "entry_price": 110.0, "target_1": 100.0, "t1_hit": False}
        action = check_t1_hit(pos, current_price=100.0)
        assert action is not None
        assert action.action == "partial_close"
        assert action.reason == "t1_hit"
        assert action.close_pct == 0.5
        assert action.new_sl == 110.0

    def test_t1_not_hit(self):
        """Price below T1 for bull position returns None."""
        pos = {"direction": "bull", "entry_price": 100.0, "target_1": 110.0, "t1_hit": False}
        action = check_t1_hit(pos, current_price=105.0)
        assert action is None

    def test_t1_already_hit(self):
        """If T1 was already hit, returns None (no duplicate partial close)."""
        pos = {"direction": "bull", "entry_price": 100.0, "target_1": 110.0, "t1_hit": True}
        action = check_t1_hit(pos, current_price=115.0)
        assert action is None

    def test_t1_hit_long_above(self):
        """Bull: price overshooting T1 still triggers."""
        pos = {"direction": "bull", "entry_price": 100.0, "target_1": 110.0, "t1_hit": False}
        action = check_t1_hit(pos, current_price=115.0)
        assert action is not None
        assert action.action == "partial_close"


# ===== check_ema9_exit =========================================================


class TestEma9Exit:
    """EMA9 cross exit after T1 hit."""

    def test_ema9_exit_after_t1_bull(self):
        """Bull: price < EMA9 after T1 hit triggers close."""
        pos = {"direction": "bull", "t1_hit": True}
        action = check_ema9_exit(pos, ema9_15m=105.0, current_price=104.0)
        assert action is not None
        assert action.action == "close"
        assert action.reason == "ema9_cross"

    def test_ema9_exit_after_t1_bear(self):
        """Bear: price > EMA9 after T1 hit triggers close."""
        pos = {"direction": "bear", "t1_hit": True}
        action = check_ema9_exit(pos, ema9_15m=100.0, current_price=101.0)
        assert action is not None
        assert action.action == "close"
        assert action.reason == "ema9_cross"

    def test_ema9_exit_before_t1(self):
        """No EMA9 exit if T1 not hit yet."""
        pos = {"direction": "bull", "t1_hit": False}
        action = check_ema9_exit(pos, ema9_15m=105.0, current_price=104.0)
        assert action is None

    def test_ema9_no_cross(self):
        """Bull: price above EMA9 -> no exit."""
        pos = {"direction": "bull", "t1_hit": True}
        action = check_ema9_exit(pos, ema9_15m=100.0, current_price=105.0)
        assert action is None


# ===== check_candle_rules =====================================================


class TestCandleRules:
    """Time-based exit via candle count."""

    def test_8_candle_rule(self):
        """8 candles without T1 hit -> partial close 50%."""
        pos = {"candles_since_entry": 8, "t1_hit": False}
        action = check_candle_rules(pos)
        assert action is not None
        assert action.action == "partial_close"
        assert action.reason == "candle_8"
        assert action.close_pct == 0.5

    def test_8_candle_not_elapsed(self):
        """7 candles -> no action."""
        pos = {"candles_since_entry": 7, "t1_hit": False}
        action = check_candle_rules(pos)
        assert action is None

    def test_16_candle_rule(self):
        """16 candles after T1 hit -> full close."""
        pos = {"candles_since_entry": 16, "t1_hit": True}
        action = check_candle_rules(pos)
        assert action is not None
        assert action.action == "close"
        assert action.reason == "candle_16"

    def test_16_candle_before_t1(self):
        """16 candles but T1 not hit -> 8-candle rule triggers instead."""
        pos = {"candles_since_entry": 16, "t1_hit": False}
        action = check_candle_rules(pos)
        assert action is not None
        assert action.action == "partial_close"
        assert action.reason == "candle_8"

    def test_0_candles(self):
        """Zero candles -> no action."""
        pos = {"candles_since_entry": 0, "t1_hit": False}
        action = check_candle_rules(pos)
        assert action is None


# ===== check_geo_spike =========================================================


class TestGeoSpike:
    """Emergency exit on extreme adverse move."""

    def test_geo_spike_triggers_bull(self):
        """Bull: price drops > 2x ATR(D1) from entry -> emergency close."""
        pos = {"direction": "bull", "entry_price": 100.0}
        action = check_geo_spike(pos, current_price=79.0, atr_d1=10.0)
        assert action is not None
        assert action.action == "emergency_close"
        assert action.reason == "geo_spike"

    def test_geo_spike_triggers_bear(self):
        """Bear: price rises > 2x ATR(D1) from entry -> emergency close."""
        pos = {"direction": "bear", "entry_price": 100.0}
        action = check_geo_spike(pos, current_price=121.0, atr_d1=10.0)
        assert action is not None
        assert action.action == "emergency_close"

    def test_geo_spike_normal(self):
        """Normal adverse move (< 2x ATR) -> no trigger."""
        pos = {"direction": "bull", "entry_price": 100.0}
        action = check_geo_spike(pos, current_price=85.0, atr_d1=10.0)
        assert action is None

    def test_geo_spike_zero_atr(self):
        """Zero ATR(D1) -> returns None (protection)."""
        pos = {"direction": "bull", "entry_price": 100.0}
        action = check_geo_spike(pos, current_price=50.0, atr_d1=0.0)
        assert action is None

    def test_geo_spike_favorable_move(self):
        """Favorable move (price up for bull) -> no trigger."""
        pos = {"direction": "bull", "entry_price": 100.0}
        action = check_geo_spike(pos, current_price=130.0, atr_d1=10.0)
        assert action is None


# ===== manage_position orchestration ===========================================


class TestManagePosition:
    """manage_position priority ordering."""

    def test_manage_position_priority_geo_spike(self):
        """Geo spike overrides all other rules."""
        pos = {
            "direction": "bull", "entry_price": 100.0,
            "target_1": 110.0, "t1_hit": False,
            "candles_since_entry": 20,
        }
        market = {"price": 75.0, "ema9_15m": 90.0, "atr_d1": 10.0}
        actions = manage_position(pos, market)
        assert len(actions) == 1
        assert actions[0].action == "emergency_close"
        assert actions[0].reason == "geo_spike"

    def test_manage_position_t1_hit_flow(self):
        """T1 hit produces partial_close when no geo spike."""
        pos = {
            "direction": "bull", "entry_price": 100.0,
            "target_1": 110.0, "t1_hit": False,
            "candles_since_entry": 2,
        }
        market = {"price": 110.0, "ema9_15m": 108.0, "atr_d1": 50.0}
        actions = manage_position(pos, market)
        assert len(actions) == 1
        assert actions[0].action == "partial_close"
        assert actions[0].reason == "t1_hit"

    def test_manage_position_ema9_exit_after_t1(self):
        """EMA9 cross triggers after T1 was already hit."""
        pos = {
            "direction": "bull", "entry_price": 100.0,
            "target_1": 110.0, "t1_hit": True,
            "candles_since_entry": 5,
        }
        market = {"price": 104.0, "ema9_15m": 105.0, "atr_d1": 50.0}
        actions = manage_position(pos, market)
        assert len(actions) == 1
        assert actions[0].action == "close"
        assert actions[0].reason == "ema9_cross"

    def test_manage_position_candle_rule_fallback(self):
        """Candle rule triggers when nothing else fires."""
        pos = {
            "direction": "bull", "entry_price": 100.0,
            "target_1": 115.0, "t1_hit": False,
            "candles_since_entry": 8,
        }
        market = {"price": 102.0, "ema9_15m": 100.0, "atr_d1": 50.0}
        actions = manage_position(pos, market)
        assert len(actions) == 1
        assert actions[0].action == "partial_close"
        assert actions[0].reason == "candle_8"

    def test_manage_position_no_action(self):
        """No rules triggered returns empty list."""
        pos = {
            "direction": "bull", "entry_price": 100.0,
            "target_1": 115.0, "t1_hit": False,
            "candles_since_entry": 3,
        }
        market = {"price": 102.0, "ema9_15m": 100.0, "atr_d1": 50.0}
        actions = manage_position(pos, market)
        assert actions == []
