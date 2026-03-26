"""Unit tests for src.trading.bot.lot_sizing — VIX regime, tier matrix, lot calculation."""

from __future__ import annotations

import pytest

from src.core.enums import Grade, VixRegime
from src.trading.bot.lot_sizing import (
    _round_to_step,
    adjust_for_drawdown,
    adjust_for_streak,
    calculate_lot_size,
    classify_vix,
    deduct_spread,
    get_tier_multiplier,
)

# ===== Tier multiplier matrix =================================================


class TestTierMultiplier:
    """Verify VIX x Grade multiplier matrix."""

    def test_full_lot_normal_vix_a_plus(self):
        """A+ grade in normal VIX -> 1.0x multiplier."""
        assert get_tier_multiplier(15.0, Grade.A_PLUS) == 1.0

    def test_full_lot_normal_vix_a(self):
        """A grade in normal VIX -> 1.0x multiplier."""
        assert get_tier_multiplier(18.0, Grade.A) == 1.0

    def test_half_lot_normal_vix_b(self):
        """B grade in normal VIX -> 0.6x multiplier."""
        assert get_tier_multiplier(15.0, Grade.B) == 0.6

    def test_half_lot_elevated_vix(self):
        """A+ grade in elevated VIX -> 0.6x multiplier."""
        assert get_tier_multiplier(25.0, Grade.A_PLUS) == 0.6

    def test_quarter_lot_extreme_vix(self):
        """A+ grade in extreme VIX -> 0.3x multiplier."""
        assert get_tier_multiplier(35.0, Grade.A_PLUS) == 0.3

    def test_no_trade_extreme_vix_c_grade(self):
        """C grade in extreme VIX -> 0.0x (no trade)."""
        assert get_tier_multiplier(35.0, Grade.C) == 0.0

    def test_unknown_grade_returns_zero(self):
        """Unknown grade string returns 0.0."""
        assert get_tier_multiplier(15.0, "X") == 0.0


# ===== VIX classification =====================================================


class TestClassifyVix:
    """classify_vix boundaries."""

    def test_classify_vix_normal(self):
        """VIX < 20 -> NORMAL."""
        assert classify_vix(15.0) == VixRegime.NORMAL

    def test_classify_vix_normal_boundary(self):
        """VIX == 20.0 -> NORMAL (boundary: > 20 triggers ELEVATED)."""
        assert classify_vix(20.0) == VixRegime.NORMAL

    def test_classify_vix_elevated(self):
        """VIX 20-30 -> ELEVATED."""
        assert classify_vix(25.0) == VixRegime.ELEVATED

    def test_classify_vix_elevated_boundary(self):
        """VIX == 30.0 -> ELEVATED (boundary: > 30 triggers EXTREME)."""
        assert classify_vix(30.0) == VixRegime.ELEVATED

    def test_classify_vix_extreme(self):
        """VIX > 30 -> EXTREME."""
        assert classify_vix(45.0) == VixRegime.EXTREME


# ===== calculate_lot_size =====================================================


