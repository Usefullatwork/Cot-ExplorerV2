"""Unit tests for src.trading.bot.risk_manager."""

from __future__ import annotations

import pytest

from src.trading.bot.risk_manager import (
    RiskCheckResult,
    check_consecutive_losses,
    check_daily_loss_limit,
    check_equity_curve,
    check_vix_halt,
    check_weekly_loss_cap,
    evaluate_risk,
)

# ── RiskCheckResult ────────────────────────────────────────────────────────


class TestRiskCheckResult:
    def test_frozen(self) -> None:
        r = RiskCheckResult(True, "ok", 1.0)
        with pytest.raises(AttributeError):
            r.allowed = False  # type: ignore[misc]

    def test_fields(self) -> None:
        r = RiskCheckResult(False, "blocked", 0.0)
        assert r.allowed is False
        assert r.reason == "blocked"
        assert r.recommended_size_multiplier == 0.0


# ── check_equity_curve ─────────────────────────────────────────────────────


class TestCheckEquityCurve:
    def test_no_equity_history(self) -> None:
        r = check_equity_curve(0.0, 0.0)
        assert r.allowed is True
        assert r.recommended_size_multiplier == 1.0

    def test_healthy(self) -> None:
        r = check_equity_curve(100_000, 98_000)
        assert r.allowed is True
        assert r.recommended_size_multiplier == 1.0

    def test_caution_zone(self) -> None:
        # 7% drawdown — between 5% resume and 10% pause
        r = check_equity_curve(100_000, 93_000)
        assert r.allowed is True
        assert 0.0 < r.recommended_size_multiplier < 1.0

    def test_pause_at_threshold(self) -> None:
        # Exactly 10% drawdown
        r = check_equity_curve(100_000, 90_000)
        assert r.allowed is False
        assert r.recommended_size_multiplier == 0.0

    def test_deep_drawdown(self) -> None:
        r = check_equity_curve(100_000, 80_000)
        assert r.allowed is False
        assert "drawdown" in r.reason

    def test_custom_thresholds(self) -> None:
        # 15% drawdown with pause=20%, resume=10% -> caution zone (allowed, scaled)
        r = check_equity_curve(100_000, 85_000, pause_threshold=0.20, resume_threshold=0.10)
        assert r.allowed is True
        assert 0.0 < r.recommended_size_multiplier < 1.0

    def test_custom_thresholds_healthy(self) -> None:
        # 5% drawdown with pause=20%, resume=10% -> healthy (full size)
        r = check_equity_curve(100_000, 95_000, pause_threshold=0.20, resume_threshold=0.10)
        assert r.allowed is True
        assert r.recommended_size_multiplier == 1.0

    def test_negative_peak(self) -> None:
        r = check_equity_curve(-100, 50)
        assert r.allowed is True


# ── check_daily_loss_limit ─────────────────────────────────────────────────


class TestCheckDailyLossLimit:
    def test_zero_losses(self) -> None:
        r = check_daily_loss_limit(0)
        assert r.allowed is True
        assert r.recommended_size_multiplier == 1.0

    def test_under_limit(self) -> None:
        r = check_daily_loss_limit(2, max_daily_losses=3)
        assert r.allowed is True

    def test_at_limit(self) -> None:
        r = check_daily_loss_limit(3, max_daily_losses=3)
        assert r.allowed is False
        assert r.recommended_size_multiplier == 0.0

    def test_over_limit(self) -> None:
        r = check_daily_loss_limit(5, max_daily_losses=3)
        assert r.allowed is False

    def test_custom_limit(self) -> None:
        r = check_daily_loss_limit(4, max_daily_losses=5)
        assert r.allowed is True


# ── check_consecutive_losses ───────────────────────────────────────────────


class TestCheckConsecutiveLosses:
    def test_no_losses(self) -> None:
        r = check_consecutive_losses(0)
        assert r.allowed is True
        assert r.recommended_size_multiplier == 1.0

    def test_one_loss(self) -> None:
        r = check_consecutive_losses(1)
        assert r.allowed is True
        assert r.recommended_size_multiplier == 1.0

    def test_two_losses(self) -> None:
        r = check_consecutive_losses(2)
        assert r.allowed is True
        assert r.recommended_size_multiplier == 0.5

    def test_three_losses(self) -> None:
        r = check_consecutive_losses(3)
        assert r.allowed is True
        assert r.recommended_size_multiplier == 0.25

    def test_many_losses(self) -> None:
        r = check_consecutive_losses(10)
        assert r.allowed is True
        assert r.recommended_size_multiplier == 0.25


