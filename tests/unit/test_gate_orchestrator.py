"""Tests for the 8-gate chain-of-responsibility orchestrator."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from src.pipeline.gate_orchestrator import (
    GateDecision,
    GateResult,
    _assign_automation_level,
    _gate_correlation,
    _gate_kill_switch,
    _gate_regime,
    _gate_signal_health,
    _gate_stress,
    _gate_var,
    evaluate_signal,
)


# ── Fixtures ─────────────────────────────────────────────────────────────────


def _make_signal(**overrides):
    sig = MagicMock()
    sig.id = overrides.get("id", 1)
    sig.instrument = overrides.get("instrument", "EURUSD")
    sig.direction = overrides.get("direction", "bull")
    sig.grade = overrides.get("grade", "A")
    sig.score = overrides.get("score", 8)
    sig.entry_price = overrides.get("entry_price", 1.1000)
    sig.stop_loss = overrides.get("stop_loss", 1.0950)
    sig.target_1 = overrides.get("target_1", 1.1100)
    sig.target_2 = overrides.get("target_2", None)
    return sig


def _make_state(**overrides):
    state = MagicMock()
    state.var_95_pct = overrides.get("var_95_pct", 0.01)
    state.var_99_pct = overrides.get("var_99_pct", 0.02)
    state.cvar_95_pct = overrides.get("cvar_95_pct", 0.015)
    state.stress_survives = overrides.get("stress_survives", True)
    state.stress_worst_pct = overrides.get("stress_worst_pct", 8.0)
    state.regime = overrides.get("regime", "normal")
    state.open_position_count = overrides.get("open_position_count", 1)
    state.signal_weights_json = overrides.get("signal_weights_json", '{"EURUSD": 1.2}')
    state.correlation_max = overrides.get("correlation_max", 0.3)
    state.kelly_cache_json = overrides.get("kelly_cache_json", None)
    state.risk_parity_json = overrides.get("risk_parity_json", None)
    state.vix_price = overrides.get("vix_price", 18.0)
    return state


def _make_config(**overrides):
    config = MagicMock()
    config.kill_switch_active = overrides.get("kill_switch_active", False)
    config.kill_switch_reason = overrides.get("kill_switch_reason", None)
    config.risk_pct = overrides.get("risk_pct", 0.01)
    return config


# ── Gate 1: Kill switch ──────────────────────────────────────────────────────


def test_kill_switch_off():
    g = _gate_kill_switch(_make_config(kill_switch_active=False))
    assert g.passed is True


def test_kill_switch_on():
    g = _gate_kill_switch(_make_config(kill_switch_active=True, kill_switch_reason="Emergency"))
    assert g.passed is False
    assert "Emergency" in g.reason


def test_kill_switch_none_config():
    g = _gate_kill_switch(None)
    assert g.passed is True


# ── Gate 2: Signal health ────────────────────────────────────────────────────


def test_signal_health_healthy():
    g = _gate_signal_health(_make_signal(), _make_state())
    assert g.passed is True
    assert g.size_multiplier == 1.0


def test_signal_health_dead_signal():
    state = _make_state(signal_weights_json='{"EURUSD": 0.0}')
    g = _gate_signal_health(_make_signal(), state)
    assert g.passed is False


def test_signal_health_degraded():
    state = _make_state(signal_weights_json='{"EURUSD": 0.3}')
    g = _gate_signal_health(_make_signal(), state)
    assert g.passed is True
    assert g.size_multiplier == 0.7


def test_signal_health_no_state():
    g = _gate_signal_health(_make_signal(), None)
    assert g.passed is True


# ── Gate 3: VaR ──────────────────────────────────────────────────────────────


def test_var_gate_pass():
    g = _gate_var(_make_state(var_95_pct=0.015))
    assert g.passed is True


def test_var_gate_fail():
    g = _gate_var(_make_state(var_95_pct=0.03))
    assert g.passed is False


def test_var_gate_no_data():
    g = _gate_var(_make_state(var_95_pct=None))
    assert g.passed is True


# ── Gate 4: Stress ───────────────────────────────────────────────────────────


def test_stress_gate_survives():
    g = _gate_stress(_make_state(stress_survives=True, stress_worst_pct=8.0))
    assert g.passed is True


def test_stress_gate_fails():
    g = _gate_stress(_make_state(stress_survives=False, stress_worst_pct=18.0))
    assert g.passed is False


# ── Gate 5: Regime ───────────────────────────────────────────────────────────


def test_regime_gate_normal():
    g = _gate_regime(_make_state(regime="normal", open_position_count=2))
    assert g.passed is True


def test_regime_gate_crisis_full():
    g = _gate_regime(_make_state(regime="crisis", open_position_count=1))
    assert g.passed is False


# ── Gate 6: Correlation ──────────────────────────────────────────────────────


def test_correlation_no_conflict():
    session = MagicMock()
    session.query.return_value.filter.return_value.all.return_value = []
    g = _gate_correlation(_make_signal(instrument="USDJPY"), session)
    assert g.passed is True


def test_correlation_with_correlated_open():
    session = MagicMock()
    pos = MagicMock()
    pos.instrument = "GBPUSD"
    session.query.return_value.filter.return_value.all.return_value = [pos]
    g = _gate_correlation(_make_signal(instrument="EURUSD"), session)
    assert g.passed is True
    assert g.size_multiplier == 0.5  # reduced


# ── Automation level ─────────────────────────────────────────────────────────


def test_automation_a_plus():
    sig = _make_signal(grade="A+", score=10)
    gates = [GateResult("g1", True, "ok", 1.0)]
    level = _assign_automation_level(sig, gates, True)
    assert level == "A+"


def test_automation_a():
    sig = _make_signal(grade="A", score=8)
    gates = [GateResult("g1", True, "ok", 0.8)]
    level = _assign_automation_level(sig, gates, True)
    assert level == "A"


def test_automation_b_no_state():
    sig = _make_signal(grade="A+", score=10)
    gates = [GateResult("g1", True, "ok", 1.0)]
    level = _assign_automation_level(sig, gates, False)
    assert level == "B"


def test_automation_b_low_multiplier():
    sig = _make_signal(grade="B", score=6)
    gates = [GateResult("g1", True, "ok", 0.5)]
    level = _assign_automation_level(sig, gates, True)
    assert level == "B"


# ── Full chain ───────────────────────────────────────────────────────────────


def test_evaluate_signal_all_pass():
    session = MagicMock()
    session.query.return_value.filter.return_value.all.return_value = []
    decision = evaluate_signal(
        _make_signal(), _make_state(), _make_config(), session,
    )
    assert decision.passed is True
    assert len(decision.gate_results) == 8


def test_evaluate_signal_kill_switch_blocks():
    session = MagicMock()
    decision = evaluate_signal(
        _make_signal(), _make_state(),
        _make_config(kill_switch_active=True), session,
    )
    assert decision.passed is False
    assert decision.blocking_gate == "kill_switch"
    assert len(decision.gate_results) == 1