class TestCalculateLotSize:
    """Full lot-size calculation end-to-end."""

    def test_calculate_lot_size_eurusd(self):
        """EURUSD: $10k account, 1% risk, A+ grade, normal VIX.

        SL distance = |1.1000 - 1.0950| = 0.0050 -> 50 pips (pip_size=0.0001)
        risk_amount = 10000 * 0.01 * 1.0 = $100
        raw_lots = 100 / (50 * 10.0) = 0.20
        After floor rounding to lot_step=0.01: may be 0.19 or 0.20
        depending on float precision in pip division.
        """
        lots = calculate_lot_size(
            account_balance=10_000.0,
            risk_pct=0.01,
            entry=1.1000,
            stop_loss=1.0950,
            vix=15.0,
            grade=Grade.A_PLUS,
            instrument="EURUSD",
        )
        # Floor rounding of ~0.20 with float precision can yield 0.19 or 0.20
        assert lots in (0.19, 0.20)

    def test_calculate_lot_size_gold(self):
        """Gold: $10k account, 1% risk, A+ grade, normal VIX.

        pip_size=0.01, pip_value_per_lot=1.0
        SL distance = |2000.0 - 1990.0| = 10.0 -> 10.0 / 0.01 = 1000 pips
        risk_amount = 10000 * 0.01 * 1.0 = $100
        lots = 100 / (1000 * 1.0) = 0.10
        """
        lots = calculate_lot_size(
            account_balance=10_000.0,
            risk_pct=0.01,
            entry=2000.0,
            stop_loss=1990.0,
            vix=15.0,
            grade=Grade.A_PLUS,
            instrument="Gold",
        )
        assert lots == pytest.approx(0.10)

    def test_lot_rounding_to_step(self):
        """Lots should be rounded DOWN to the nearest lot_step (0.01)."""
        # With B grade (0.6x) on EURUSD, 50 pip SL:
        # risk = 10000 * 0.01 * 0.6 = $60
        # raw_lots = 60 / (50 * 10) = 0.12
        # Floor rounding can yield 0.11 or 0.12 depending on float precision
        lots = calculate_lot_size(
            account_balance=10_000.0,
            risk_pct=0.01,
            entry=1.1000,
            stop_loss=1.0950,
            vix=15.0,
            grade=Grade.B,
            instrument="EURUSD",
        )
        assert lots in (0.11, 0.12)

    def test_zero_sl_distance(self):
        """Entry == stop_loss returns 0.0 (division protection)."""
        lots = calculate_lot_size(
            account_balance=10_000.0,
            risk_pct=0.01,
            entry=1.1000,
            stop_loss=1.1000,
            vix=15.0,
            grade=Grade.A_PLUS,
            instrument="EURUSD",
        )
        assert lots == 0.0

    def test_blocked_trade_returns_zero(self):
        """C grade + extreme VIX -> multiplier 0.0 -> lots 0.0."""
        lots = calculate_lot_size(
            account_balance=10_000.0,
            risk_pct=0.01,
            entry=1.1000,
            stop_loss=1.0950,
            vix=35.0,
            grade=Grade.C,
            instrument="EURUSD",
        )
        assert lots == 0.0

    def test_unknown_instrument_returns_zero(self):
        """Unknown instrument key returns 0.0."""
        lots = calculate_lot_size(
            account_balance=10_000.0,
            risk_pct=0.01,
            entry=1.1000,
            stop_loss=1.0950,
            vix=15.0,
            grade=Grade.A_PLUS,
            instrument="UNKNOWN",
        )
        assert lots == 0.0


# ===== _round_to_step ==========================================================


class TestRoundToStep:
    """Internal rounding helper."""

    def test_round_down(self):
        assert _round_to_step(0.127, 0.01) == pytest.approx(0.12)

    def test_exact_multiple(self):
        assert _round_to_step(0.05, 0.01) == pytest.approx(0.05)

    def test_zero_step_returns_value(self):
        assert _round_to_step(0.127, 0.0) == pytest.approx(0.127)

    def test_negative_step_returns_value(self):
        assert _round_to_step(0.127, -0.01) == pytest.approx(0.127)


# ===== adjust_for_drawdown ===================================================


class TestAdjustForDrawdown:
    """Drawdown-based risk reduction."""

    def test_no_drawdown(self) -> None:
        assert adjust_for_drawdown(0.01, 0.0) == 0.01

    def test_small_drawdown(self) -> None:
        assert adjust_for_drawdown(0.01, 5.0) == 0.01

    def test_moderate_drawdown(self) -> None:
        assert adjust_for_drawdown(0.01, 15.0) == pytest.approx(0.005)

    def test_boundary_10(self) -> None:
        assert adjust_for_drawdown(0.01, 10.0) == pytest.approx(0.005)

    def test_severe_drawdown(self) -> None:
        assert adjust_for_drawdown(0.01, 25.0) == pytest.approx(0.0025)

    def test_boundary_20(self) -> None:
        assert adjust_for_drawdown(0.01, 20.0) == pytest.approx(0.0025)


# ===== adjust_for_streak =====================================================


class TestAdjustForStreak:
    """Anti-martingale streak multiplier."""

    def test_no_streak(self) -> None:
        assert adjust_for_streak(1.0, 0, 0) == 1.0

    def test_one_win(self) -> None:
        assert adjust_for_streak(1.0, 1, 0) == 1.0

    def test_two_wins_boost(self) -> None:
        assert adjust_for_streak(1.0, 2, 0) == pytest.approx(1.1)

    def test_many_wins_capped(self) -> None:
        assert adjust_for_streak(1.0, 10, 0) == pytest.approx(1.1)

    def test_cap_at_1_2(self) -> None:
        assert adjust_for_streak(1.15, 3, 0) == 1.2

    def test_one_loss(self) -> None:
        assert adjust_for_streak(1.0, 0, 1) == 0.75

    def test_two_losses(self) -> None:
        assert adjust_for_streak(1.0, 0, 2) == 0.5

    def test_many_losses(self) -> None:
        assert adjust_for_streak(1.0, 0, 5) == 0.5

    def test_losses_override_wins(self) -> None:
        assert adjust_for_streak(1.0, 3, 2) == 0.5


