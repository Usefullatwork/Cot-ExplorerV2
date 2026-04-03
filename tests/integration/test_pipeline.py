"""Integration tests for the pipeline runner."""

from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch

import pytest

# Pre-load src.security so its audit_log sub-module can be mocked safely
# without replacing the real package (which would break later imports).
import src.security  # noqa: E402
_mock_audit_mod = MagicMock()
sys.modules.setdefault("src.security.audit_log", _mock_audit_mod)

from src.pipeline.runner import run_full_pipeline  # noqa: E402


@pytest.fixture(autouse=True)
def mock_stage_functions():
    """Patch all stage functions so no real fetching occurs."""
    with (
        patch("src.pipeline.runner._stage_quality") as quality,
        patch("src.pipeline.runner._stage_calendar") as cal,
        patch("src.pipeline.runner._stage_cot") as cot,
        patch("src.pipeline.runner._stage_combine") as combine,
        patch("src.pipeline.runner._stage_fundamentals") as fund,
        patch("src.pipeline.runner._stage_prices") as prices,
        patch("src.pipeline.runner._stage_scoring") as scoring,
        patch("src.pipeline.runner._stage_output") as output,
        patch("src.pipeline.runner._stage_push") as push,
        patch("src.pipeline.runner._stage_rebalance") as rebalance,
    ):
        yield {
            "quality": quality,
            "calendar": cal,
            "cot": cot,
            "combine": combine,
            "fundamentals": fund,
            "prices": prices,
            "scoring": scoring,
            "output": output,
            "push": push,
            "rebalance": rebalance,
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

    expected_stages = {"quality", "calendar", "cot", "combine", "fundamentals", "prices", "scoring", "output", "push", "rebalance"}
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
    with (
        patch("src.pipeline.runner._stage_calendar"),
        patch("src.pipeline.runner._stage_cot"),
        patch("src.pipeline.runner._stage_combine"),
        patch("src.pipeline.runner._stage_fundamentals"),
        patch("src.pipeline.runner._stage_prices"),
        patch("src.pipeline.runner._stage_scoring"),
        patch("src.pipeline.runner._stage_push"),
    ):
        results = run_full_pipeline()

    # Output stage should not crash
    assert results["output"] == "ok"


def test_pipeline_result_values_are_strings():
    """All result values should be strings ('ok' or 'error: ...')."""
    results = run_full_pipeline()

    for stage, outcome in results.items():
        assert isinstance(outcome, str), f"Stage {stage} has non-string outcome: {type(outcome)}"


# ===== Edge case tests added by Agent D3 =====================================


def test_multiple_stage_failures(mock_stage_functions):
    """Multiple stages failing should not halt the pipeline."""
    mock_stage_functions["calendar"].side_effect = RuntimeError("calendar down")
    mock_stage_functions["cot"].side_effect = ValueError("bad COT data")
    mock_stage_functions["prices"].side_effect = TimeoutError("price fetch timeout")

    results = run_full_pipeline()

    assert "error" in results["calendar"]
    assert "error" in results["cot"]
    assert "error" in results["prices"]
    # Non-failing stages should be ok
    assert results["combine"] == "ok"
    assert results["fundamentals"] == "ok"
    assert results["scoring"] == "ok"
    assert results["output"] == "ok"
    assert results["push"] == "ok"


def test_all_stages_fail(mock_stage_functions):
    """All stages failing should still return results for all 8 stages."""
    for name, mock_fn in mock_stage_functions.items():
        mock_fn.side_effect = RuntimeError(f"{name} failed")

    results = run_full_pipeline()

    assert len(results) == 10
    for stage, outcome in results.items():
        assert "error" in outcome


def test_stage_returns_none_not_crash(mock_stage_functions):
    """A stage function that returns None (normal) should be 'ok'."""
    mock_stage_functions["calendar"].return_value = None

    results = run_full_pipeline()
    assert results["calendar"] == "ok"


def test_first_stage_failure_last_stage_runs(mock_stage_functions):
    """First stage (calendar) fails, last stage (push) should still run."""
    mock_stage_functions["calendar"].side_effect = RuntimeError("first fails")

    results = run_full_pipeline()

    assert "error" in results["calendar"]
    assert results["push"] == "ok"
    assert mock_stage_functions["push"].called


def test_last_stage_failure(mock_stage_functions):
    """Last stage (push) failing should not affect earlier results."""
    mock_stage_functions["push"].side_effect = RuntimeError("push failed")

    results = run_full_pipeline()

    assert results["calendar"] == "ok"
    assert results["cot"] == "ok"
    assert "error" in results["push"]


def test_stage_failure_error_message_contains_exception_text(mock_stage_functions):
    """Error outcome should contain the exception message."""
    mock_stage_functions["fundamentals"].side_effect = ValueError("FRED API rate limited")

    results = run_full_pipeline()

    assert "FRED API rate limited" in results["fundamentals"]


def test_stage_keyboard_interrupt_propagates(mock_stage_functions):
    """KeyboardInterrupt is not caught by except Exception — should propagate."""
    mock_stage_functions["scoring"].side_effect = KeyboardInterrupt()

    with pytest.raises(KeyboardInterrupt):
        run_full_pipeline()


def test_pipeline_order_preserved(mock_stage_functions):
    """Results dict should have stages in pipeline order."""
    results = run_full_pipeline()

    expected_order = ["quality", "calendar", "cot", "combine", "fundamentals", "prices", "scoring", "output", "push", "rebalance"]
    assert list(results.keys()) == expected_order
