"""Tests for the execution bridge routing logic."""

from __future__ import annotations

from unittest.mock import MagicMock

from src.pipeline.execution_bridge import (
    ExecutionResult,
    _log_blocked,
    _notify_and_wait,
    execute_decisions,
)
from src.pipeline.gate_orchestrator import GateDecision


def _make_decision(**overrides) -> GateDecision:
    return GateDecision(
        signal_id=overrides.get("signal_id", 1),
        passed=overrides.get("passed", True),
        automation_level=overrides.get("automation_level", "A+"),
        final_lot_size=overrides.get("final_lot_size", 0.1),
    )


def test_blocked_returns_blocked():
    session = MagicMock()
    session.add = MagicMock()
    session.flush = MagicMock()
    d = _make_decision(automation_level="blocked", passed=False, blocking_gate="var_gate")
    result = _log_blocked(d, session)
    assert result.action == "blocked"
    assert result.lot_size == 0.0


def test_notify_returns_notified():
    session = MagicMock()
    sig = MagicMock()
    sig.id = 1
    sig.instrument = "EURUSD"
    sig.direction = "bull"
    session.get.return_value = sig
    session.add = MagicMock()
    session.flush = MagicMock()

    d = _make_decision(automation_level="B")
    result = _notify_and_wait(d, session)
    assert result.action == "notified"
    assert result.lot_size == 0.1


def test_notify_signal_not_found():
    session = MagicMock()
    session.get.return_value = None
    d = _make_decision(automation_level="B")
    result = _notify_and_wait(d, session)
    assert result.action == "blocked"
    assert "not found" in result.error


def test_execute_decisions_routes_correctly():
    session = MagicMock()
    sig = MagicMock()
    sig.id = 1
    sig.instrument = "EURUSD"
    sig.direction = "bull"
    session.get.return_value = sig
    session.add = MagicMock()
    session.flush = MagicMock()

    decisions = [
        _make_decision(signal_id=1, automation_level="B"),
        _make_decision(signal_id=2, automation_level="blocked", passed=False),
    ]
    results = execute_decisions(decisions, session)
    assert len(results) == 2
    assert results[0].action == "notified"
    assert results[1].action == "blocked"


def test_execute_result_dataclass():
    r = ExecutionResult(signal_id=1, action="executed", lot_size=0.5, broker_order_id="123")
    assert r.signal_id == 1
    assert r.action == "executed"
    assert r.broker_order_id == "123"
    assert r.error is None
