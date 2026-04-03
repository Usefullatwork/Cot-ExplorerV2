"""Tests for src.analysis.stress_test -- historical scenario stress testing."""

from __future__ import annotations

import pytest

from src.analysis.stress_test import (
    Position,
    ScenarioImpact,
    StressResult,
    check_stress_gate,
    classify_instrument,
    run_all_stress_tests,
    stress_test_portfolio,
)


# ---------------------------------------------------------------------------
# classify_instrument
# ---------------------------------------------------------------------------


class TestClassifyInstrument:
    """Instrument -> sensitivity class mapping."""

    def test_forex_major(self) -> None:
        assert classify_instrument("EURUSD") == "forex_major"

    def test_forex_safe(self) -> None:
        assert classify_instrument("USDJPY") == "forex_safe"

    def test_gold(self) -> None:
        assert classify_instrument("Gold") == "gold"

    def test_indices(self) -> None:
        assert classify_instrument("SPX") == "indices"

    def test_unknown_instrument(self) -> None:
        assert classify_instrument("DOGECOIN") == "unknown"


# ---------------------------------------------------------------------------
# stress_test_portfolio
# ---------------------------------------------------------------------------


class TestStressTestPortfolio:
    """Single-scenario stress tests."""

    def test_long_gold_2008_gains(self) -> None:
        """Long Gold in 2008 GFC -> gold went up 15% -> position gains."""
        positions = [Position("Gold", "long", 50_000.0)]
        result = stress_test_portfolio(positions, 100_000.0, "2008_gfc")

        assert result.scenario_name == "2008_gfc"
        assert result.total_loss_pct < 0.0  # negative loss = gain
        assert result.survives is True

    def test_long_spx_2008_heavy_loss(self) -> None:
        """Long SPX in 2008 GFC -> indices -40% -> heavy loss."""
        positions = [Position("SPX", "long", 80_000.0)]
        result = stress_test_portfolio(positions, 100_000.0, "2008_gfc")

        assert result.total_loss_pct > 0.0
        assert result.worst_instrument == "SPX"
        # 80k * 40% = 32k loss -> 32% of 100k equity
        assert result.total_loss_pct == pytest.approx(32.0)

    def test_short_oil_2008_gains(self) -> None:
        """Short oil in 2008 -> oil crashed 55% -> short profits."""
        positions = [Position("Brent", "short", 30_000.0)]
        result = stress_test_portfolio(positions, 100_000.0, "2008_gfc")

        # Short profits when price drops
        assert result.total_loss_pct < 0.0

    def test_long_oil_2008_loses(self) -> None:
        """Long oil in 2008 -> oil crashed 55% -> big loss."""
        positions = [Position("WTI", "long", 40_000.0)]
        result = stress_test_portfolio(positions, 100_000.0, "2008_gfc")

        # 40k * 55% = 22k loss -> 22% of 100k
        assert result.total_loss_pct == pytest.approx(22.0)

    def test_long_oil_2022_gains(self) -> None:
        """Long oil in 2022 rate shock -> oil went up 20% -> gains."""
        positions = [Position("Brent", "long", 50_000.0)]
        result = stress_test_portfolio(positions, 100_000.0, "2022_rate_shock")

        assert result.total_loss_pct < 0.0  # gain

    def test_unknown_instrument_small_impact(self) -> None:
        """Unknown instrument gets default -2% sensitivity."""
        positions = [Position("DOGECOIN", "long", 10_000.0)]
        result = stress_test_portfolio(positions, 100_000.0, "flash_crash")

        # 10k * 2% = 200 loss -> 0.2% of 100k
        assert result.total_loss_pct == pytest.approx(0.2)

    def test_empty_portfolio(self) -> None:
        result = stress_test_portfolio([], 100_000.0, "2008_gfc")
        assert result.total_loss_pct == 0.0
        assert result.survives is True
        assert result.impacts == []

    def test_zero_equity(self) -> None:
        positions = [Position("Gold", "long", 10_000.0)]
        result = stress_test_portfolio(positions, 0.0, "2008_gfc")
        assert result.total_loss_pct == 0.0
        assert result.survives is True

    def test_unknown_scenario(self) -> None:
        """Unknown scenario -> no sensitivities -> default impact."""
        positions = [Position("Gold", "long", 10_000.0)]
        result = stress_test_portfolio(positions, 100_000.0, "alien_invasion")
        # Default sensitivity is -0.02 for all classes when scenario is unknown
        assert result.total_loss_pct == pytest.approx(0.2)

    def test_mixed_portfolio_2020(self) -> None:
        """Mixed portfolio in COVID: gold long gains, SPX long loses."""
        positions = [
            Position("Gold", "long", 30_000.0),
            Position("SPX", "long", 50_000.0),
        ]
        result = stress_test_portfolio(positions, 100_000.0, "2020_covid")

        # Gold: 30k * 10% = 3k gain (loss = -3%)
        # SPX: 50k * 35% = 17.5k loss (loss = +17.5%)
        # Net: 14.5k loss -> 14.5% of equity
        assert result.total_loss_pct == pytest.approx(14.5)
        assert result.worst_instrument == "SPX"

    def test_survives_flag(self) -> None:
        """survives is True when total_loss_pct < 15%."""
        positions = [Position("Gold", "long", 10_000.0)]
        result = stress_test_portfolio(positions, 100_000.0, "flash_crash")
        assert result.survives is True

    def test_does_not_survive(self) -> None:
        """Large SPX position in 2008 -> loss > 15% -> does not survive."""
        positions = [Position("SPX", "long", 50_000.0)]
        result = stress_test_portfolio(positions, 100_000.0, "2008_gfc")
        # 50k * 40% = 20k -> 20% > 15%
        assert result.survives is False

    def test_custom_sensitivities(self) -> None:
        """Override sensitivities for custom scenario testing."""
        custom = {"custom": {"gold": -0.50}}
        positions = [Position("Gold", "long", 20_000.0)]
        result = stress_test_portfolio(
            positions, 100_000.0, "custom", sensitivities=custom,
        )
        # 20k * 50% loss = 10k -> 10%
        assert result.total_loss_pct == pytest.approx(10.0)