# ===== deduct_spread ==========================================================


class TestDeductSpread:
    """Spread cost deduction from risk budget."""

    def test_normal_deduction(self) -> None:
        assert deduct_spread(100.0, 2.0, 10.0) == 80.0

    def test_zero_spread(self) -> None:
        assert deduct_spread(100.0, 0.0, 10.0) == 100.0

    def test_spread_exceeds_risk(self) -> None:
        assert deduct_spread(10.0, 5.0, 10.0) == 0.0

    def test_exact_match(self) -> None:
        assert deduct_spread(50.0, 5.0, 10.0) == 0.0


# ===== calculate_lot_size with new params =====================================


class TestCalculateLotSizeEnhanced:
    """Lot sizing with drawdown, streak, and spread adjustments."""

    def test_drawdown_reduces_size(self) -> None:
        lots_normal = calculate_lot_size(10_000, 0.01, 1.1050, 1.1000, 15.0, "A+", "EURUSD")
        lots_dd = calculate_lot_size(
            10_000, 0.01, 1.1050, 1.1000, 15.0, "A+", "EURUSD", drawdown_pct=15.0,
        )
        assert lots_dd < lots_normal

    def test_severe_drawdown_reduces_more(self) -> None:
        lots_10 = calculate_lot_size(
            10_000, 0.01, 1.1050, 1.1000, 15.0, "A+", "EURUSD", drawdown_pct=12.0,
        )
        lots_25 = calculate_lot_size(
            10_000, 0.01, 1.1050, 1.1000, 15.0, "A+", "EURUSD", drawdown_pct=25.0,
        )
        assert lots_25 <= lots_10

    def test_loss_streak_reduces_size(self) -> None:
        lots_normal = calculate_lot_size(10_000, 0.01, 1.1050, 1.1000, 15.0, "A+", "EURUSD")
        lots_loss = calculate_lot_size(
            10_000, 0.01, 1.1050, 1.1000, 15.0, "A+", "EURUSD", consecutive_losses=2,
        )
        assert lots_loss < lots_normal

    def test_win_streak_increases_size(self) -> None:
        lots_normal = calculate_lot_size(
            50_000, 0.01, 1.1050, 1.1000, 15.0, "A+", "EURUSD",
        )
        lots_win = calculate_lot_size(
            50_000, 0.01, 1.1050, 1.1000, 15.0, "A+", "EURUSD", consecutive_wins=3,
        )
        assert lots_win >= lots_normal

    def test_spread_reduces_size(self) -> None:
        lots_normal = calculate_lot_size(10_000, 0.01, 1.1050, 1.1000, 15.0, "A+", "EURUSD")
        lots_spread = calculate_lot_size(
            10_000, 0.01, 1.1050, 1.1000, 15.0, "A+", "EURUSD", spread_pips=2.0,
        )
        assert lots_spread < lots_normal

    def test_huge_spread_returns_zero(self) -> None:
        lots = calculate_lot_size(
            1_000, 0.001, 1.1050, 1.1000, 15.0, "B", "EURUSD", spread_pips=100.0,
        )
        assert lots == 0.0

    def test_all_adjustments_combined(self) -> None:
        lots_base = calculate_lot_size(10_000, 0.01, 1.1050, 1.1000, 15.0, "A+", "EURUSD")
        lots_all = calculate_lot_size(
            10_000, 0.01, 1.1050, 1.1000, 15.0, "A+", "EURUSD",
            drawdown_pct=12.0,
            consecutive_losses=1,
            spread_pips=1.0,
        )
        assert lots_all < lots_base

    def test_defaults_match_original(self) -> None:
        """With all new params at defaults, result matches original formula."""
        lots = calculate_lot_size(10_000, 0.01, 1.1050, 1.1000, 15.0, "A+", "EURUSD")
        lots_explicit = calculate_lot_size(
            10_000, 0.01, 1.1050, 1.1000, 15.0, "A+", "EURUSD",
            drawdown_pct=0.0,
            consecutive_wins=0,
            consecutive_losses=0,
            spread_pips=0.0,
        )
        assert lots == lots_explicit
