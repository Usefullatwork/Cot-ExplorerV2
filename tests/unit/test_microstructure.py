"""Unit tests for src.analysis.microstructure — market microstructure analysis."""

from __future__ import annotations

import pytest

from src.analysis.microstructure import (
    ExecutionQualityMetrics,
    LiquidityScore,
    SpreadQuality,
    classify_session,
    classify_spread_quality,
    execution_quality_report,
    liquidity_score,
    optimal_execution_window,
)


# ===== Session classification =================================================


class TestClassifySession:
    """Session classification mirrors transaction_costs."""

    def test_london_morning(self):
        assert classify_session(9) == "london"

    def test_ny_overlap(self):
        assert classify_session(14) == "ny_overlap"

    def test_ny_afternoon(self):
        assert classify_session(18) == "ny"

    def test_asian_late_night(self):
        assert classify_session(1) == "asian"

    def test_asian_before_midnight(self):
        assert classify_session(23) == "asian"

    def test_off_hours(self):
        assert classify_session(22) == "off_hours"

    def test_wraps_modulo(self):
        assert classify_session(24 + 9) == "london"


# ===== Liquidity score ========================================================


class TestLiquidityScore:
    """Liquidity scoring by instrument, session, and VIX."""

    def test_eurusd_london_high_score(self):
        """Major forex in London session should be highly liquid."""
        result = liquidity_score("EURUSD", hour_cet=10)
        assert result.score >= 0.90
        assert result.session == "london"
        assert result.vix_adjustment == 0.0

    def test_wheat_asian_low_score(self):
        """Agriculture commodity in Asian session should be illiquid."""
        result = liquidity_score("WHEAT", hour_cet=3)
        assert result.score <= 0.25
        assert result.session == "asian"

    def test_high_vix_reduces_score(self):
        """VIX above threshold penalises liquidity."""
        calm = liquidity_score("EURUSD", hour_cet=10, vix=15.0)
        stressed = liquidity_score("EURUSD", hour_cet=10, vix=40.0)
        assert stressed.score < calm.score
        assert stressed.vix_adjustment < 0

    def test_vix_at_threshold_no_penalty(self):
        """VIX exactly at threshold should not reduce score."""
        result = liquidity_score("EURUSD", hour_cet=10, vix=25.0)
        assert result.vix_adjustment == 0.0

    def test_score_clamped_to_zero(self):
        """Extreme VIX should not produce negative scores."""
        result = liquidity_score("CORN", hour_cet=22, vix=100.0)
        assert result.score >= 0.0

    def test_score_clamped_to_one(self):
        """Score should never exceed 1.0."""
        result = liquidity_score("EURUSD", hour_cet=14, vix=5.0)
        assert result.score <= 1.0

    def test_unknown_instrument_low_default(self):
        """Unknown instrument uses conservative default scores."""
        result = liquidity_score("UNOBTANIUM", hour_cet=10)
        assert result.score <= 0.35
        assert "unknown" in result.reason.lower()

    def test_spx_ny_session(self):
        """US index during NY session should be liquid."""
        result = liquidity_score("SPX", hour_cet=18)
        assert result.score >= 0.85


# ===== Optimal execution window ===============================================


class TestOptimalExecutionWindow:
    """Best execution window recommendations."""

    def test_eurusd_prefers_ny_overlap(self):
        """EURUSD (forex_major) should prefer ny_overlap."""
        window = optimal_execution_window("EURUSD")
        assert window.session == "ny_overlap"
        assert window.best_start_cet == 13
        assert window.best_end_cet == 17

    def test_spx_prefers_ny(self):
        """SPX (index) should prefer ny session."""
        window = optimal_execution_window("SPX")
        assert window.session == "ny"

    def test_unknown_instrument_returns_window(self):
        """Unknown instrument still returns a valid window."""
        window = optimal_execution_window("UNKNOWN123")
        assert window.instrument == "UNKNOWN123"
        assert window.session in (
            "london", "ny_overlap", "ny", "asian", "off_hours",
        )


# ===== Spread quality classification ==========================================


