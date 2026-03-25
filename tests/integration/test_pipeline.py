"""Integration tests for the pipeline runner."""

from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch

import pytest

# Mock src.security.audit_log before importing runner, since the module
# may not exist on disk yet.
_mock_audit_mod = MagicMock()
sys.modules.setdefault("src.security", MagicMock())
sys.modules.setdefault("src.security.audit_log", _mock_audit_mod)

from src.pipeline.runner import run_full_pipeline  # noqa: E402


@pytest.fixture()
def mock_subprocess():
    """Patch subprocess.run so no real scripts execute."""
    with patch("subprocess.run") as m:
        m.return_value = MagicMock(returncode=0)
        yield m


def test_run_full_pipeline_all_ok(mock_subprocess):
    """All stages complete with 'ok' when subprocess succeeds."""
    with patch("src.pipeline.runner._stage_output"):
        results = run_full_pipeline()

    assert "calendar" in results
    assert "cot" in results
    assert "push" in results
    for stage, outcome in results.items():
        assert outcome == "ok", f"Stage {stage} failed: {outcome}"


def test_run_full_pipeline_returns_all_stages(mock_subprocess):
    """Pipeline returns results for all 8 stages."""
    with patch("src.pipeline.runner._stage_output"):
        results = run_full_pipeline()

    expected_stages = {"calendar", "cot", "combine", "fundamentals", "prices", "scoring", "output", "push"}
    assert set(results.keys()) == expected_stages


def test_pipeline_stage_failure_does_not_halt(mock_subprocess):
    """A failing stage is logged but subsequent stages still run."""
    call_count = 0

    def _raise_once(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise RuntimeError("calendar fetch failed")

    mock_subprocess.side_effect = _raise_once

    with patch("src.pipeline.runner._stage_output"):
        results = run_full_pipeline()

    assert "error" in results["calendar"]
    # Later stages should still run
    assert results["combine"] == "ok"


def test_pipeline_calls_subprocess_for_stages(mock_subprocess):
    """Verify subprocess.run is called for script-based stages."""
    with patch("src.pipeline.runner._stage_output"):
        run_full_pipeline()

    # calendar, cot, fundamentals, prices, scoring, push = 6 subprocess calls
    assert mock_subprocess.call_count >= 5


def test_pipeline_output_stage_with_no_macro_file(mock_subprocess, tmp_path, monkeypatch):
    """Output stage handles missing macro data gracefully."""
    # Point macro data to empty tmp dir so _stage_output finds no file
    monkeypatch.chdir(tmp_path)
    results = run_full_pipeline()
    # Output stage should not crash
    assert results["output"] == "ok"


def test_pipeline_result_values_are_strings(mock_subprocess):
    """All result values should be strings ('ok' or 'error: ...')."""
    with patch("src.pipeline.runner._stage_output"):
        results = run_full_pipeline()

    for stage, outcome in results.items():
        assert isinstance(outcome, str), f"Stage {stage} has non-string outcome: {type(outcome)}"
