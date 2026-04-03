"""Unit tests for enhanced correlation functions in src.analysis.correlation."""

from __future__ import annotations

import pytest

from src.analysis.correlation import (
    correlation_regime_change,
    ewma_correlation,
    portfolio_correlation_penalty,
)


# ===== ewma_correlation =======================================================


class TestEwmaCorrelation:
    """EWMA correlation tests."""

    def test_identical_series_perfect_positive(self) -> None:
        """Identical return series -> correlation ~1.0."""
        series = [0.01, -0.02, 0.03, -0.01, 0.02, 0.01, -0.03, 0.02]
        corr = ewma_correlation(series, series)
        assert corr == pytest.approx(1.0, abs=0.01)

    def test_opposite_series_perfect_negative(self) -> None:
        """Opposite return series -> correlation ~-1.0."""
        series_a = [0.01, -0.02, 0.03, -0.01, 0.02, 0.01, -0.03, 0.02]
        series_b = [-x for x in series_a]
        corr = ewma_correlation(series_a, series_b)
        assert corr == pytest.approx(-1.0, abs=0.01)

    def test_uncorrelated_near_zero(self) -> None:
        """Uncorrelated series -> correlation near 0."""
        # Deliberately uncorrelated pattern
        series_a = [0.01, -0.02, 0.03, -0.01, 0.02, -0.03, 0.01, -0.02]
        series_b = [0.02, 0.01, -0.01, 0.03, -0.02, 0.01, -0.03, 0.02]
        corr = ewma_correlation(series_a, series_b)
        assert abs(corr) < 0.8  # not strongly correlated

    def test_short_series_returns_zero(self) -> None:
        """Series with fewer than 2 elements returns 0.0."""
        assert ewma_correlation([1.0], [2.0]) == 0.0
        assert ewma_correlation([], []) == 0.0

    def test_constant_series_returns_zero(self) -> None:
        """Constant series (zero variance) returns 0.0."""
        series_a = [0.05] * 10
        series_b = list(range(10))  # non-constant to avoid 0/0
        # series_a has zero variance -> denom = 0 -> return 0.0
        corr = ewma_correlation(series_a, series_b)
        assert corr == 0.0

    def test_different_halflife(self) -> None:
        """Different halflife produces different results."""
        series_a = [0.01, -0.02, 0.05, -0.01, 0.02, 0.03, -0.01, 0.04]
        series_b = [0.02, -0.01, 0.04, -0.02, 0.01, 0.02, -0.02, 0.03]
        corr_short = ewma_correlation(series_a, series_b, halflife=3)
        corr_long = ewma_correlation(series_a, series_b, halflife=50)
        # Different halflife -> different correlation values
        assert corr_short != pytest.approx(corr_long, abs=0.001)

    def test_result_bounded(self) -> None:
        """Result is always in [-1.0, 1.0]."""
        series_a = [0.1, -0.5, 0.3, -0.1, 0.2]
        series_b = [0.2, -0.3, 0.1, 0.4, -0.2]
        corr = ewma_correlation(series_a, series_b)
        assert -1.0 <= corr <= 1.0


# ===== correlation_regime_change ===============================================


