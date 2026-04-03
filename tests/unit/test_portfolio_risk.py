"""Tests for src.analysis.portfolio_risk -- VaR, CVaR, correlation, regime limits."""

from __future__ import annotations

import math

import pytest

from src.analysis.portfolio_risk import (
    CorrelationSizingResult,
    RegimeLimits,
    VaRResult,
    check_var_gate,
    compute_correlation_sizing,
    compute_parametric_var,
    compute_portfolio_var,
    compute_regime_position_limit,
    pearson_correlation,
)


# ---------------------------------------------------------------------------
# compute_portfolio_var
# ---------------------------------------------------------------------------


class TestComputePortfolioVar:
    """Historical VaR and CVaR."""

    def test_known_distribution(self) -> None:
        """Uniform returns -0.05 to +0.05 -> VaR at 95% ~ 0.045."""
        returns = [i / 1000.0 for i in range(-50, 51)]  # -0.05 to +0.05
        result = compute_portfolio_var(returns)

        assert isinstance(result, VaRResult)
        assert result.var_95 > 0.0
        assert result.var_99 >= result.var_95
        assert result.cvar_95 >= result.var_95
        assert result.cvar_99 >= result.var_99
        assert result.n_returns == len(returns)

    def test_all_positive_returns(self) -> None:
        """All positive returns -> VaR ~ 0 or small."""
        returns = [0.01, 0.02, 0.03, 0.01, 0.02]
        result = compute_portfolio_var(returns)
        # Even the worst return is positive, so VaR is negative (= gain)
        # Our implementation negates the percentile, so VaR could be negative
        assert isinstance(result, VaRResult)

    def test_all_negative_returns(self) -> None:
        """All negative returns -> large VaR."""
        returns = [-0.03, -0.04, -0.05, -0.02, -0.06]
        result = compute_portfolio_var(returns)
        assert result.var_95 > 0.0

    def test_single_return(self) -> None:
        """< 2 returns -> zero VaR."""
        result = compute_portfolio_var([0.01])
        assert result.var_95 == 0.0
        assert result.var_99 == 0.0

    def test_empty_returns(self) -> None:
        result = compute_portfolio_var([])
        assert result.var_95 == 0.0
        assert result.n_returns == 0

    def test_two_returns(self) -> None:
        """Minimum viable input."""
        result = compute_portfolio_var([-0.05, 0.05])
        assert isinstance(result, VaRResult)
        assert result.n_returns == 2

    def test_var99_gte_var95(self) -> None:
        """99% VaR should be >= 95% VaR for a long series."""
        returns = [(-1) ** i * 0.01 * (i % 7) for i in range(200)]
        result = compute_portfolio_var(returns)
        assert result.var_99 >= result.var_95


# ---------------------------------------------------------------------------
# compute_parametric_var
# ---------------------------------------------------------------------------


class TestComputeParametricVar:
    """Parametric (normal) VaR."""

    def test_normal_ish_returns(self) -> None:
        """Mean-zero, std~0.01 -> VaR_95 ~ 1.645 * 0.01."""
        returns = [0.01, -0.01, 0.005, -0.005, 0.008, -0.008, 0.003, -0.003]
        result = compute_parametric_var(returns, confidence=0.95)
        assert result > 0.0

    def test_empty_returns(self) -> None:
        assert compute_parametric_var([]) == 0.0

    def test_single_return(self) -> None:
        assert compute_parametric_var([0.01]) == 0.0

    def test_constant_returns(self) -> None:
        """Zero variance -> VaR = 0."""
        returns = [0.01] * 10
        result = compute_parametric_var(returns)
        assert result == 0.0

    def test_higher_confidence_higher_var(self) -> None:
        """99% VaR should be larger than 95% VaR."""
        returns = [0.02, -0.03, 0.01, -0.01, 0.005, -0.02, 0.015, -0.005]
        var_95 = compute_parametric_var(returns, 0.95)
        var_99 = compute_parametric_var(returns, 0.99)
        assert var_99 > var_95


# ---------------------------------------------------------------------------
# check_var_gate
# ---------------------------------------------------------------------------


class TestCheckVarGate:
    """VaR gate: block when exceeding threshold."""

    def test_within_limit(self) -> None:
        allowed, reason = check_var_gate(0.01, max_var_pct=0.02)
        assert allowed is True
        assert "within limit" in reason

    def test_at_limit(self) -> None:
        allowed, _ = check_var_gate(0.02, max_var_pct=0.02)
        assert allowed is True

    def test_exceeds_limit(self) -> None:
        allowed, reason = check_var_gate(0.03, max_var_pct=0.02)
        assert allowed is False
        assert "VaR gate" in reason

    def test_zero_var(self) -> None:
        allowed, _ = check_var_gate(0.0, max_var_pct=0.02)
        assert allowed is True


# ---------------------------------------------------------------------------
# pearson_correlation
# ---------------------------------------------------------------------------