# ── check_weekly_loss_cap ──────────────────────────────────────────────────


class TestCheckWeeklyLossCap:
    def test_positive_pnl(self) -> None:
        r = check_weekly_loss_cap(3.0)
        assert r.allowed is True

    def test_within_cap(self) -> None:
        r = check_weekly_loss_cap(-3.0, cap_pct=-5.0)
        assert r.allowed is True

    def test_at_cap(self) -> None:
        r = check_weekly_loss_cap(-5.0, cap_pct=-5.0)
        assert r.allowed is False

    def test_below_cap(self) -> None:
        r = check_weekly_loss_cap(-8.0, cap_pct=-5.0)
        assert r.allowed is False

    def test_custom_cap(self) -> None:
        r = check_weekly_loss_cap(-9.0, cap_pct=-10.0)
        assert r.allowed is True


# ── check_vix_halt ─────────────────────────────────────────────────────────


class TestCheckVixHalt:
    def test_normal_vix(self) -> None:
        r = check_vix_halt(15.0)
        assert r.allowed is True
        assert r.recommended_size_multiplier == 1.0

    def test_elevated_vix(self) -> None:
        r = check_vix_halt(35.0)
        assert r.allowed is True

    def test_at_threshold(self) -> None:
        r = check_vix_halt(40.0)
        assert r.allowed is True  # > not >=

    def test_above_threshold(self) -> None:
        r = check_vix_halt(41.0)
        assert r.allowed is False
        assert r.recommended_size_multiplier == 0.0

    def test_custom_threshold(self) -> None:
        r = check_vix_halt(35.0, halt_threshold=30.0)
        assert r.allowed is False


# ── evaluate_risk ──────────────────────────────────────────────────────────


class TestEvaluateRisk:
    def test_all_clear(self) -> None:
        r = evaluate_risk(100_000, 98_000, 0, 0, 1.0, 15.0)
        assert r.allowed is True
        assert r.recommended_size_multiplier == 1.0
        assert "all risk checks passed" in r.reason

    def test_vix_halt_blocks(self) -> None:
        r = evaluate_risk(100_000, 100_000, 0, 0, 0.0, 45.0)
        assert r.allowed is False
        assert "VIX" in r.reason

    def test_daily_limit_blocks(self) -> None:
        r = evaluate_risk(100_000, 100_000, 3, 0, 0.0, 15.0)
        assert r.allowed is False
        assert "daily" in r.reason

    def test_weekly_cap_blocks(self) -> None:
        r = evaluate_risk(100_000, 100_000, 0, 0, -6.0, 15.0)
        assert r.allowed is False
        assert "weekly" in r.reason

    def test_equity_drawdown_blocks(self) -> None:
        r = evaluate_risk(100_000, 88_000, 0, 0, 0.0, 15.0)
        assert r.allowed is False
        assert "equity" in r.reason

    def test_consecutive_losses_scale_down(self) -> None:
        r = evaluate_risk(100_000, 100_000, 0, 2, 0.0, 15.0)
        assert r.allowed is True
        assert r.recommended_size_multiplier == 0.5

    def test_multiplicative_stacking(self) -> None:
        # 6% drawdown (caution zone) + 2 consecutive losses (0.5x)
        r = evaluate_risk(100_000, 94_000, 0, 2, 0.0, 15.0)
        assert r.allowed is True
        assert r.recommended_size_multiplier < 0.5

    def test_custom_params(self) -> None:
        r = evaluate_risk(
            100_000, 100_000, 4, 0, 0.0, 15.0,
            max_daily_losses=5,
        )
        assert r.allowed is True

    def test_first_blocker_wins(self) -> None:
        # Both VIX halt and daily limit triggered — first blocker returned
        r = evaluate_risk(100_000, 80_000, 5, 5, -10.0, 50.0)
        assert r.allowed is False
        assert r.recommended_size_multiplier == 0.0
