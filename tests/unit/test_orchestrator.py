"""Unit tests for src.agents.orchestrator — DAG execution planning and pipeline."""

from __future__ import annotations

import pytest

from src.agents.orchestrator import (
    AgentResult,
    AgentTask,
    PipelineState,
    build_execution_plan,
    execute_plan,
    get_ready_agents,
    summarize_pipeline,
    topological_sort_waves,
)

# ── Fixtures ─────────────────────────────────────────────────────────


def _agent(
    aid: str,
    category: str,
    subcategory: str = "default",
    schedule: str = "every_run",
    instrument: list[str] | None = None,
) -> dict:
    """Create a minimal agent dict matching the registry format."""
    return {
        "id": aid,
        "category": category,
        "subcategory": subcategory,
        "schedule": schedule,
        "instrument": instrument,
    }


def _make_all_category_agents() -> list[dict]:
    """Create one agent per category for a full-plan test."""
    return [
        _agent("ma_trend", "market_analysis", "trend"),
        _agent("fa_macro", "fundamental", "macro_policy"),
        _agent("macro_yield", "macro_analysis", "yield_curve"),
        _agent("sv_confluence", "signal_validation", "confluence_check"),
        _agent("ss_regime", "strategy_selection", "regime_switching"),
        _agent("rm_sizing", "risk_management", "position_sizing"),
        _agent("te_entry", "trading_execution", "entry_confirmation"),
        _agent("bt_eval", "backtesting", "evaluation"),
    ]


def _ok_executor(task: AgentTask) -> AgentResult:
    """Executor that always succeeds."""
    return AgentResult(agent_id=task.agent_id, success=True, output={"ok": True})


def _fail_executor(task: AgentTask) -> AgentResult:
    """Executor that always fails."""
    return AgentResult(
        agent_id=task.agent_id, success=False, output=None, error="boom"
    )


def _selective_fail_executor(fail_ids: set[str]):
    """Return an executor that fails for specific agent IDs."""

    def _exec(task: AgentTask) -> AgentResult:
        if task.agent_id in fail_ids:
            return AgentResult(
                agent_id=task.agent_id, success=False, output=None, error="boom"
            )
        return AgentResult(
            agent_id=task.agent_id, success=True, output={"ok": True}
        )

    return _exec


# ── build_execution_plan ─────────────────────────────────────────────


class TestBuildExecutionPlan:
    """Building execution plans from agent dicts."""

    def test_full_mode_includes_all_categories(self):
        agents = _make_all_category_agents()
        plan = build_execution_plan(agents, mode="full")
        all_ids = {t.agent_id for wave in plan for t in wave}
        assert all_ids == {
            "ma_trend", "fa_macro", "macro_yield", "sv_confluence",
            "ss_regime", "rm_sizing", "te_entry", "bt_eval",
        }

    def test_instrument_mode_filters_by_instrument(self):
        agents = [
            _agent("a", "market_analysis", instrument=["EURUSD"]),
            _agent("b", "market_analysis", instrument=["XAUUSD"]),
            _agent("c", "fundamental"),  # no instrument -> included
        ]
        plan = build_execution_plan(agents, mode="instrument", instrument="EURUSD")
        all_ids = {t.agent_id for wave in plan for t in wave}
        assert "a" in all_ids
        assert "c" in all_ids  # cross-instrument
        assert "b" not in all_ids

    def test_schedule_filter_excludes_non_matching(self):
        agents = [
            _agent("daily_agent", "market_analysis", schedule="daily"),
            _agent("weekly_agent", "market_analysis", schedule="weekly"),
        ]
        plan = build_execution_plan(agents, schedule_filter="weekly")
        all_ids = {t.agent_id for wave in plan for t in wave}
        assert all_ids == {"weekly_agent"}

    def test_schedule_filter_daily_excludes_weekly(self):
        agents = [
            _agent("d1", "fundamental", schedule="daily"),
            _agent("w1", "fundamental", schedule="weekly"),
            _agent("e1", "fundamental", schedule="every_run"),
        ]
        plan = build_execution_plan(agents, schedule_filter="daily")
        all_ids = {t.agent_id for wave in plan for t in wave}
        assert all_ids == {"d1"}

    def test_empty_agents_returns_empty_plan(self):
        plan = build_execution_plan([], mode="full")
        assert plan == []

    def test_single_agent_produces_single_wave(self):
        agents = [_agent("solo", "backtesting")]
        plan = build_execution_plan(agents, mode="full")
        assert len(plan) == 1
        assert len(plan[0]) == 1
        assert plan[0][0].agent_id == "solo"


