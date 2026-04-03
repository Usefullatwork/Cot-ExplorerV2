"""Tests for Layer 2 runner helper functions."""

from __future__ import annotations

from src.pipeline.layer2_runner import _compute_daily_returns, _positions_to_stress_format

# ── _compute_daily_returns ───────────────────────────────────────────────────


def test_compute_returns_normal():
    closes = [100.0, 101.0, 102.01, 100.99]
    rets = _compute_daily_returns(closes)
    assert len(rets) == 3
    assert abs(rets[0] - 0.01) < 0.001
    assert abs(rets[1] - 0.01) < 0.001


def test_compute_returns_empty():
    assert _compute_daily_returns([]) == []
    assert _compute_daily_returns([100.0]) == []


def test_compute_returns_two_prices():
    rets = _compute_daily_returns([100.0, 110.0])
    assert len(rets) == 1
    assert abs(rets[0] - 0.10) < 0.001


def test_compute_returns_negative():
    rets = _compute_daily_returns([100.0, 90.0])
    assert len(rets) == 1
    assert abs(rets[0] - (-0.10)) < 0.001


# ── _positions_to_stress_format ──────────────────────────────────────────────


class MockPosition:
    def __init__(self, instrument, direction, entry_price, lot_size):
        self.instrument = instrument
        self.direction = direction
        self.entry_price = entry_price
        self.lot_size = lot_size


def test_positions_to_stress_bull():
    pos = MockPosition("EURUSD", "bull", 1.1, 0.5)
    result = _positions_to_stress_format([pos])
    assert len(result) == 1
    assert result[0].direction == "long"
    assert result[0].instrument == "EURUSD"
    assert result[0].value_usd == abs(1.1 * 0.5)


def test_positions_to_stress_bear():
    pos = MockPosition("Gold", "bear", 2000.0, 0.1)
    result = _positions_to_stress_format([pos])
    assert result[0].direction == "short"


def test_positions_to_stress_empty():
    assert _positions_to_stress_format([]) == []


def test_positions_to_stress_multiple():
    positions = [
        MockPosition("EURUSD", "bull", 1.1, 1.0),
        MockPosition("Gold", "bear", 2000.0, 0.5),
    ]
    result = _positions_to_stress_format(positions)
    assert len(result) == 2
    assert result[0].instrument == "EURUSD"
    assert result[1].instrument == "Gold"
