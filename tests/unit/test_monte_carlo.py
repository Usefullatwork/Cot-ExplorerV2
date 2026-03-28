"""Unit tests for src.trading.backtesting.monte_carlo — equity curves, percentiles, simulation."""

from __future__ import annotations

import pytest

from src.trading.backtesting.monte_carlo import (
    _build_equity_curve,
    _percentile,
    generate_report,
    run_monte_carlo,
)

# ===========================================================================
# _build_equity_curve tests
# ===========================================================================


class TestBuildEquityCurve:
    """Tests for the equity curve builder."""

    def test_equity_curve_all_wins(self):
        """All positive trades -> final > start, dd=0."""
        trades = [100.0, 200.0, 150.0, 50.0]
        final, max_dd = _build_equity_curve(trades, 10000.0)
        assert final == 10000.0 + 500.0
        assert max_dd == 0.0

    def test_equity_curve_all_losses(self):
        """All negative trades -> final < start."""
        trades = [-100.0, -200.0, -50.0]
        final, max_dd = _build_equity_curve(trades, 10000.0)
        assert final == 10000.0 - 350.0
        assert final < 10000.0
        assert max_dd > 0.0

    def test_equity_curve_mixed(self):
        """Mixed trades -> correct final and max drawdown."""
        trades = [100.0, -200.0, 300.0]
        final, max_dd = _build_equity_curve(trades, 10000.0)
        # 10000 -> 10100 -> 9900 -> 10200
        assert final == 10200.0
        # Peak after trade 1 = 10100. Trough after trade 2 = 9900.
        # dd = (10100 - 9900) / 10100 * 100 = 1.98...%
        expected_dd = (10100.0 - 9900.0) / 10100.0 * 100.0
        assert abs(max_dd - expected_dd) < 0.01

    def test_equity_curve_single_trade(self):
        """One trade -> simple calculation."""
        final, max_dd = _build_equity_curve([500.0], 10000.0)
        assert final == 10500.0
        assert max_dd == 0.0

        final, max_dd = _build_equity_curve([-500.0], 10000.0)
        assert final == 9500.0
        expected_dd = (10000.0 - 9500.0) / 10000.0 * 100.0
        assert abs(max_dd - expected_dd) < 0.01

    def test_equity_curve_empty_trades(self):
        """Empty trade list -> equity unchanged, dd=0."""
        final, max_dd = _build_equity_curve([], 10000.0)
        assert final == 10000.0
        assert max_dd == 0.0


# ===========================================================================
# _percentile tests
# ===========================================================================


class TestPercentile:
    """Tests for the percentile computation."""

    def test_percentile_50_is_median(self):
        """[1,2,3] -> percentile 50 = 2."""
        assert _percentile([1.0, 2.0, 3.0], 50.0) == 2.0

    def test_percentile_0_is_min(self):
        """Percentile 0 returns minimum value."""
        assert _percentile([1.0, 2.0, 3.0, 4.0, 5.0], 0.0) == 1.0

    def test_percentile_100_is_max(self):
        """Percentile 100 returns maximum value."""
        assert _percentile([1.0, 2.0, 3.0, 4.0, 5.0], 100.0) == 5.0

    def test_percentile_interpolation(self):
        """Verify linear interpolation between values."""
        values = [10.0, 20.0, 30.0, 40.0, 50.0]
        # pct=25 -> k=(25/100)*(4)=1.0 -> lo=1, hi=2, frac=0 -> values[1]=20
        result = _percentile(values, 25.0)
        assert abs(result - 20.0) < 0.01

        # pct=37.5 -> k=(37.5/100)*(4)=1.5 -> lo=1, hi=2, frac=0.5 -> 20+0.5*(30-20)=25
        result = _percentile(values, 37.5)
        assert abs(result - 25.0) < 0.01

    def test_percentile_single_value(self):
        """Single-element list -> always returns that value."""
        assert _percentile([42.0], 0.0) == 42.0
        assert _percentile([42.0], 50.0) == 42.0
        assert _percentile([42.0], 100.0) == 42.0

    def test_percentile_empty_list(self):
        """Empty list returns 0.0."""
        assert _percentile([], 50.0) == 0.0


# ===========================================================================
# run_monte_carlo tests
# ===========================================================================