# ── topological_sort_waves ───────────────────────────────────────────


class TestTopologicalSortWaves:
    """Topological sorting into parallel execution waves."""

    def test_no_deps_all_in_wave_zero(self):
        tasks = [
            AgentTask("a", "market_analysis", "x", "daily", [], [], 0),
            AgentTask("b", "fundamental", "x", "daily", [], [], 1),
        ]
        waves = topological_sort_waves(tasks)
        assert len(waves) == 1
        ids = [t.agent_id for t in waves[0]]
        assert set(ids) == {"a", "b"}

    def test_market_analysis_before_signal_validation(self):
        """market_analysis (wave 0) before signal_validation (wave 1)."""
        agents = _make_all_category_agents()
        plan = build_execution_plan(agents, mode="full")
        wave_0_ids = {t.agent_id for t in plan[0]}
        assert "ma_trend" in wave_0_ids

        # signal_validation depends on market_analysis
        sv_wave = None
        for i, wave in enumerate(plan):
            for t in wave:
                if t.agent_id == "sv_confluence":
                    sv_wave = i
        assert sv_wave is not None and sv_wave > 0

    def test_trading_execution_in_last_wave(self):
        """trading_execution should be in the deepest wave."""
        agents = _make_all_category_agents()
        plan = build_execution_plan(agents, mode="full")
        last_wave_ids = {t.agent_id for t in plan[-1]}
        assert "te_entry" in last_wave_ids

    def test_backtesting_in_wave_zero(self):
        """backtesting has no deps, should be in wave 0."""
        agents = _make_all_category_agents()
        plan = build_execution_plan(agents, mode="full")
        wave_0_ids = {t.agent_id for t in plan[0]}
        assert "bt_eval" in wave_0_ids

    def test_priority_ordering_within_wave(self):
        """Within a wave, lower priority number comes first."""
        tasks = [
            AgentTask("high", "x", "x", "daily", [], [], 9),
            AgentTask("low", "x", "x", "daily", [], [], 0),
            AgentTask("mid", "x", "x", "daily", [], [], 5),
        ]
        waves = topological_sort_waves(tasks)
        ids = [t.agent_id for t in waves[0]]
        assert ids == ["low", "mid", "high"]

    def test_empty_tasks_returns_empty(self):
        assert topological_sort_waves([]) == []

    def test_unknown_category_defaults_to_no_deps(self):
        agents = [_agent("custom", "exotic_category")]
        plan = build_execution_plan(agents, mode="full")
        assert len(plan) == 1
        assert plan[0][0].agent_id == "custom"


# ── execute_plan ─────────────────────────────────────────────────────


class TestExecutePlan:
    """Executing plans with success and failure scenarios."""

    def test_all_succeed(self):
        agents = _make_all_category_agents()
        plan = build_execution_plan(agents, mode="full")
        state = execute_plan(plan, _ok_executor)
        assert len(state.completed) == 8
        assert len(state.failed) == 0
        assert len(state.skipped) == 0

    def test_one_failure_skips_dependents(self):
        """Failing market_analysis skips signal_validation and downstream."""
        agents = _make_all_category_agents()
        plan = build_execution_plan(agents, mode="full")
        executor = _selective_fail_executor({"ma_trend"})
        state = execute_plan(plan, executor)

        failed_ids = {r.agent_id for r in state.failed}
        assert "ma_trend" in failed_ids

        # signal_validation depends on market_analysis -> skipped
        assert "sv_confluence" in state.skipped

    def test_fail_fast_stops_after_first_failure(self):
        agents = _make_all_category_agents()
        plan = build_execution_plan(agents, mode="full")
        # Fail an agent in wave 0
        executor = _selective_fail_executor({"ma_trend"})
        state = execute_plan(plan, executor, fail_fast=True)

        # Wave 0 completes (some succeed, one fails), but all
        # subsequent waves are skipped entirely
        assert len(state.failed) >= 1
        # Everything after wave 0 is skipped
        wave_0_ids = {t.agent_id for t in plan[0]}
        for wave in plan[1:]:
            for task in wave:
                assert task.agent_id in state.skipped

    def test_executor_exception_captured_as_failure(self):
        def _raise(task: AgentTask) -> AgentResult:
            raise RuntimeError("unexpected crash")

        agents = [_agent("crasher", "backtesting")]
        plan = build_execution_plan(agents, mode="full")
        state = execute_plan(plan, _raise)
        assert len(state.failed) == 1
        assert "unexpected crash" in state.failed[0].error

    def test_empty_plan_returns_empty_state(self):
        state = execute_plan([], _ok_executor)
        assert len(state.scheduled) == 0
        assert len(state.completed) == 0


