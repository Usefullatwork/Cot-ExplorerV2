"""Tests for src.analysis.rebalancer -- weekly portfolio rebalancing."""

from __future__ import annotations

import pytest

from src.analysis.rebalancer import (
    PositionState,
    RebalanceAction,
    RebalanceRecommendation,
    RebalanceReport,
    compute_signal_decay,
    compute_target_allocations,
    generate_rebalance_actions,
    should_close_position,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_position(
    instrument: str = "EURUSD",
    direction: str = "long",
    entry_score: int = 10,
    current_score: int = 10,
    days_held: int = 5,
    current_pnl_pips: float = 20.0,
    lot_size: float = 1.0,
) -> PositionState:
    """Create a PositionState with sensible defaults."""
    return PositionState(
        instrument=instrument,
        direction=direction,
        entry_score=entry_score,
        current_score=current_score,
        entry_date="2026-03-25",
        days_held=days_held,
        current_pnl_pips=current_pnl_pips,
        lot_size=lot_size,
    )


# ---------------------------------------------------------------------------
# compute_signal_decay
# ---------------------------------------------------------------------------


class TestComputeSignalDecay:
    """Tests for signal decay factor computation."""

    def test_high_score_recent_near_one(self) -> None:
        """Same score, just entered -> decay near 1.0."""
        decay = compute_signal_decay(
            current_score=10, entry_score=10, days_held=0,
        )
        assert decay == pytest.approx(1.0)

    def test_low_score_old_near_zero(self) -> None:
        """Low current score + long hold -> decay near 0.0."""
        decay = compute_signal_decay(
            current_score=1, entry_score=12, days_held=60,
        )
        assert decay < 0.1

    def test_half_life_exactly(self) -> None:
        """At exactly half_life_days, time_factor should be 0.5."""
        decay = compute_signal_decay(
            current_score=10, entry_score=10, days_held=14,
            half_life_days=14.0,
        )
        assert decay == pytest.approx(0.5, rel=1e-6)

    def test_clamped_to_zero(self) -> None:
        """Extreme decay should never go below 0.0."""
        decay = compute_signal_decay(
            current_score=0, entry_score=12, days_held=100,
        )
        assert decay >= 0.0

    def test_clamped_to_one(self) -> None:
        """Even with score improvement, decay should not exceed 1.0."""
        decay = compute_signal_decay(
            current_score=15, entry_score=10, days_held=0,
        )
        assert decay <= 1.0

    def test_entry_score_zero_safe(self) -> None:
        """entry_score=0 should not cause division by zero."""
        decay = compute_signal_decay(
            current_score=5, entry_score=0, days_held=7,
        )
        assert 0.0 <= decay <= 1.0


# ---------------------------------------------------------------------------
# should_close_position
# ---------------------------------------------------------------------------


class TestShouldClosePosition:
    """Tests for position closing decisions."""

    def test_signal_reversed_close(self) -> None:
        """current_score < 3 should trigger close for reversal."""
        pos = _make_position(current_score=2)
        close, reason = should_close_position(pos)
        assert close
        assert "reversed" in reason.lower()

    def test_signal_decayed_close(self) -> None:
        """Old position with declining score should close on decay."""
        pos = _make_position(
            entry_score=12, current_score=4, days_held=20,
        )
        close, reason = should_close_position(pos)
        assert close
        assert "decay" in reason.lower()

    def test_max_holding_exceeded_close(self) -> None:
        """Position held longer than max should close."""
        pos = _make_position(days_held=35, current_score=8)
        close, reason = should_close_position(pos, max_holding_days=30)
        assert close
        assert "hold" in reason.lower()

    def test_underwater_weak_score_close(self) -> None:
        """Deeply underwater + weak score should close."""
        pos = _make_position(current_pnl_pips=-150.0, current_score=4)
        close, reason = should_close_position(pos)
        assert close
        assert "underwater" in reason.lower()

    def test_healthy_position_hold(self) -> None:
        """Strong fresh position should not close."""
        pos = _make_position(
            entry_score=10, current_score=10, days_held=3,
            current_pnl_pips=50.0,
        )
        close, reason = should_close_position(pos)
        assert not close
        assert "healthy" in reason.lower()

    def test_underwater_but_strong_score_hold(self) -> None:
        """Underwater but strong score (>=5) should hold."""
        pos = _make_position(
            current_pnl_pips=-120.0, current_score=8, days_held=3,
            entry_score=10,
        )
        close, reason = should_close_position(pos)
        assert not close

    def test_exactly_at_max_holding_hold(self) -> None:
        """Exactly at max_holding_days should hold (> not >=)."""
        # Use high score to avoid triggering decay threshold
        pos = _make_position(
            days_held=30, current_score=12, entry_score=12,
            current_pnl_pips=50.0,
        )
        close, _ = should_close_position(
            pos, max_holding_days=30, decay_threshold=0.1,
        )
        assert not close


# ---------------------------------------------------------------------------
# compute_target_allocations
# ---------------------------------------------------------------------------


class TestComputeTargetAllocations:
    """Tests for target allocation computation."""

    def test_top_5_by_score(self) -> None:
        """Should pick top 5 by score when more instruments qualify."""
        signals = {
            f"INST_{i}": {"score": 6 + i, "direction": "long", "grade": "B"}
            for i in range(8)
        }
        allocs = compute_target_allocations(signals, regime="NORMAL")
        assert len(allocs) == 5
        # Highest scores should be included
        assert "INST_7" in allocs
        assert "INST_6" in allocs

    def test_below_threshold_excluded(self) -> None:
        """Instruments with score < 6 should be excluded."""
        signals = {
            "GOOD": {"score": 8, "direction": "long", "grade": "B"},
            "BAD": {"score": 4, "direction": "long", "grade": "D"},
        }
        allocs = compute_target_allocations(signals, regime="NORMAL")
        assert "GOOD" in allocs
        assert "BAD" not in allocs

    def test_weights_sum_to_one(self) -> None:
        """Weights should sum to 1.0."""
        signals = {
            "A": {"score": 10, "direction": "long", "grade": "A"},
            "B": {"score": 8, "direction": "long", "grade": "B"},
        }
        allocs = compute_target_allocations(signals, regime="NORMAL")
        assert sum(allocs.values()) == pytest.approx(1.0)

    def test_empty_signals_empty_result(self) -> None:
        """No signals should produce empty allocations."""
        allocs = compute_target_allocations({}, regime="NORMAL")
        assert allocs == {}

    def test_all_below_threshold_empty(self) -> None:
        """All scores below 6 should produce empty allocations."""
        signals = {
            "A": {"score": 3, "direction": "long", "grade": "D"},
            "B": {"score": 5, "direction": "long", "grade": "C"},
        }
        allocs = compute_target_allocations(signals, regime="NORMAL")
        assert allocs == {}

    def test_kelly_fractions_used_when_provided(self) -> None:
        """Kelly fractions should override score-based weighting."""
        signals = {
            "A": {"score": 10, "direction": "long", "grade": "A"},
            "B": {"score": 10, "direction": "long", "grade": "A"},
        }
        kelly = {"A": 0.3, "B": 0.1}
        allocs = compute_target_allocations(
            signals, regime="NORMAL", kelly_fractions=kelly,
        )
        # A should have higher weight (0.3 vs 0.1)
        assert allocs["A"] > allocs["B"]
        assert sum(allocs.values()) == pytest.approx(1.0)

    def test_kelly_zero_falls_back_to_score(self) -> None:
        """Kelly fraction of 0 for an instrument falls back to score."""
        signals = {
            "A": {"score": 8, "direction": "long", "grade": "B"},
        }
        kelly = {"A": 0.0}
        allocs = compute_target_allocations(
            signals, regime="NORMAL", kelly_fractions=kelly,
        )
        assert "A" in allocs
        assert allocs["A"] == pytest.approx(1.0)

    def test_max_positions_respected(self) -> None:
        """Should not exceed max_positions."""
        signals = {
            f"I{i}": {"score": 12, "direction": "long", "grade": "A+"}
            for i in range(10)
        }
        allocs = compute_target_allocations(
            signals, regime="NORMAL", max_positions=3,
        )
        assert len(allocs) == 3


# ---------------------------------------------------------------------------
# generate_rebalance_actions
# ---------------------------------------------------------------------------


class TestGenerateRebalanceActions:
    """Tests for rebalance action generation."""

    def test_close_decayed_position(self) -> None:
        """A decayed position should generate a close recommendation."""
        positions = [_make_position(
            instrument="EURUSD", current_score=2, entry_score=10,
        )]
        report = generate_rebalance_actions(
            positions, target_allocations={}, equity=100_000, regime="NORMAL",
        )
        assert isinstance(report, RebalanceReport)
        assert report.n_close >= 1
        close_rec = next(
            r for r in report.recommendations
            if r.action == RebalanceAction.CLOSE
        )
        assert close_rec.urgency == "immediate"

    def test_open_new_target(self) -> None:
        """An instrument in target but not held should generate open."""
        report = generate_rebalance_actions(
            current_positions=[],
            target_allocations={"GBPUSD": 0.5, "USDJPY": 0.5},
            equity=100_000,
            regime="NORMAL",
        )
        assert report.n_open == 2
        for rec in report.recommendations:
            assert rec.action == RebalanceAction.OPEN
            assert rec.urgency == "next_session"

    def test_hold_healthy_in_target(self) -> None:
        """A healthy position within target range should hold."""
        pos = _make_position(
            instrument="EURUSD", entry_score=10, current_score=10,
            days_held=3, lot_size=1.0, current_pnl_pips=50.0,
        )
        # Target allocation that results in ~1.0 lots for 100K equity
        target = {"EURUSD": 0.1}  # 0.1 * 100K / 10K = 1.0 lots
        report = generate_rebalance_actions(
            [pos], target, equity=100_000, regime="NORMAL",
        )
        assert report.n_hold == 1

    def test_close_not_in_target(self) -> None:
        """Position not in target allocations should close."""
        pos = _make_position(
            instrument="NZDUSD", entry_score=10, current_score=8,
            days_held=3, current_pnl_pips=10.0,
        )
        target = {"EURUSD": 1.0}  # NZDUSD not in target
        report = generate_rebalance_actions(
            [pos], target, equity=100_000, regime="NORMAL",
        )
        close_recs = [
            r for r in report.recommendations
            if r.instrument == "NZDUSD" and r.action == RebalanceAction.CLOSE
        ]
        assert len(close_recs) == 1

    def test_no_positions_no_targets(self) -> None:
        """No positions and no targets should produce empty report."""
        report = generate_rebalance_actions(
            current_positions=[], target_allocations={},
            equity=100_000, regime="NORMAL",
        )
        assert report.n_close == 0
        assert report.n_open == 0
        assert report.n_hold == 0
        assert report.total_positions == 0

    def test_all_positions_close_on_decay(self) -> None:
        """All deeply decayed positions should close."""
        positions = [
            _make_position(
                instrument=f"INST_{i}", current_score=1,
                entry_score=12, days_held=50,
            )
            for i in range(3)
        ]
        report = generate_rebalance_actions(
            positions, target_allocations={},
            equity=100_000, regime="NORMAL",
        )
        assert report.n_close == 3
        for rec in report.recommendations:
            assert rec.action == RebalanceAction.CLOSE

    def test_total_positions_includes_opens(self) -> None:
        """total_positions should count current + newly opened."""
        pos = _make_position(
            instrument="EURUSD", current_score=10, entry_score=10,
            days_held=2, lot_size=1.0, current_pnl_pips=10.0,
        )
        target = {"EURUSD": 0.1, "GBPUSD": 0.5}
        report = generate_rebalance_actions(
            [pos], target, equity=100_000, regime="NORMAL",
        )
        # 1 existing + 1 new open
        assert report.total_positions == 2

    def test_urgency_immediate_for_risk_close(self) -> None:
        """Risk-driven closures should have 'immediate' urgency."""
        pos = _make_position(current_score=1)
        report = generate_rebalance_actions(
            [pos], {}, equity=100_000, regime="NORMAL",
        )
        close_rec = report.recommendations[0]
        assert close_rec.urgency == "immediate"
