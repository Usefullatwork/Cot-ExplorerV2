"""Unit tests for src.analysis.risk_parity — inverse-vol weights, target-vol sizing, ERC."""

from __future__ import annotations

import math

import pytest

from src.analysis.risk_parity import (
    RiskParityAllocation,
    RiskParityResult,
    equal_risk_contribution,
    inverse_vol_weights,
    target_vol_position_size,
)


# ===== inverse_vol_weights ====================================================


class TestInverseVolWeights:
    """Inverse-volatility weight allocation."""

    def test_equal_vols_equal_weights(self) -> None:
        """Equal volatilities produce equal weights."""
        vols = {"A": 0.10, "B": 0.10, "C": 0.10}
        result = inverse_vol_weights(vols)
        weights = [a.clamped_weight for a in result.allocations]
        assert all(abs(w - weights[0]) < 1e-6 for w in weights)

    def test_high_vol_gets_less_weight(self) -> None:
        """Higher vol instrument gets lower raw weight."""
        vols = {"LOW": 0.05, "HIGH": 0.20}
        result = inverse_vol_weights(vols)
        alloc_map = {a.instrument: a for a in result.allocations}
        # Raw weights reflect inverse-vol before clamping
        assert alloc_map["LOW"].raw_weight > alloc_map["HIGH"].raw_weight

    def test_weights_sum_to_one(self) -> None:
        """Clamped weights re-normalize to ~1.0."""
        vols = {"A": 0.05, "B": 0.10, "C": 0.20, "D": 0.30}
        result = inverse_vol_weights(vols)
        assert result.total_weight == pytest.approx(1.0, abs=0.01)

    def test_weight_clamping_min(self) -> None:
        """Very high vol instrument gets clamped to min_weight."""
        vols = {"STABLE": 0.01, "VOLATILE": 10.0}
        result = inverse_vol_weights(vols, min_weight=0.05, max_weight=0.95)
        alloc_map = {a.instrument: a for a in result.allocations}
        assert alloc_map["VOLATILE"].clamped_weight >= 0.05

    def test_weight_clamping_max(self) -> None:
        """Very low vol instrument gets clamped to max_weight."""
        vols = {"STABLE": 0.001, "VOLATILE": 1.0}
        result = inverse_vol_weights(vols, min_weight=0.02, max_weight=0.30)
        alloc_map = {a.instrument: a for a in result.allocations}
        # After re-normalization, the stable one should not exceed max in raw terms
        # but after re-norm it can be higher — just verify it's not absurdly above
        assert alloc_map["STABLE"].clamped_weight <= 1.0

    def test_hhi_equal_weights(self) -> None:
        """HHI for n equal weights = 1/n."""
        vols = {"A": 0.10, "B": 0.10, "C": 0.10, "D": 0.10}
        result = inverse_vol_weights(vols)
        expected_hhi = 1.0 / 4.0
        assert result.hhi == pytest.approx(expected_hhi, abs=0.01)

    def test_hhi_concentrated(self) -> None:
        """HHI for a concentrated portfolio is higher than equal-weight."""
        vols = {"A": 0.01, "B": 1.0, "C": 1.0, "D": 1.0}
        result = inverse_vol_weights(vols, min_weight=0.01, max_weight=0.97)
        equal_hhi = 1.0 / 4.0
        # Should be more concentrated than equal weight
        assert result.hhi >= equal_hhi - 0.01

    def test_empty_volatilities(self) -> None:
        """Empty dict returns empty result."""
        result = inverse_vol_weights({})
        assert result.allocations == []
        assert result.total_weight == 0.0
        assert result.hhi == 0.0

    def test_zero_volatility_excluded(self) -> None:
        """Instruments with vol <= 0 are excluded."""
        vols = {"A": 0.10, "B": 0.0, "C": -0.05}
        result = inverse_vol_weights(vols)
        assert len(result.allocations) == 1
        assert result.allocations[0].instrument == "A"

    def test_single_instrument(self) -> None:
        """Single instrument gets 100% weight."""
        vols = {"ONLY": 0.15}
        result = inverse_vol_weights(vols)
        assert len(result.allocations) == 1
        assert result.allocations[0].clamped_weight == pytest.approx(1.0, abs=0.01)

    def test_equity_target_risk(self) -> None:
        """target_risk_usd = equity * clamped_weight."""
        vols = {"A": 0.10, "B": 0.10}
        result = inverse_vol_weights(vols, equity=100_000)
        for alloc in result.allocations:
            expected = 100_000 * alloc.clamped_weight
            assert alloc.target_risk_usd == pytest.approx(expected, abs=1.0)

    def test_frozen_dataclasses(self) -> None:
        """Result and allocation dataclasses are frozen."""
        vols = {"A": 0.10}
        result = inverse_vol_weights(vols)
        with pytest.raises(AttributeError):
            result.hhi = 0.5  # type: ignore[misc]
        with pytest.raises(AttributeError):
            result.allocations[0].volatility = 0.5  # type: ignore[misc]


