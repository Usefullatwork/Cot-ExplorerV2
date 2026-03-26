"""Unit tests for src.trading.bot.position_manager — all exit logic."""

from __future__ import annotations

from src.trading.bot.position_manager import (
    check_anti_whipsaw,
    check_atr_trailing,
    check_breakeven,
    check_candle_rules,
    check_ema9_exit,
    check_geo_spike,
    check_session_exit,
    check_t1_hit,
    check_triple_tp,
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
            "stop_loss": 100.0,  # SL already at entry so breakeven skips
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

    def test_manage_position_session_exit_scalp(self):
        """Session exit fires for SCALP at hour 21 CET."""
        pos = {
            "direction": "bull", "entry_price": 100.0,
            "target_1": 115.0, "t1_hit": False,
            "candles_since_entry": 2,
        }
        market = {
            "price": 102.0, "ema9_15m": 100.0, "atr_d1": 50.0,
            "current_hour_cet": 21, "timeframe_bias": "SCALP",
        }
        actions = manage_position(pos, market)
        assert len(actions) == 1
        assert actions[0].reason == "session_end"

    def test_manage_position_session_exit_swing_stays(self):
        """SWING positions are not closed at session end."""
        pos = {
            "direction": "bull", "entry_price": 100.0,
            "target_1": 115.0, "t1_hit": False,
            "candles_since_entry": 2,
        }
        market = {
            "price": 102.0, "ema9_15m": 100.0, "atr_d1": 50.0,
            "current_hour_cet": 22, "timeframe_bias": "SWING",
        }
        actions = manage_position(pos, market)
        assert actions == []

    def test_manage_position_atr_trailing(self):
        """ATR trailing fires after T1 hit when price advances."""
        pos = {
            "direction": "bull", "entry_price": 100.0,
            "target_1": 110.0, "t1_hit": True,
            "stop_loss": 100.0, "candles_since_entry": 5,
        }
        # price at 115, ATR=2 -> new_sl = 115-3=112 > current 100
        market = {
            "price": 115.0, "ema9_15m": 116.0, "atr_d1": 50.0,
            "atr": 2.0,
        }
        actions = manage_position(pos, market)
        assert len(actions) == 1
        assert actions[0].action == "modify_sl"
        assert actions[0].reason == "atr_trailing"

    def test_manage_position_breakeven_triggers(self):
        """Breakeven triggers when price moves 50% toward T1."""
        pos = {
            "direction": "bull", "entry_price": 100.0,
            "target_1": 110.0, "t1_hit": False,
            "stop_loss": 95.0, "candles_since_entry": 2,
        }
        # halfway = 5, price-entry = 6 >= 5 -> breakeven triggers
        market = {"price": 106.0, "ema9_15m": 108.0, "atr_d1": 50.0}
        actions = manage_position(pos, market)
        assert len(actions) == 1
        assert actions[0].action == "modify_sl"
        assert actions[0].reason == "breakeven"

    def test_manage_position_triple_tp_t2(self):
        """Triple TP T2 fires at 2R after T1 hit (breakeven already applied)."""
        pos = {
            "direction": "bull", "entry_price": 100.0,
            "target_1": 110.0, "t1_hit": True, "t2_hit": False,
            "stop_loss": 100.0,  # SL at entry (breakeven already applied)
            "initial_risk": 5.0,  # original R preserved for TP levels
            "candles_since_entry": 5,
        }
        # T2 = entry + 2*R = 100 + 10 = 110
        market = {
            "price": 110.0, "ema9_15m": 112.0, "atr_d1": 50.0,
            "atr": 0.0,  # disable ATR trailing
        }
        actions = manage_position(pos, market)
        assert len(actions) == 1
        assert actions[0].action == "partial_close"
        assert actions[0].reason == "t2"
        assert actions[0].close_pct == 0.3


# ===== check_atr_trailing =====================================================


class TestAtrTrailing:
    """ATR-based trailing stop after T1 hit."""

    def test_atr_trailing_long_moves_up(self):
        """Bull: new trailing SL above current SL -> modify."""
        pos = {"direction": "bull", "stop_loss": 95.0, "t1_hit": True}
        action = check_atr_trailing(pos, current_price=110.0, atr_value=2.0)
        assert action is not None
        assert action.action == "modify_sl"
        assert action.reason == "atr_trailing"
        assert action.new_sl == 107.0  # 110 - 1.5*2

    def test_atr_trailing_long_no_retreat(self):
        """Bull: new trailing SL below current SL -> no change."""
        pos = {"direction": "bull", "stop_loss": 108.0, "t1_hit": True}
        action = check_atr_trailing(pos, current_price=110.0, atr_value=2.0)
        # 110 - 3 = 107 < 108, so no modification
        assert action is None

    def test_atr_trailing_short_moves_down(self):
        """Bear: new trailing SL below current SL -> modify."""
        pos = {"direction": "bear", "stop_loss": 115.0, "t1_hit": True}
        action = check_atr_trailing(pos, current_price=100.0, atr_value=2.0)
        assert action is not None
        assert action.new_sl == 103.0  # 100 + 1.5*2

    def test_atr_trailing_short_no_retreat(self):
        """Bear: new trailing SL above current SL -> no change."""
        pos = {"direction": "bear", "stop_loss": 102.0, "t1_hit": True}
        action = check_atr_trailing(pos, current_price=100.0, atr_value=2.0)
        # 100 + 3 = 103 > 102, so no move (would be retreat upward)
        assert action is None

    def test_atr_trailing_before_t1(self):
        """Does not activate before T1 hit."""
        pos = {"direction": "bull", "stop_loss": 95.0, "t1_hit": False}
        action = check_atr_trailing(pos, current_price=115.0, atr_value=2.0)
        assert action is None

    def test_atr_trailing_zero_atr(self):
        """Zero ATR returns None (guard)."""
        pos = {"direction": "bull", "stop_loss": 95.0, "t1_hit": True}
        action = check_atr_trailing(pos, current_price=115.0, atr_value=0.0)
        assert action is None

    def test_atr_trailing_short_initial_sl_zero(self):
        """Bear: initial SL of 0.0 allows first trailing SL set."""
        pos = {"direction": "bear", "stop_loss": 0.0, "t1_hit": True}
        action = check_atr_trailing(pos, current_price=100.0, atr_value=2.0)
        assert action is not None
        assert action.new_sl == 103.0


# ===== check_breakeven ========================================================


class TestBreakeven:
    """Breakeven + buffer move."""

    def test_breakeven_long_triggers(self):
        """Bull: price at 50% of T1 distance moves SL to entry + buffer."""
        pos = {
            "direction": "bull", "entry_price": 100.0,
            "target_1": 110.0, "stop_loss": 95.0,
            "pip_size": 0.0001,
        }
        # halfway = 5, price - entry = 5 -> triggers
        action = check_breakeven(pos, current_price=105.0)
        assert action is not None
        assert action.action == "modify_sl"
        assert action.reason == "breakeven"
        assert action.new_sl == 100.0 + 2 * 0.0001  # entry + 2 pips

    def test_breakeven_long_not_far_enough(self):
        """Bull: price below 50% threshold -> no action."""
        pos = {
            "direction": "bull", "entry_price": 100.0,
            "target_1": 110.0, "stop_loss": 95.0,
        }
        action = check_breakeven(pos, current_price=104.0)
        assert action is None

    def test_breakeven_long_already_at_entry(self):
        """Bull: SL already at entry -> no re-trigger."""
        pos = {
            "direction": "bull", "entry_price": 100.0,
            "target_1": 110.0, "stop_loss": 100.0,
        }
        action = check_breakeven(pos, current_price=106.0)
        assert action is None

    def test_breakeven_long_sl_above_entry(self):
        """Bull: SL above entry (already trailed past) -> no re-trigger."""
        pos = {
            "direction": "bull", "entry_price": 100.0,
            "target_1": 110.0, "stop_loss": 102.0,
        }
        action = check_breakeven(pos, current_price=106.0)
        assert action is None

    def test_breakeven_short_triggers(self):
        """Bear: price at 50% of T1 distance moves SL to entry - buffer."""
        pos = {
            "direction": "bear", "entry_price": 110.0,
            "target_1": 100.0, "stop_loss": 115.0,
            "pip_size": 0.01,
        }
        # halfway = 5, entry - price = 5 -> triggers
        action = check_breakeven(pos, current_price=105.0)
        assert action is not None
        assert action.new_sl == 110.0 - 2 * 0.01

    def test_breakeven_short_already_at_entry(self):
        """Bear: SL at entry -> no re-trigger."""
        pos = {
            "direction": "bear", "entry_price": 110.0,
            "target_1": 100.0, "stop_loss": 110.0,
        }
        action = check_breakeven(pos, current_price=105.0)
        assert action is None

    def test_breakeven_zero_distance(self):
        """T1 == entry -> no action (guard against division by zero)."""
        pos = {
            "direction": "bull", "entry_price": 100.0,
            "target_1": 100.0, "stop_loss": 95.0,
        }
        action = check_breakeven(pos, current_price=100.0)
        assert action is None


# ===== check_triple_tp ========================================================


class TestTripleTp:
    """Triple take-profit levels at 1R/2R/3R."""

    def test_t2_long_hit(self):
        """Bull: price at 2R triggers T2 partial close (30%)."""
        pos = {
            "direction": "bull", "entry_price": 100.0,
            "stop_loss": 95.0, "t1_hit": True, "t2_hit": False,
        }
        # R=5, T2 = 100+10=110
        action = check_triple_tp(pos, current_price=110.0)
        assert action is not None
        assert action.action == "partial_close"
        assert action.reason == "t2"
        assert action.close_pct == 0.3

    def test_t3_long_hit(self):
        """Bull: price at 3R triggers T3 close (20%)."""
        pos = {
            "direction": "bull", "entry_price": 100.0,
            "stop_loss": 95.0, "t1_hit": True,
            "t2_hit": True, "t3_hit": False,
        }
        # R=5, T3 = 100+15=115
        action = check_triple_tp(pos, current_price=115.0)
        assert action is not None
        assert action.action == "close"
        assert action.reason == "t3"
        assert action.close_pct == 0.2

    def test_t2_short_hit(self):
        """Bear: price at 2R triggers T2."""
        pos = {
            "direction": "bear", "entry_price": 110.0,
            "stop_loss": 115.0, "t1_hit": True, "t2_hit": False,
        }
        # R=5, T2 = 110-10=100
        action = check_triple_tp(pos, current_price=100.0)
        assert action is not None
        assert action.reason == "t2"

    def test_t3_short_hit(self):
        """Bear: price at 3R triggers T3."""
        pos = {
            "direction": "bear", "entry_price": 110.0,
            "stop_loss": 115.0, "t1_hit": True,
            "t2_hit": True, "t3_hit": False,
        }
        # R=5, T3 = 110-15=95
        action = check_triple_tp(pos, current_price=95.0)
        assert action is not None
        assert action.reason == "t3"

    def test_t2_not_hit_yet(self):
        """Price below 2R -> no action."""
        pos = {
            "direction": "bull", "entry_price": 100.0,
            "stop_loss": 95.0, "t1_hit": True, "t2_hit": False,
        }
        action = check_triple_tp(pos, current_price=109.0)
        assert action is None

    def test_t2_already_hit(self):
        """T2 already hit and T3 not reached -> no action."""
        pos = {
            "direction": "bull", "entry_price": 100.0,
            "stop_loss": 95.0, "t1_hit": True,
            "t2_hit": True, "t3_hit": False,
        }
        action = check_triple_tp(pos, current_price=112.0)
        assert action is None

    def test_before_t1(self):
        """Triple TP does not fire before T1 hit."""
        pos = {
            "direction": "bull", "entry_price": 100.0,
            "stop_loss": 95.0, "t1_hit": False,
        }
        action = check_triple_tp(pos, current_price=120.0)
        assert action is None

    def test_zero_r_value(self):
        """R=0 (entry == SL) -> no action (guard)."""
        pos = {
            "direction": "bull", "entry_price": 100.0,
            "stop_loss": 100.0, "t1_hit": True, "t2_hit": False,
        }
        action = check_triple_tp(pos, current_price=120.0)
        assert action is None

    def test_t3_already_hit(self):
        """Both T2 and T3 already hit -> no action."""
        pos = {
            "direction": "bull", "entry_price": 100.0,
            "stop_loss": 95.0, "t1_hit": True,
            "t2_hit": True, "t3_hit": True,
        }
        action = check_triple_tp(pos, current_price=120.0)
        assert action is None


# ===== check_session_exit =====================================================


class TestSessionExit:
    """Session-based exit for scalp trades."""

    def test_scalp_closes_at_21(self):
        """SCALP trades close at hour 21 CET."""
        pos = {"direction": "bull", "entry_price": 100.0}
        action = check_session_exit(pos, current_hour_cet=21, timeframe_bias="SCALP")
        assert action is not None
        assert action.action == "close"
        assert action.reason == "session_end"

    def test_scalp_closes_at_23(self):
        """SCALP trades close at hour 23 CET (past boundary)."""
        pos = {"direction": "bull"}
        action = check_session_exit(pos, current_hour_cet=23, timeframe_bias="SCALP")
        assert action is not None

    def test_scalp_stays_open_at_20(self):
        """SCALP trades stay open before hour 21."""
        pos = {"direction": "bull"}
        action = check_session_exit(pos, current_hour_cet=20, timeframe_bias="SCALP")
        assert action is None

    def test_swing_stays_open(self):
        """SWING trades are not affected by session exit."""
        pos = {"direction": "bull"}
        action = check_session_exit(pos, current_hour_cet=22, timeframe_bias="SWING")
        assert action is None

    def test_makro_stays_open(self):
        """MAKRO trades are not affected by session exit."""
        pos = {"direction": "bull"}
        action = check_session_exit(pos, current_hour_cet=22, timeframe_bias="MAKRO")
        assert action is None


# ===== check_anti_whipsaw =====================================================


class TestAntiWhipsaw:
    """Anti-whipsaw cooldown timer."""

    def test_cooldown_elapsed(self):
        """Enough bars passed -> re-entry allowed."""
        assert check_anti_whipsaw("EURUSD", last_loss_bar=10, current_bar=14) is True

    def test_cooldown_not_elapsed(self):
        """Within cooldown -> re-entry blocked."""
        assert check_anti_whipsaw("EURUSD", last_loss_bar=10, current_bar=13) is False

    def test_exact_boundary(self):
        """Exactly at cooldown boundary -> allowed."""
        assert check_anti_whipsaw("EURUSD", last_loss_bar=10, current_bar=14, cooldown_bars=4) is True

    def test_one_short(self):
        """One bar short of cooldown -> blocked."""
        assert check_anti_whipsaw("EURUSD", last_loss_bar=10, current_bar=13, cooldown_bars=4) is False

    def test_custom_cooldown(self):
        """Custom cooldown of 8 bars."""
        assert check_anti_whipsaw("Gold", last_loss_bar=5, current_bar=12, cooldown_bars=8) is False
        assert check_anti_whipsaw("Gold", last_loss_bar=5, current_bar=13, cooldown_bars=8) is True

    def test_same_bar(self):
        """Loss on current bar -> blocked."""
        assert check_anti_whipsaw("GBPUSD", last_loss_bar=10, current_bar=10) is False

    def test_zero_cooldown(self):
        """Zero cooldown -> always allowed."""
        assert check_anti_whipsaw("USDJPY", last_loss_bar=10, current_bar=10, cooldown_bars=0) is True