# ── get_ready_agents ─────────────────────────────────────────────────


class TestGetReadyAgents:
    """Determining which tasks are ready to run."""

    def test_wave_0_ready_initially(self):
        agents = _make_all_category_agents()
        plan = build_execution_plan(agents, mode="full")
        all_tasks = [t for wave in plan for t in wave]
        state = PipelineState(scheduled=all_tasks)
        ready = get_ready_agents(state, all_tasks)
        ready_ids = {t.agent_id for t in ready}
        # All wave-0 tasks should be ready
        wave_0_ids = {t.agent_id for t in plan[0]}
        assert wave_0_ids == ready_ids

    def test_after_wave_0_completes_wave_1_ready(self):
        agents = _make_all_category_agents()
        plan = build_execution_plan(agents, mode="full")
        all_tasks = [t for wave in plan for t in wave]

        # Simulate wave 0 completion
        state = PipelineState(
            scheduled=all_tasks,
            completed=[
                AgentResult(agent_id=t.agent_id, success=True, output={})
                for t in plan[0]
            ],
        )
        ready = get_ready_agents(state, all_tasks)
        ready_ids = {t.agent_id for t in ready}

        # Wave 1 tasks should now be ready
        if len(plan) > 1:
            wave_1_ids = {t.agent_id for t in plan[1]}
            assert wave_1_ids.issubset(ready_ids)

    def test_failed_dep_blocks_dependents(self):
        agents = _make_all_category_agents()
        plan = build_execution_plan(agents, mode="full")
        all_tasks = [t for wave in plan for t in wave]

        # market_analysis failed, others in wave 0 completed
        completed = [
            AgentResult(agent_id=t.agent_id, success=True, output={})
            for t in plan[0]
            if t.agent_id != "ma_trend"
        ]
        state = PipelineState(
            scheduled=all_tasks,
            completed=completed,
            failed=[AgentResult(agent_id="ma_trend", success=False, output=None)],
        )
        ready = get_ready_agents(state, all_tasks)
        ready_ids = {t.agent_id for t in ready}

        # signal_validation depends on market_analysis -> NOT ready
        assert "sv_confluence" not in ready_ids


# ── summarize_pipeline ───────────────────────────────────────────────


class TestSummarizePipeline:
    """Pipeline summary generation."""

    def test_all_completed(self):
        agents = _make_all_category_agents()
        plan = build_execution_plan(agents, mode="full")
        state = execute_plan(plan, _ok_executor)
        report = summarize_pipeline(state)
        assert report["total_scheduled"] == 8
        assert report["completed"] == 8
        assert report["failed"] == 0
        assert report["skipped"] == 0
        assert report["success_rate"] == 1.0

    def test_partial_failure_rate(self):
        state = PipelineState(
            scheduled=[],
            completed=[
                AgentResult(agent_id="a_ok", success=True, output={}),
                AgentResult(agent_id="b_ok", success=True, output={}),
            ],
            failed=[
                AgentResult(agent_id="c_fail", success=False, output=None, error="x"),
            ],
            skipped=["d_skip"],
        )
        report = summarize_pipeline(state)
        assert report["completed"] == 2
        assert report["failed"] == 1
        assert report["skipped"] == 1
        # success_rate = 2 / (2+1) = 0.6667
        assert abs(report["success_rate"] - 0.6667) < 0.001
        assert report["failed_agents"] == ["c_fail"]

    def test_empty_pipeline(self):
        state = PipelineState()
        report = summarize_pipeline(state)
        assert report["total_scheduled"] == 0
        assert report["success_rate"] == 0.0
        assert report["categories_completed"] == []
        assert report["failed_agents"] == []
