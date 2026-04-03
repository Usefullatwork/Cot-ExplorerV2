"""Unit tests for run_equity_curve_monte_carlo in src.trading.backtesting.monte_carlo."""

from __future__ import annotations

import pytest

from src.trading.backtesting.monte_carlo import (
    EquityCurveMCResult,
    run_equity_curve_monte_carlo,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _positive_returns(n: int = 252, daily_pct: float = 0.001) -> list[float]:
    """Generate n days of steady positive returns."""
    return [daily_pct] * n


def _negative_returns(n: int = 252, daily_pct: float = -0.005) -> list[float]:
    """Generate n days of steady negative returns."""
    return [daily_pct] * n


def _mixed_returns(n: int = 252) -> list[float]:
    """Alternating positive/negative returns with net positive drift."""
    returns: list[float] = []
    for i in range(n):
        returns.append(0.005 if i % 2 == 0 else -0.003)
    return returns


# ===========================================================================
# Determinism
# ===========================================================================


class TestDeterminism:
    """Verify reproducibility with seeded RNG."""

    def test_same_seed_same_result(self):
        """Identical seed -> identical output."""
        rets = _mixed_returns(100)
        r1 = run_equity_curve_monte_carlo(rets, seed=42, iterations=500)
        r2 = run_equity_curve_monte_carlo(rets, seed=42, iterations=500)
        assert r1.mean_annual_return == r2.mean_annual_return
        assert r1.ci_annual_return == r2.ci_annual_return
        assert r1.ruin_probability == r2.ruin_probability
        assert r1.mean_sharpe == r2.mean_sharpe

    def test_different_seed_different_result(self):
        """Different seeds should (almost certainly) give different results."""
        rets = _mixed_returns(100)
        r1 = run_equity_curve_monte_carlo(rets, seed=42, iterations=500)
        r2 = run_equity_curve_monte_carlo(rets, seed=99, iterations=500)
        # Not all fields will match
        assert r1.mean_annual_return != r2.mean_annual_return or r1.mean_sharpe != r2.mean_sharpe


# ===========================================================================
# Positive returns
# ===========================================================================


class TestPositiveReturns:
    """All-positive returns should have good metrics and no ruin."""

    def test_positive_mean_annual_return(self):
        """Steady positive returns -> mean_annual_return > 0."""
        rets = _positive_returns(252)
        result = run_equity_curve_monte_carlo(rets, seed=42, iterations=500)
        assert result.mean_annual_return > 0

    def test_positive_zero_ruin(self):
        """All-positive returns should never hit ruin."""
        rets = _positive_returns(252)
        result = run_equity_curve_monte_carlo(rets, seed=42, iterations=500)
        assert result.ruin_probability == 0.0

    def test_positive_sharpe_positive(self):
        """Mostly positive returns with some variance -> positive Sharpe."""
        # Constant returns have std=0 so Sharpe=0. Use varying positive returns.
        rets = [0.001 * (1 + (i % 5) * 0.2) for i in range(252)]
        result = run_equity_curve_monte_carlo(rets, seed=42, iterations=500)
        assert result.mean_sharpe > 0


# ===========================================================================
# Negative returns
# ===========================================================================


class TestNegativeReturns:
    """All-negative returns should have poor metrics and high ruin."""

    def test_negative_mean_annual_return(self):
        """Steady losses -> mean_annual_return < 0."""
        rets = _negative_returns(252)
        result = run_equity_curve_monte_carlo(rets, seed=42, iterations=500)
        assert result.mean_annual_return < 0

    def test_negative_high_ruin(self):
        """Large daily losses over a year -> ruin probability near 1.0."""
        rets = _negative_returns(252, daily_pct=-0.005)
        result = run_equity_curve_monte_carlo(
            rets, seed=42, iterations=500, ruin_threshold=0.50,
        )
        assert result.ruin_probability > 0.5

    def test_negative_sharpe_negative(self):
        """Mostly negative returns with some variance -> negative Sharpe."""
        # Constant returns have std=0 so Sharpe=0. Use varying negative returns.
        rets = [-0.005 * (1 + (i % 5) * 0.2) for i in range(252)]
        result = run_equity_curve_monte_carlo(rets, seed=42, iterations=500)
        assert result.mean_sharpe < 0


# ===========================================================================
# Confidence intervals
# ===========================================================================


class TestConfidenceIntervals:
    """CI bounds: lower < mean < upper."""

    def test_ci_annual_return_bounds(self):
        """5th percentile <= mean <= 95th percentile for annual return."""
        rets = _mixed_returns(252)
        result = run_equity_curve_monte_carlo(rets, seed=42, iterations=1000)
        lo, hi = result.ci_annual_return
        assert lo <= result.mean_annual_return <= hi

    def test_ci_max_drawdown_bounds(self):
        """5th percentile <= mean <= 95th percentile for max drawdown."""
        rets = _mixed_returns(252)
        result = run_equity_curve_monte_carlo(rets, seed=42, iterations=1000)
        lo, hi = result.ci_max_drawdown
        assert lo <= result.mean_max_drawdown <= hi

    def test_ci_sharpe_bounds(self):
        """5th percentile <= mean <= 95th percentile for Sharpe."""
        rets = _mixed_returns(252)
        result = run_equity_curve_monte_carlo(rets, seed=42, iterations=1000)
        lo, hi = result.ci_sharpe
        assert lo <= result.mean_sharpe <= hi


# ===========================================================================
# Block size effect
# ===========================================================================


class TestBlockSize:
    """Block size should affect results (preserving different correlation)."""

    def test_block_size_1_vs_20_differ(self):
        """block_size=1 and block_size=20 should produce different results."""
        rets = _mixed_returns(252)
        r1 = run_equity_curve_monte_carlo(rets, seed=42, iterations=500, block_size=1)
        r20 = run_equity_curve_monte_carlo(rets, seed=42, iterations=500, block_size=20)
        # Results should differ because block structure changes resampling
        differs = (
            r1.mean_annual_return != r20.mean_annual_return
            or r1.mean_max_drawdown != r20.mean_max_drawdown
            or r1.mean_sharpe != r20.mean_sharpe
        )
        assert differs, "block_size=1 and block_size=20 produced identical results"

    def test_block_size_clamped_to_1(self):
        """block_size=0 should be clamped to 1 and still work."""
        rets = _mixed_returns(100)
        result = run_equity_curve_monte_carlo(rets, seed=42, iterations=100, block_size=0)
        assert isinstance(result, EquityCurveMCResult)


# ===========================================================================
# Recovery time
# ===========================================================================


class TestRecoveryTime:
    """Recovery time tests."""

    def test_recovery_time_positive_for_drawdowns(self):
        """Returns with drawdowns should have recovery_time > 0."""
        rets = _mixed_returns(252)
        result = run_equity_curve_monte_carlo(rets, seed=42, iterations=500)
        assert result.mean_recovery_time > 0

    def test_recovery_time_with_all_positive(self):
        """All-positive returns have zero drawdown -> recovery_time = 0."""
        rets = _positive_returns(100)
        result = run_equity_curve_monte_carlo(rets, seed=42, iterations=500)
        assert result.mean_recovery_time == 0.0


# ===========================================================================
# Edge cases
# ===========================================================================


class TestEdgeCases:
    """Edge cases and validation."""

    def test_single_return(self):
        """Single daily return should still work."""
        result = run_equity_curve_monte_carlo([0.01], seed=42, iterations=100)
        assert isinstance(result, EquityCurveMCResult)
        assert result.iterations == 100

    def test_empty_raises(self):
        """Empty returns list raises ValueError."""
        with pytest.raises(ValueError, match="daily_returns must not be empty"):
            run_equity_curve_monte_carlo([])

    def test_iterations_below_1_raises(self):
        """iterations < 1 raises ValueError."""
        with pytest.raises(ValueError, match="iterations must be >= 1"):
            run_equity_curve_monte_carlo([0.01], iterations=0)

    def test_min_iterations_clamped(self):
        """Iterations below 100 are clamped to 100."""
        result = run_equity_curve_monte_carlo([0.01, -0.005], seed=42, iterations=5)
        assert result.iterations == 100

    def test_result_is_frozen(self):
        """EquityCurveMCResult is frozen dataclass."""
        result = run_equity_curve_monte_carlo([0.01], seed=42, iterations=100)
        with pytest.raises(AttributeError):
            result.iterations = 999  # type: ignore[misc]

    def test_all_zero_returns(self):
        """All zero returns -> zero annual return, zero drawdown."""
        rets = [0.0] * 100
        result = run_equity_curve_monte_carlo(rets, seed=42, iterations=100)
        assert result.mean_annual_return == 0.0
        assert result.mean_max_drawdown == 0.0
        assert result.ruin_probability == 0.0
