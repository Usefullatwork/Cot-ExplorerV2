"""Tests for src.analysis.kelly -- Kelly criterion position sizing."""

from __future__ import annotations

import math

import pytest

from src.analysis.kelly import (
    KellyResult,
    compute_kelly,
    half_kelly,
    kelly_fraction,
    kelly_position_size,
)


# ---------------------------------------------------------------------------
# kelly_fraction
# ---------------------------------------------------------------------------


class TestKellyFraction:
    """Full Kelly fraction f* = (bp - q) / b."""

    def test_positive_edge_60pct_1to1(self) -> None:
        """60% win rate, 1:1 RR -> f* = (1*0.6 - 0.4)/1 = 0.2."""
        result = kelly_fraction(0.6, 1.0, 1.0)
        assert result == pytest.approx(0.2)

    def test_no_edge_50pct_1to1(self) -> None:
        """50% win rate, 1:1 RR -> f* = 0 (no edge)."""
        result = kelly_fraction(0.5, 1.0, 1.0)
        assert result == pytest.approx(0.0)

    def test_negative_edge_40pct(self) -> None:
        """40% win rate, 1:1 RR -> negative edge -> clamped to 0."""
        result = kelly_fraction(0.4, 1.0, 1.0)
        assert result == 0.0

    def test_high_rr_low_winrate(self) -> None:
        """30% win rate, 3:1 RR -> f* = (3*0.3 - 0.7)/3 = 0.0667."""
        result = kelly_fraction(0.3, 3.0, 1.0)
        assert result == pytest.approx(2 / 30, rel=1e-4)

    def test_perfect_winrate(self) -> None:
        """100% win rate -> f* = 1.0 (bet everything)."""
        result = kelly_fraction(1.0, 2.0, 1.0)
        assert result == pytest.approx(1.0)

    def test_clamped_to_one(self) -> None:
        """Extreme edge should not exceed 1.0."""
        result = kelly_fraction(0.99, 100.0, 1.0)
        assert result <= 1.0

    def test_zero_avg_loss(self) -> None:
        """avg_loss = 0 -> 0.0 (avoid division by zero)."""
        assert kelly_fraction(0.6, 1.0, 0.0) == 0.0

    def test_zero_avg_win(self) -> None:
        """avg_win = 0 -> 0.0 (no upside)."""
        assert kelly_fraction(0.6, 0.0, 1.0) == 0.0

    def test_zero_win_rate(self) -> None:
        """win_rate = 0 -> 0.0."""
        assert kelly_fraction(0.0, 2.0, 1.0) == 0.0


# ---------------------------------------------------------------------------
# half_kelly
# ---------------------------------------------------------------------------


class TestHalfKelly:
    """Half-Kelly with max_fraction clamp."""

    def test_half_of_full(self) -> None:
        """Half-Kelly = full / 2."""
        full = kelly_fraction(0.6, 1.0, 1.0)
        result = half_kelly(0.6, 1.0, 1.0, max_fraction=1.0)
        assert result == pytest.approx(full / 2.0)

    def test_clamped_to_max_fraction(self) -> None:
        """High edge half-Kelly clamped to max_fraction."""
        result = half_kelly(0.9, 5.0, 1.0, max_fraction=0.25)
        assert result <= 0.25

    def test_no_edge_returns_zero(self) -> None:
        """No edge -> half-Kelly = 0."""
        assert half_kelly(0.5, 1.0, 1.0) == 0.0

    def test_default_max_fraction(self) -> None:
        """Default max_fraction is 0.25."""
        result = half_kelly(0.95, 10.0, 1.0)
        assert result <= 0.25


# ---------------------------------------------------------------------------
# kelly_position_size
# ---------------------------------------------------------------------------