class TestClassifySpreadQuality:
    """Spread quality relative to typical."""

    def test_excellent_ratio(self):
        assert classify_spread_quality(0.3, 1.0) == SpreadQuality.EXCELLENT

    def test_good_ratio(self):
        assert classify_spread_quality(0.6, 1.0) == SpreadQuality.GOOD

    def test_normal_ratio(self):
        assert classify_spread_quality(1.0, 1.0) == SpreadQuality.NORMAL

    def test_wide_ratio(self):
        assert classify_spread_quality(1.5, 1.0) == SpreadQuality.WIDE

    def test_very_wide_ratio(self):
        assert classify_spread_quality(2.5, 1.0) == SpreadQuality.VERY_WIDE

    def test_boundary_0_5(self):
        """Exactly 0.5 ratio falls into GOOD (>=0.5, <0.8)."""
        assert classify_spread_quality(0.5, 1.0) == SpreadQuality.GOOD

    def test_boundary_0_8(self):
        """Exactly 0.8 ratio falls into NORMAL (>=0.8, <1.2)."""
        assert classify_spread_quality(0.8, 1.0) == SpreadQuality.NORMAL

    def test_boundary_1_2(self):
        """Exactly 1.2 ratio falls into WIDE (>=1.2, <2.0)."""
        assert classify_spread_quality(1.2, 1.0) == SpreadQuality.WIDE

    def test_boundary_2_0(self):
        """Exactly 2.0 ratio falls into VERY_WIDE (>=2.0)."""
        assert classify_spread_quality(2.0, 1.0) == SpreadQuality.VERY_WIDE

    def test_zero_typical_returns_very_wide(self):
        """Zero typical spread avoids division by zero."""
        assert classify_spread_quality(1.0, 0.0) == SpreadQuality.VERY_WIDE

    def test_negative_typical_returns_very_wide(self):
        """Negative typical spread treated as invalid."""
        assert classify_spread_quality(1.0, -0.5) == SpreadQuality.VERY_WIDE


# ===== Execution quality report ===============================================


class TestExecutionQualityReport:
    """Aggregate execution quality from fill records."""

    def test_known_log_averages(self):
        """Known log data produces correct aggregates."""
        log = [
            {
                "slippage_pips": 0.2,
                "spread_pips": 1.0,
                "typical_spread": 1.0,
                "filled": True,
                "cost_vs_mid_pips": 0.5,
            },
            {
                "slippage_pips": 0.4,
                "spread_pips": 0.8,
                "typical_spread": 1.0,
                "filled": True,
                "cost_vs_mid_pips": 0.3,
            },
        ]
        result = execution_quality_report(log)
        assert result.n_fills == 2
        assert result.avg_slippage_pips == pytest.approx(0.3)
        assert result.max_slippage_pips == pytest.approx(0.4)
        assert result.fill_rate == pytest.approx(1.0)
        assert result.cost_vs_mid_pips == pytest.approx(0.4)

    def test_fill_rate_with_unfilled(self):
        """Unfilled entries reduce the fill rate."""
        log = [
            {"slippage_pips": 0.1, "spread_pips": 1.0, "typical_spread": 1.0,
             "filled": True, "cost_vs_mid_pips": 0.1},
            {"slippage_pips": 0.0, "spread_pips": 1.0, "typical_spread": 1.0,
             "filled": False, "cost_vs_mid_pips": 0.0},
        ]
        result = execution_quality_report(log)
        assert result.fill_rate == pytest.approx(0.5)

    def test_empty_log(self):
        """Empty log returns zeroed metrics."""
        result = execution_quality_report([])
        assert result.n_fills == 0
        assert result.avg_slippage_pips == 0.0
        assert result.fill_rate == 0.0

    def test_zero_typical_spread_gives_zero_quality(self):
        """Zero typical_spread produces zero quality for that entry."""
        log = [
            {"slippage_pips": 0.1, "spread_pips": 1.0, "typical_spread": 0.0,
             "filled": True, "cost_vs_mid_pips": 0.1},
        ]
        result = execution_quality_report(log)
        assert result.avg_spread_quality == 0.0
