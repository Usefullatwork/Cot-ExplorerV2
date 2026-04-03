"""Unit tests for src.analysis.bootstrap — bootstrap confidence intervals."""

from __future__ import annotations

import math
import statistics

import pytest

from src.analysis.bootstrap import (
    BootstrapCI,
    bootstrap_ci,
    bootstrap_mean_ci,
    bootstrap_sharpe_ci,
)


# ---------------------------------------------------------------------------
# bootstrap_ci
# ---------------------------------------------------------------------------

class TestBootstrapCI:
    """Tests for the general-purpose bootstrap_ci function."""

    def test_deterministic_with_seed(self) -> None:
        """Same seed produces identical results."""
        data = [1.0, 2.0, 3.0, 4.0, 5.0]
        mean_fn = lambda d: sum(d) / len(d)
        r1 = bootstrap_ci(data, mean_fn, n_boot=500, seed=99)
        r2 = bootstrap_ci(data, mean_fn, n_boot=500, seed=99)
        assert r1 == r2

    def test_ci_contains_true_mean_for_normal_data(self) -> None:
        """For large normal-ish data, 95% CI should contain the true mean."""
        rng = __import__("random").Random(123)
        data = [rng.gauss(10.0, 2.0) for _ in range(500)]
        mean_fn = lambda d: sum(d) / len(d)
        result = bootstrap_ci(data, mean_fn, n_boot=2000, confidence=0.95)
        assert result.ci_lower <= 10.0 <= result.ci_upper

    def test_narrow_ci_for_large_n(self) -> None:
        """CI width should shrink with more data."""
        rng = __import__("random").Random(42)
        small = [rng.gauss(5.0, 1.0) for _ in range(20)]
        large = [rng.gauss(5.0, 1.0) for _ in range(2000)]
        mean_fn = lambda d: sum(d) / len(d)
        ci_small = bootstrap_ci(small, mean_fn, n_boot=1000)
        ci_large = bootstrap_ci(large, mean_fn, n_boot=1000)
        width_small = ci_small.ci_upper - ci_small.ci_lower
        width_large = ci_large.ci_upper - ci_large.ci_lower
        assert width_large < width_small

    def test_dataclass_fields(self) -> None:
        """BootstrapCI has all expected fields."""
        data = [1.0, 2.0, 3.0]
        result = bootstrap_ci(data, lambda d: sum(d) / len(d), n_boot=100)
        assert isinstance(result, BootstrapCI)
        assert result.n_bootstrap == 100
        assert result.confidence == 0.95
        assert result.ci_lower <= result.estimate <= result.ci_upper

    def test_single_data_point(self) -> None:
        """Single value: estimate equals the value, CI collapses."""
        result = bootstrap_ci([7.0], lambda d: sum(d) / len(d), n_boot=100)
        assert result.estimate == 7.0
        assert result.ci_lower == 7.0
        assert result.ci_upper == 7.0

    def test_all_same_data(self) -> None:
        """All-same data: zero-width CI at that value."""
        data = [3.0] * 50
        result = bootstrap_ci(data, lambda d: sum(d) / len(d), n_boot=500)
        assert result.estimate == 3.0
        assert abs(result.ci_lower - 3.0) < 1e-10
        assert abs(result.ci_upper - 3.0) < 1e-10

    def test_empty_data_raises(self) -> None:
        """Empty data raises ValueError."""
        with pytest.raises(ValueError, match="non-empty"):
            bootstrap_ci([], lambda d: sum(d) / len(d))

    def test_invalid_confidence_raises(self) -> None:
        """Confidence outside (0, 1) raises ValueError."""
        with pytest.raises(ValueError, match="confidence"):
            bootstrap_ci([1.0], lambda d: sum(d) / len(d), confidence=1.5)
        with pytest.raises(ValueError, match="confidence"):
            bootstrap_ci([1.0], lambda d: sum(d) / len(d), confidence=0.0)


# ---------------------------------------------------------------------------
# bootstrap_sharpe_ci
# ---------------------------------------------------------------------------

class TestBootstrapSharpeCI:
    """Tests for the Sharpe-specific bootstrap."""

    def test_positive_sharpe_ci_above_zero(self) -> None:
        """Strong positive returns yield CI entirely above zero."""
        rng = __import__("random").Random(7)
        returns = [rng.gauss(0.02, 0.005) for _ in range(200)]
        result = bootstrap_sharpe_ci(returns, n_boot=1000, seed=7)
        assert result.ci_lower > 0.0
        assert result.estimate > 0.0

    def test_flat_returns_ci_around_zero(self) -> None:
        """Near-zero mean returns: CI should straddle zero."""
        rng = __import__("random").Random(42)
        returns = [rng.gauss(0.0, 0.01) for _ in range(200)]
        result = bootstrap_sharpe_ci(returns, n_boot=1000, seed=42)
        assert result.ci_lower < 0.0 < result.ci_upper

    def test_annualization(self) -> None:
        """Different periods_per_year changes the Sharpe estimate."""
        rng = __import__("random").Random(5)
        returns = [rng.gauss(0.01, 0.02) for _ in range(100)]
        weekly = bootstrap_sharpe_ci(returns, periods_per_year=52, seed=5)
        daily = bootstrap_sharpe_ci(returns, periods_per_year=252, seed=5)
        assert abs(daily.estimate) > abs(weekly.estimate)

    def test_empty_returns_raises(self) -> None:
        """Empty returns raises ValueError."""
        with pytest.raises(ValueError, match="non-empty"):
            bootstrap_sharpe_ci([])


# ---------------------------------------------------------------------------
# bootstrap_mean_ci
# ---------------------------------------------------------------------------

class TestBootstrapMeanCI:
    """Tests for the convenience mean bootstrap."""

    def test_matches_known_mean(self) -> None:
        """Mean estimate matches the sample mean."""
        data = [2.0, 4.0, 6.0, 8.0, 10.0]
        result = bootstrap_mean_ci(data, n_boot=500)
        assert abs(result.estimate - 6.0) < 1e-10

    def test_ci_reasonable_for_large_sample(self) -> None:
        """For large sample, CI should be tight around the mean."""
        rng = __import__("random").Random(88)
        data = [rng.gauss(100.0, 5.0) for _ in range(1000)]
        result = bootstrap_mean_ci(data, n_boot=2000)
        width = result.ci_upper - result.ci_lower
        assert width < 2.0

    def test_delegates_to_bootstrap_ci(self) -> None:
        """bootstrap_mean_ci and bootstrap_ci with mean give same result."""
        data = [1.0, 3.0, 5.0, 7.0]
        r1 = bootstrap_mean_ci(data, n_boot=300, seed=11)
        r2 = bootstrap_ci(
            data, lambda d: sum(d) / len(d), n_boot=300, seed=11,
        )
        assert abs(r1.estimate - r2.estimate) < 1e-10
        assert abs(r1.ci_lower - r2.ci_lower) < 1e-10
        assert abs(r1.ci_upper - r2.ci_upper) < 1e-10