class TestKellyPositionSize:
    """Lot size from half-Kelly."""

    def test_known_calculation(self) -> None:
        """Verify lot calculation with known inputs."""
        equity = 100_000.0
        win_rate = 0.6
        avg_win = 1.5
        avg_loss = 1.0
        entry = 1.1000
        sl = 1.0950
        pip_size = 0.0001
        pip_val = 10.0

        hk = half_kelly(win_rate, avg_win, avg_loss)
        risk_amount = equity * hk
        sl_pips = abs(entry - sl) / pip_size  # 50 pips
        risk_per_lot = sl_pips * pip_val  # 500
        expected_lots = risk_amount / risk_per_lot

        result = kelly_position_size(
            equity, win_rate, avg_win, avg_loss, entry, sl, pip_size, pip_val,
        )
        assert result == pytest.approx(expected_lots, rel=1e-6)

    def test_zero_equity(self) -> None:
        assert kelly_position_size(0.0, 0.6, 1.5, 1.0, 1.1, 1.095) == 0.0

    def test_zero_sl_distance(self) -> None:
        """Entry == stop loss -> 0 lots."""
        assert kelly_position_size(100_000, 0.6, 1.5, 1.0, 1.1, 1.1) == 0.0

    def test_no_edge(self) -> None:
        """No edge -> 0 lots."""
        assert kelly_position_size(100_000, 0.5, 1.0, 1.0, 1.1, 1.095) == 0.0

    def test_negative_equity(self) -> None:
        assert kelly_position_size(-100, 0.6, 1.5, 1.0, 1.1, 1.095) == 0.0


# ---------------------------------------------------------------------------
# compute_kelly
# ---------------------------------------------------------------------------


class TestComputeKelly:
    """Compute KellyResult from raw P&L list."""

    def test_mixed_trades(self) -> None:
        """Standard mix of wins and losses."""
        trades = [100.0, -50.0, 80.0, -40.0, 120.0, -60.0]
        result = compute_kelly(trades)

        assert result.win_rate == pytest.approx(3 / 6)
        assert result.avg_win == pytest.approx(100.0)
        assert result.avg_loss == pytest.approx(50.0)
        assert result.full_kelly > 0.0
        assert result.half_kelly == pytest.approx(result.full_kelly / 2.0)
        assert result.quarter_kelly == pytest.approx(result.full_kelly / 4.0)

    def test_all_wins(self) -> None:
        """All winning trades -> avg_loss=0 -> kelly=0 (can't compute b)."""
        trades = [100.0, 200.0, 50.0]
        result = compute_kelly(trades)
        assert result.win_rate == pytest.approx(1.0)
        assert result.avg_loss == 0.0
        assert result.full_kelly == 0.0

    def test_all_losses(self) -> None:
        """All losing trades -> win_rate=0 -> kelly=0."""
        trades = [-100.0, -50.0, -75.0]
        result = compute_kelly(trades)
        assert result.win_rate == 0.0
        assert result.full_kelly == 0.0

    def test_single_win(self) -> None:
        trades = [100.0]
        result = compute_kelly(trades)
        assert result.win_rate == 1.0
        assert result.avg_win == 100.0

    def test_single_loss(self) -> None:
        trades = [-50.0]
        result = compute_kelly(trades)
        assert result.win_rate == 0.0
        assert result.full_kelly == 0.0

    def test_empty_list(self) -> None:
        result = compute_kelly([])
        assert result.full_kelly == 0.0
        assert result.win_rate == 0.0
        assert result.edge == 0.0

    def test_zeros_ignored(self) -> None:
        """Zero P&L trades are excluded from calculation."""
        trades = [100.0, 0.0, -50.0, 0.0]
        result = compute_kelly(trades)
        assert result.win_rate == pytest.approx(0.5)

    def test_edge_positive(self) -> None:
        """Edge = win_rate * avg_win - (1-win_rate) * avg_loss."""
        trades = [200.0, -50.0, 150.0, -60.0]
        result = compute_kelly(trades)
        expected_edge = result.win_rate * result.avg_win - (1 - result.win_rate) * result.avg_loss
        assert result.edge == pytest.approx(expected_edge)