class TestRunMonteCarlo:
    """Tests for the full Monte Carlo simulation."""

    def test_monte_carlo_deterministic_with_seed(self):
        """Same seed -> same result."""
        trades = [100.0, -50.0, 80.0, -30.0, 200.0, -100.0]
        r1 = run_monte_carlo(trades, starting_equity=10000.0, iterations=500, seed=42)
        r2 = run_monte_carlo(trades, starting_equity=10000.0, iterations=500, seed=42)
        assert r1.median_final_equity == r2.median_final_equity
        assert r1.percentile_5 == r2.percentile_5
        assert r1.percentile_95 == r2.percentile_95
        assert r1.probability_of_ruin == r2.probability_of_ruin

    def test_monte_carlo_all_wins_no_ruin(self):
        """All positive trades -> 0% ruin probability."""
        trades = [100.0, 200.0, 150.0, 50.0, 300.0, 250.0, 100.0, 80.0]
        result = run_monte_carlo(trades, starting_equity=10000.0, iterations=500, seed=123)
        assert result.probability_of_ruin == 0.0
        assert result.confidence_profitable == 100.0

    def test_monte_carlo_all_losses_high_ruin(self):
        """All negative trades -> high ruin probability."""
        # Total loss = -8000 from 10000 start -> final = 2000 which is < 5000 (50% ruin)
        trades = [-1000.0] * 8
        result = run_monte_carlo(trades, starting_equity=10000.0, iterations=500, seed=456)
        assert result.probability_of_ruin == 100.0
        assert result.confidence_profitable == 0.0

    def test_monte_carlo_confidence_bounds(self):
        """percentile_5 <= median <= percentile_95."""
        trades = [100.0, -50.0, 80.0, -30.0, 200.0, -100.0, 50.0, -20.0]
        result = run_monte_carlo(trades, starting_equity=10000.0, iterations=1000, seed=789)
        assert result.percentile_5 <= result.median_final_equity
        assert result.median_final_equity <= result.percentile_95
        assert result.percentile_25 <= result.percentile_75

    def test_monte_carlo_empty_trades_raises(self):
        """Empty trades list raises ValueError."""
        with pytest.raises(ValueError, match="trades list must not be empty"):
            run_monte_carlo([], starting_equity=10000.0)

    def test_monte_carlo_min_iterations_enforced(self):
        """Iterations below 100 are clamped to 100."""
        trades = [100.0, -50.0, 80.0]
        result = run_monte_carlo(trades, starting_equity=10000.0, iterations=1, seed=42)
        assert result.iterations == 100

    def test_monte_carlo_result_is_frozen(self):
        """MonteCarloResult is frozen dataclass — attributes are read-only."""
        trades = [100.0, -50.0]
        result = run_monte_carlo(trades, starting_equity=10000.0, iterations=100, seed=42)
        with pytest.raises(AttributeError):
            result.iterations = 999  # type: ignore[misc]


# ===========================================================================
# generate_report tests
# ===========================================================================


class TestGenerateReport:
    """Tests for the JSON report generator."""

    def test_generate_report_structure(self):
        """Verify dict keys match expected schema."""
        trades = [100.0, -50.0, 80.0, -30.0, 200.0]
        mc_result = run_monte_carlo(trades, starting_equity=10000.0, iterations=100, seed=42)
        report = generate_report(mc_result)

        # Top-level keys
        assert "simulation" in report
        assert "equity_distribution" in report
        assert "risk_assessment" in report

        # Simulation section
        assert "iterations" in report["simulation"]
        assert "original_final_equity" in report["simulation"]

        # Equity distribution section
        assert "median" in report["equity_distribution"]
        assert "percentile_5" in report["equity_distribution"]
        assert "percentile_25" in report["equity_distribution"]
        assert "percentile_75" in report["equity_distribution"]
        assert "percentile_95" in report["equity_distribution"]

        # Risk assessment section
        assert "probability_of_ruin_pct" in report["risk_assessment"]
        assert "max_drawdown_median_pct" in report["risk_assessment"]
        assert "max_drawdown_95th_pct" in report["risk_assessment"]
        assert "confidence_profitable_pct" in report["risk_assessment"]

    def test_generate_report_values_match_result(self):
        """Report values match the MonteCarloResult fields."""
        trades = [100.0, -50.0, 80.0]
        mc_result = run_monte_carlo(trades, starting_equity=10000.0, iterations=100, seed=42)
        report = generate_report(mc_result)

        assert report["simulation"]["iterations"] == mc_result.iterations
        assert report["simulation"]["original_final_equity"] == mc_result.original_final_equity
        assert report["equity_distribution"]["median"] == mc_result.median_final_equity
        assert report["risk_assessment"]["probability_of_ruin_pct"] == mc_result.probability_of_ruin