# ---------------------------------------------------------------------------
# check_stress_gate
# ---------------------------------------------------------------------------


class TestCheckStressGate:
    """Gate check: block if any scenario exceeds max_loss_pct."""

    def test_all_within_limits(self) -> None:
        results = [
            StressResult("a", "test", 5.0, "SPX", 10.0, [], True),
            StressResult("b", "test", 10.0, "SPX", 15.0, [], True),
        ]
        allowed, reason = check_stress_gate(results, max_loss_pct=15.0)
        assert allowed is True
        assert "within limits" in reason

    def test_one_exceeds(self) -> None:
        results = [
            StressResult("a", "test", 5.0, "SPX", 10.0, [], True),
            StressResult("b", "test", 20.0, "SPX", 25.0, [], False),
        ]
        allowed, reason = check_stress_gate(results, max_loss_pct=15.0)
        assert allowed is False
        assert "stress gate" in reason

    def test_empty_results(self) -> None:
        allowed, _ = check_stress_gate([])
        assert allowed is True

    def test_at_exact_limit(self) -> None:
        """Exactly at max_loss_pct -> blocked (>= comparison)."""
        results = [
            StressResult("a", "test", 15.0, "SPX", 15.0, [], False),
        ]
        allowed, _ = check_stress_gate(results, max_loss_pct=15.0)
        assert allowed is False


# ---------------------------------------------------------------------------
# run_all_stress_tests
# ---------------------------------------------------------------------------


class TestRunAllStressTests:
    """Run all four scenarios."""

    def test_empty_portfolio(self) -> None:
        results, allowed, reason = run_all_stress_tests([], 100_000.0)
        assert len(results) == 4
        assert allowed is True
        assert all(r.total_loss_pct == 0.0 for r in results)

    def test_four_scenarios_returned(self) -> None:
        positions = [Position("Gold", "long", 10_000.0)]
        results, allowed, reason = run_all_stress_tests(positions, 100_000.0)
        assert len(results) == 4
        scenario_names = {r.scenario_name for r in results}
        assert scenario_names == {"2008_gfc", "2020_covid", "2022_rate_shock", "flash_crash"}

    def test_large_position_blocked(self) -> None:
        """Massive SPX long -> 2008 scenario fails gate."""
        positions = [Position("SPX", "long", 90_000.0)]
        results, allowed, reason = run_all_stress_tests(positions, 100_000.0)
        # 90k * 40% = 36k loss -> 36% > 15%
        assert allowed is False
        assert "stress gate" in reason

    def test_small_gold_position_passes(self) -> None:
        """Small gold position survives all scenarios."""
        positions = [Position("Gold", "long", 5_000.0)]
        results, allowed, reason = run_all_stress_tests(positions, 100_000.0)
        assert allowed is True