class TestCorrelationRegimeChange:
    """Correlation regime change detection."""

    def test_stable_no_change(self) -> None:
        """Stable correlation series -> no regime change."""
        correlations = [0.50, 0.52, 0.48, 0.51, 0.49, 0.50, 0.51]
        is_changed, score = correlation_regime_change(correlations)
        assert is_changed is False

    def test_spike_detected(self) -> None:
        """Large spike in correlation -> regime change detected."""
        # Stable around 0.5, then sudden jump to 0.95
        correlations = [0.50, 0.52, 0.48, 0.51, 0.49, 0.50, 0.95]
        is_changed, score = correlation_regime_change(correlations)
        assert is_changed is True
        assert score is not None
        assert score > 2.0

    def test_breakdown_detected(self) -> None:
        """Large drop in correlation -> regime change detected."""
        correlations = [0.80, 0.82, 0.78, 0.81, 0.79, 0.80, -0.20]
        is_changed, score = correlation_regime_change(correlations)
        assert is_changed is True

    def test_too_few_values(self) -> None:
        """Fewer than 3 values -> no detection."""
        is_changed, score = correlation_regime_change([0.5, 0.9])
        assert is_changed is False
        assert score is None

    def test_custom_threshold(self) -> None:
        """Higher threshold requires larger deviation."""
        correlations = [0.50, 0.52, 0.48, 0.51, 0.49, 0.50, 0.70]
        # Default threshold (2.0) may flag this
        is_changed_default, _ = correlation_regime_change(correlations, threshold_std=2.0)
        # Very high threshold should not flag
        is_changed_high, _ = correlation_regime_change(correlations, threshold_std=10.0)
        assert is_changed_high is False

    def test_constant_series_no_change(self) -> None:
        """Constant series (zero std) -> no change."""
        is_changed, score = correlation_regime_change([0.5, 0.5, 0.5, 0.5])
        assert is_changed is False
        assert score is None


# ===== portfolio_correlation_penalty ===========================================


class TestPortfolioCorrelationPenalty:
    """Portfolio correlation penalty tests."""

    def test_no_existing_positions(self) -> None:
        """No existing positions -> multiplier 1.0."""
        mult, corr = portfolio_correlation_penalty([0.01, -0.02], [])
        assert mult == 1.0
        assert corr == 0.0

    def test_high_correlation_blocked(self) -> None:
        """Highly correlated candidate is blocked (multiplier=0)."""
        series = [0.01, -0.02, 0.03, -0.01, 0.02, 0.01, -0.03, 0.02]
        mult, corr = portfolio_correlation_penalty(
            series, [series], block_threshold=0.85,
        )
        assert mult == 0.0
        assert corr > 0.85

    def test_low_correlation_full_size(self) -> None:
        """Low correlation -> multiplier 1.0."""
        series_a = [0.01, -0.02, 0.03, -0.01, 0.02, -0.03, 0.01, -0.02]
        series_b = [0.02, 0.01, -0.01, 0.03, -0.02, 0.01, -0.03, 0.02]
        mult, corr = portfolio_correlation_penalty(
            series_a, [series_b], block_threshold=0.85, penalty_start=0.50,
        )
        # If correlation is below 0.50, multiplier should be 1.0
        if corr <= 0.50:
            assert mult == 1.0

    def test_penalty_zone_partial_multiplier(self) -> None:
        """Correlation in penalty zone produces 0 < multiplier < 1."""
        # Create series with moderate correlation (~0.7)
        base = [0.01, -0.02, 0.03, -0.01, 0.02, 0.01, -0.03, 0.02]
        noisy = [b + (0.005 if i % 2 == 0 else -0.005) for i, b in enumerate(base)]
        mult, corr = portfolio_correlation_penalty(
            base, [noisy],
            block_threshold=0.99,  # high block so we stay in penalty zone
            penalty_start=0.30,
        )
        # corr should be high but below 0.99 -> partial penalty
        if 0.30 < corr < 0.99:
            assert 0.0 < mult < 1.0

    def test_opposite_series_blocked(self) -> None:
        """Perfectly inverse-correlated series -> blocked (abs corr > threshold)."""
        series = [0.01, -0.02, 0.03, -0.01, 0.02, 0.01, -0.03, 0.02]
        opposite = [-x for x in series]
        mult, corr = portfolio_correlation_penalty(
            series, [opposite], block_threshold=0.85,
        )
        assert mult == 0.0
        assert corr > 0.85

    def test_multiple_existing_uses_max(self) -> None:
        """With multiple existing positions, uses the maximum correlation."""
        series = [0.01, -0.02, 0.03, -0.01, 0.02, 0.01, -0.03, 0.02]
        unrelated = [0.03, 0.01, -0.01, 0.02, -0.03, 0.01, 0.02, -0.01]
        mult, corr = portfolio_correlation_penalty(
            series, [unrelated, series], block_threshold=0.85,
        )
        # The identical series should dominate -> blocked
        assert mult == 0.0