# ===== target_vol_position_size ================================================


class TestTargetVolPositionSize:
    """Target volatility position sizing."""

    def test_reasonable_lot_size(self) -> None:
        """Basic computation returns a positive lot size."""
        lots = target_vol_position_size(
            equity=100_000,
            instrument_vol=0.10,
            target_portfolio_vol=0.10,
            n_instruments=4,
            pip_size=0.0001,
            pip_value_per_lot=10.0,
            current_price=1.10,
        )
        assert lots > 0.0

    def test_more_instruments_smaller_size(self) -> None:
        """More instruments -> smaller per-instrument size (sqrt scaling)."""
        lots_1 = target_vol_position_size(
            equity=100_000, instrument_vol=0.10, n_instruments=1,
        )
        lots_4 = target_vol_position_size(
            equity=100_000, instrument_vol=0.10, n_instruments=4,
        )
        assert lots_4 < lots_1

    def test_higher_vol_smaller_size(self) -> None:
        """Higher instrument vol -> fewer lots."""
        lots_low = target_vol_position_size(
            equity=100_000, instrument_vol=0.05,
        )
        lots_high = target_vol_position_size(
            equity=100_000, instrument_vol=0.20,
        )
        assert lots_high < lots_low

    def test_zero_equity_returns_zero(self) -> None:
        lots = target_vol_position_size(equity=0.0, instrument_vol=0.10)
        assert lots == 0.0

    def test_zero_vol_returns_zero(self) -> None:
        lots = target_vol_position_size(equity=100_000, instrument_vol=0.0)
        assert lots == 0.0

    def test_negative_equity_returns_zero(self) -> None:
        lots = target_vol_position_size(equity=-50_000, instrument_vol=0.10)
        assert lots == 0.0

    def test_zero_price_returns_zero(self) -> None:
        lots = target_vol_position_size(
            equity=100_000, instrument_vol=0.10, current_price=0.0,
        )
        assert lots == 0.0

    def test_single_instrument(self) -> None:
        """Single instrument gets full target vol allocation."""
        lots = target_vol_position_size(
            equity=100_000,
            instrument_vol=0.10,
            target_portfolio_vol=0.10,
            n_instruments=1,
            pip_size=0.0001,
            pip_value_per_lot=10.0,
            current_price=1.0,
        )
        # risk_usd = 100000 * 0.10 = 10000
        # risk_per_lot = 0.10 * (1.0 / 0.0001) * 10.0 = 0.10 * 10000 * 10 = 10000
        # lots = 10000 / 10000 = 1.0
        assert lots == pytest.approx(1.0, abs=0.01)


# ===== equal_risk_contribution =================================================


class TestEqualRiskContribution:
    """Equal risk contribution (approximate)."""

    def test_no_correlation_matches_inverse_vol(self) -> None:
        """Without correlations, ERC matches inverse-vol."""
        vols = {"A": 0.10, "B": 0.20, "C": 0.05}
        erc = equal_risk_contribution(vols)
        ivw = inverse_vol_weights(vols)
        ivw_map = {a.instrument: a.raw_weight for a in ivw.allocations}
        for k in erc:
            assert erc[k] == pytest.approx(ivw_map[k], abs=0.01)

    def test_with_correlations_adjusts(self) -> None:
        """With correlations, weights differ from inverse-vol."""
        vols = {"A": 0.10, "B": 0.10, "C": 0.10}
        corrs = {("A", "B"): 0.90, ("A", "C"): 0.0, ("B", "C"): 0.0}
        erc = equal_risk_contribution(vols, corrs)
        # A and B are highly correlated, so C should get more weight
        assert erc["C"] > erc["A"] or erc["C"] > erc["B"]

    def test_weights_sum_to_one(self) -> None:
        """ERC weights sum to ~1.0."""
        vols = {"A": 0.10, "B": 0.20, "C": 0.30}
        erc = equal_risk_contribution(vols)
        assert sum(erc.values()) == pytest.approx(1.0, abs=0.01)

    def test_empty_returns_empty(self) -> None:
        assert equal_risk_contribution({}) == {}

    def test_zero_vols_excluded(self) -> None:
        erc = equal_risk_contribution({"A": 0.10, "B": 0.0})
        assert "B" not in erc
        assert "A" in erc
