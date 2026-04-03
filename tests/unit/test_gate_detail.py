"""Tests for gate orchestrator detail field enhancement."""

import json
from dataclasses import asdict
from unittest.mock import MagicMock

import pytest

from src.pipeline.gate_orchestrator import (
    GateDecision,
    GateResult,
    _gate_kill_switch,
    _gate_signal_health,
    _gate_var,
    _gate_stress,
)


class TestGateResultDetail:
    """Verify that gate results include human-readable detail strings."""

    def test_gate_result_has_detail_field(self):
        gr = GateResult("test", True, "OK", detail="Test detail")
        assert gr.detail == "Test detail"

    def test_gate_result_default_empty_detail(self):
        gr = GateResult("test", True, "OK")
        assert gr.detail == ""

    def test_gate_result_serializes_detail(self):
        gr = GateResult("test", True, "OK", detail="Test detail")
        d = asdict(gr)
        assert "detail" in d
        assert d["detail"] == "Test detail"

    def test_kill_switch_off_detail(self):
        config = MagicMock()
        config.kill_switch_active = False
        result = _gate_kill_switch(config)
        assert result.passed is True
        assert "OFF" in result.detail

    def test_kill_switch_on_detail(self):
        config = MagicMock()
        config.kill_switch_active = True
        config.kill_switch_reason = "Manual halt"
        result = _gate_kill_switch(config)
        assert result.passed is False
        assert "BLOCKED" in result.detail
        assert "Manual halt" in result.detail

    def test_signal_health_no_data_detail(self):
        signal = MagicMock()
        result = _gate_signal_health(signal, None)
        assert result.passed is True
        assert "no weight data" in result.detail

    def test_signal_health_healthy_detail(self):
        signal = MagicMock()
        signal.instrument = "EURUSD"
        state = MagicMock()
        state.signal_weights_json = json.dumps({"EURUSD": 0.85})
        result = _gate_signal_health(signal, state)
        assert result.passed is True
        assert "EURUSD" in result.detail
        assert "0.85" in result.detail
        assert "PASSED" in result.detail

    def test_signal_health_degraded_detail(self):
        signal = MagicMock()
        signal.instrument = "EURUSD"
        state = MagicMock()
        state.signal_weights_json = json.dumps({"EURUSD": 0.35})
        result = _gate_signal_health(signal, state)
        assert result.passed is True
        assert "degraded" in result.detail
        assert "70%" in result.detail

    def test_signal_health_dead_detail(self):
        signal = MagicMock()
        signal.instrument = "EURUSD"
        state = MagicMock()
        state.signal_weights_json = json.dumps({"EURUSD": 0.0})
        result = _gate_signal_health(signal, state)
        assert result.passed is False
        assert "BLOCKED" in result.detail
        assert "dead" in result.detail

    def test_var_no_data_detail(self):
        state = MagicMock()
        state.var_95_pct = None
        result = _gate_var(state)
        assert "no VaR data" in result.detail

    def test_var_passed_with_headroom(self):
        state = MagicMock()
        state.var_95_pct = 0.015  # 1.5% as fraction
        result = _gate_var(state)
        assert result.passed is True
        assert "PASSED" in result.detail

    def test_var_blocked_detail(self):
        state = MagicMock()
        state.var_95_pct = 0.025  # 2.5% as fraction — exceeds 0.02 limit
        result = _gate_var(state)
        assert result.passed is False
        assert "BLOCKED" in result.detail

    def test_stress_passed_with_margin(self):
        state = MagicMock()
        state.stress_survives = True
        state.stress_worst_pct = 8.0
        result = _gate_stress(state)
        assert result.passed is True
        assert "8.0%" in result.detail
        assert "PASSED" in result.detail
        assert "7.0% margin" in result.detail

    def test_stress_blocked_detail(self):
        state = MagicMock()
        state.stress_survives = False
        state.stress_worst_pct = 18.0
        result = _gate_stress(state)
        assert result.passed is False
        assert "18.0%" in result.detail
        assert "BLOCKED" in result.detail