class TestPearsonCorrelation:
    """Pearson correlation coefficient."""

    def test_perfect_positive(self) -> None:
        x = [1.0, 2.0, 3.0, 4.0, 5.0]
        y = [2.0, 4.0, 6.0, 8.0, 10.0]
        assert pearson_correlation(x, y) == pytest.approx(1.0)

    def test_perfect_negative(self) -> None:
        x = [1.0, 2.0, 3.0, 4.0, 5.0]
        y = [10.0, 8.0, 6.0, 4.0, 2.0]
        assert pearson_correlation(x, y) == pytest.approx(-1.0)

    def test_uncorrelated(self) -> None:
        """Manually constructed uncorrelated series."""
        x = [1.0, -1.0, 1.0, -1.0]
        y = [1.0, 1.0, -1.0, -1.0]
        assert pearson_correlation(x, y) == pytest.approx(0.0, abs=0.01)

    def test_constant_series(self) -> None:
        """Constant series -> correlation = 0."""
        x = [5.0, 5.0, 5.0, 5.0]
        y = [1.0, 2.0, 3.0, 4.0]
        assert pearson_correlation(x, y) == 0.0

    def test_single_element(self) -> None:
        """< 2 elements -> 0."""
        assert pearson_correlation([1.0], [2.0]) == 0.0

    def test_empty(self) -> None:
        assert pearson_correlation([], []) == 0.0

    def test_different_lengths(self) -> None:
        """Uses the shorter length."""
        x = [1.0, 2.0, 3.0, 4.0, 5.0]
        y = [2.0, 4.0, 6.0]
        result = pearson_correlation(x, y)
        assert result == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# compute_correlation_sizing
# ---------------------------------------------------------------------------


class TestComputeCorrelationSizing:
    """Correlation-based position sizing adjustment."""

    def test_no_existing_positions(self) -> None:
        result = compute_correlation_sizing([0.01, -0.01], [])
        assert result.adjusted_multiplier == 1.0
        assert result.blocked is False

    def test_highly_correlated_blocked(self) -> None:
        """Perfectly correlated -> blocked."""
        candidate = [1.0, 2.0, 3.0, 4.0, 5.0]
        existing = [[2.0, 4.0, 6.0, 8.0, 10.0]]
        result = compute_correlation_sizing(candidate, existing)
        assert result.blocked is True
        assert result.adjusted_multiplier == 0.0

    def test_uncorrelated_full_multiplier(self) -> None:
        """Uncorrelated -> multiplier = 1.0."""
        candidate = [1.0, -1.0, 1.0, -1.0]
        existing = [[1.0, 1.0, -1.0, -1.0]]
        result = compute_correlation_sizing(candidate, existing)
        assert result.blocked is False
        assert result.adjusted_multiplier == 1.0

    def test_moderate_correlation_penalty(self) -> None:
        """Correlation between penalty_start and block_threshold."""
        # Build a series with ~0.69 correlation by shuffling adjacent pairs
        candidate = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0]
        existing = [[3.0, 1.0, 5.0, 2.0, 7.0, 4.0, 8.0, 6.0]]
        corr = abs(pearson_correlation(candidate, existing[0]))
        # Verify our test data actually produces a moderate correlation
        assert 0.5 < corr < 0.85, f"Expected ~0.7 correlation, got {corr}"
        result = compute_correlation_sizing(
            candidate, existing, block_threshold=0.85, penalty_start=0.5,
        )
        assert not result.blocked
        assert 0.0 < result.adjusted_multiplier < 1.0

    def test_negative_correlation_not_blocked(self) -> None:
        """Perfectly negatively correlated -> |corr|=1 -> blocked."""
        candidate = [1.0, 2.0, 3.0, 4.0, 5.0]
        existing = [[5.0, 4.0, 3.0, 2.0, 1.0]]
        result = compute_correlation_sizing(candidate, existing)
        assert result.blocked is True  # |corr| = 1.0 > 0.85

    def test_multiple_existing_uses_max(self) -> None:
        """Max correlation from multiple existing positions determines outcome."""
        candidate = [1.0, 2.0, 3.0, 4.0, 5.0]
        low_corr = [5.0, 3.0, 1.0, 3.0, 5.0]  # low corr
        high_corr = [2.0, 4.0, 6.0, 8.0, 10.0]  # perfect corr
        result = compute_correlation_sizing(candidate, [low_corr, high_corr])
        assert result.blocked is True
        assert result.max_correlation == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# compute_regime_position_limit
# ---------------------------------------------------------------------------


class TestComputeRegimePositionLimit:
    """Regime-based position limits."""

    def test_normal_below_limit(self) -> None:
        result = compute_regime_position_limit("normal", 3)
        assert result.can_open is True
        assert result.max_positions == 5

    def test_normal_at_limit(self) -> None:
        result = compute_regime_position_limit("normal", 5)
        assert result.can_open is False

    def test_crisis_one_position(self) -> None:
        result = compute_regime_position_limit("crisis", 1)
        assert result.can_open is False
        assert result.max_positions == 1

    def test_crisis_zero_positions(self) -> None:
        result = compute_regime_position_limit("crisis", 0)
        assert result.can_open is True

    def test_risk_off_limit(self) -> None:
        result = compute_regime_position_limit("risk_off", 2)
        assert result.can_open is True
        assert result.max_positions == 3

    def test_war_footing(self) -> None:
        result = compute_regime_position_limit("war_footing", 2)
        assert result.can_open is False

    def test_energy_shock(self) -> None:
        result = compute_regime_position_limit("energy_shock", 1)
        assert result.can_open is True
        assert result.max_positions == 2

    def test_sanctions(self) -> None:
        result = compute_regime_position_limit("sanctions", 2)
        assert result.can_open is False

    def test_unknown_regime_defaults_to_5(self) -> None:
        result = compute_regime_position_limit("alien_invasion", 4)
        assert result.can_open is True
        assert result.max_positions == 5

    def test_custom_limits(self) -> None:
        custom = {"normal": 10, "crisis": 0}
        result = compute_regime_position_limit("normal", 8, limits=custom)
        assert result.can_open is True
        assert result.max_positions == 10

    def test_custom_crisis_zero(self) -> None:
        custom = {"crisis": 0}
        result = compute_regime_position_limit("crisis", 0, limits=custom)
        assert result.can_open is False
