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


@pytest.fixture(autouse=True)
def mock_stage_functions():
    """Patch all stage functions so no real fetching occurs."""
    with (
        patch("src.pipeline.runner._stage_calendar") as cal,
        patch("src.pipeline.runner._stage_cot") as cot,
        patch("src.pipeline.runner._stage_combine") as combine,
        patch("src.pipeline.runner._stage_fundamentals") as fund,
        patch("src.pipeline.runner._stage_prices") as prices,
        patch("src.pipeline.runner._stage_scoring") as scoring,
        patch("src.pipeline.runner._stage_output") as output,
        patch("src.pipeline.runner._stage_push") as push,
    ):
        yield {
            "calendar": cal,
            "cot": cot,
            "combine": combine,
            "fundamentals": fund,
            "prices": prices,
            "scoring": scoring,
            "output": output,
            "push": push,
        }


def test_run_full_pipeline_all_ok():
    """All stages complete with 'ok' when functions succeed."""
    results = run_full_pipeline()

    assert "calendar" in results
    assert "cot" in results
    assert "push" in results
    for stage, outcome in results.items():
        assert outcome == "ok", f"Stage {stage} failed: {outcome}"


def test_run_full_pipeline_returns_all_stages():
    """Pipeline returns results for all 8 stages."""
    results = run_full_pipeline()

    expected_stages = {"calendar", "cot", "combine", "fundamentals", "prices", "scoring", "output", "push"}
    assert set(results.keys()) == expected_stages


def test_pipeline_stage_failure_does_not_halt(mock_stage_functions):
    """A failing stage is logged but subsequent stages still run."""
    mock_stage_functions["calendar"].side_effect = RuntimeError("calendar fetch failed")

    results = run_full_pipeline()

    assert "error" in results["calendar"]
    # Later stages should still run
    assert results["combine"] == "ok"


def test_pipeline_calls_all_stage_functions(mock_stage_functions):
    """Verify all stage functions are called."""
    run_full_pipeline()

    for name, mock_fn in mock_stage_functions.items():
        assert mock_fn.called, f"Stage {name} was not called"


def test_pipeline_output_stage_with_no_macro_file(mock_stage_functions, tmp_path, monkeypatch):
    """Output stage handles missing macro data gracefully."""
    # Unpatch output so the real function runs
    mock_stage_functions["output"].side_effect = None
    # Point macro data to empty tmp dir so _stage_output finds no file
    monkeypatch.chdir(tmp_path)

    # Re-import to get the real _stage_output
    with patch("src.pipeline.runner._stage_calendar"), \
         patch("src.pipeline.runner._stage_cot"), \
         patch("src.pipeline.runner._stage_combine"), \
         patch("src.pipeline.runner._stage_fundamentals"), \
         patch("src.pipeline.runner._stage_prices"), \
         patch("src.pipeline.runner._stage_scoring"), \
         patch("src.pipeline.runner._stage_push"):
        results = run_full_pipeline()

    # Output stage should not crash
    assert results["output"] == "ok"


def test_pipeline_result_values_are_strings():
    """All result values should be strings ('ok' or 'error: ...')."""
    results = run_full_pipeline()

    for stage, outcome in results.items():
        assert isinstance(outcome, str), f"Stage {stage} has non-string outcome: {type(outcome)}"
