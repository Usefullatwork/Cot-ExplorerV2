"""
DAG-based Agent Orchestration Engine

Manages scheduling and ordering of agent tasks. Does NOT call LLMs.
Determines which agents should run, in what order, and validates
that dependencies are satisfied before execution proceeds.

Usage:
    plan = build_execution_plan(agents, mode="full")
    state = execute_plan(plan, executor=my_callback)
    report = summarize_pipeline(state)
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable

logger = logging.getLogger(__name__)


# ── Data classes ─────────────────────────────────────────────────────


@dataclass(frozen=True)
class AgentTask:
    """A scheduled agent task."""

    agent_id: str
    category: str
    subcategory: str
    schedule: str  # "every_run", "daily", "weekly"
    instruments: list[str]  # which instruments this agent handles
    depends_on: list[str]  # agent IDs that must complete first
    priority: int  # lower = higher priority (0-9)


@dataclass
class AgentResult:
    """Result from a completed agent task."""

    agent_id: str
    success: bool
    output: Any  # agent output (dict, string, etc.)
    error: str | None = None
    duration_ms: int = 0


@dataclass
class PipelineState:
    """Current state of the orchestration pipeline."""

    scheduled: list[AgentTask] = field(default_factory=list)
    completed: list[AgentResult] = field(default_factory=list)
    failed: list[AgentResult] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)


# ── Category dependency graph ────────────────────────────────────────

# Categories that must complete before others can start.
# Categories not listed here default to no dependencies.
_CATEGORY_DEPENDENCIES: dict[str, list[str]] = {
    "market_analysis": [],
    "fundamental": [],
    "macro_analysis": [],
    "signal_validation": ["market_analysis"],
    "strategy_selection": ["market_analysis", "fundamental"],
    "risk_management": ["signal_validation", "strategy_selection"],
    "trading_execution": ["risk_management"],
    "backtesting": [],
}

# Default priority per category (lower = runs earlier within a wave).
_CATEGORY_PRIORITY: dict[str, int] = {
    "market_analysis": 0,
    "fundamental": 1,
    "macro_analysis": 1,
    "signal_validation": 3,
    "strategy_selection": 4,
    "risk_management": 6,
    "trading_execution": 8,
    "backtesting": 5,
}


# ── Public API ───────────────────────────────────────────────────────


def build_execution_plan(
    available_agents: list[dict],
    mode: str = "full",
    instrument: str | None = None,
    schedule_filter: str | None = None,
) -> list[list[AgentTask]]:
    """Build a DAG-based execution plan from available agents.

    Args:
        available_agents: list of agent dicts from registry
            (keys: id, category, subcategory, schedule, instrument).
        mode: "full" (all agents), "instrument" (filter by instrument).
        instrument: when mode="instrument", only include agents for
            this instrument.
        schedule_filter: "every_run", "daily", "weekly" -- only include
            agents matching this schedule.

    Returns:
        List of waves (each wave is a list of AgentTasks that can run
        in parallel). Waves are ordered by dependency: wave 0 has no
        deps, wave 1 depends on wave 0, etc.
    """
    filtered = _filter_agents(available_agents, mode, instrument, schedule_filter)
    tasks = _build_tasks(filtered)
    return topological_sort_waves(tasks)


def topological_sort_waves(tasks: list[AgentTask]) -> list[list[AgentTask]]:
    """Sort tasks into parallel execution waves using Kahn's algorithm.

    Wave 0: tasks with no dependencies.
    Wave N: tasks whose dependencies are all in waves 0..N-1.
    Within each wave, sort by priority (lower first).

    Raises ValueError if a dependency cycle is detected.
    """
    if not tasks:
        return []

    task_map: dict[str, AgentTask] = {t.agent_id: t for t in tasks}
    all_ids = set(task_map.keys())

    # Build in-degree counts (only count deps that are in our task set)
    in_degree: dict[str, int] = {}
    for t in tasks:
        local_deps = [d for d in t.depends_on if d in all_ids]
        in_degree[t.agent_id] = len(local_deps)

    waves: list[list[AgentTask]] = []
    placed: set[str] = set()

    while placed != all_ids:
        # Find tasks whose dependencies are all placed
        wave = [
            task_map[tid]
            for tid in sorted(all_ids - placed)
            if in_degree[tid] == 0
        ]
        if not wave:
            remaining = all_ids - placed
            raise ValueError(
                f"Dependency cycle detected among: {sorted(remaining)}"
            )

        wave.sort(key=lambda t: (t.priority, t.agent_id))
        waves.append(wave)

        for t in wave:
            placed.add(t.agent_id)
            # Decrement in-degree for dependents
            for other in tasks:
                if t.agent_id in other.depends_on and other.agent_id in all_ids:
                    in_degree[other.agent_id] = max(
                        0, in_degree[other.agent_id] - 1
                    )

    return waves


def execute_plan(
    plan: list[list[AgentTask]],
    executor: Callable[[AgentTask], AgentResult],
    fail_fast: bool = False,
) -> PipelineState:
    """Execute a plan wave by wave.

    For each wave:
    1. Run all tasks in the wave (via executor callback).
    2. Collect results.
    3. If a task fails and fail_fast=True: skip all subsequent waves.
    4. If a task fails and fail_fast=False: skip only tasks that
       depend on the failed one (transitively).

    The executor is a callback: (AgentTask) -> AgentResult.
    This allows testing without actual LLM calls.
    """
    all_tasks = [task for wave in plan for task in wave]
    state = PipelineState(scheduled=list(all_tasks))
    failed_ids: set[str] = set()

    for wave_idx, wave in enumerate(plan):
        if fail_fast and failed_ids:
            for task in wave:
                state.skipped.append(task.agent_id)
                logger.info("Skipped %s (fail_fast after failure)", task.agent_id)
            continue

        for task in wave:
            # Skip if any dependency failed
            if _has_failed_dependency(task, failed_ids):
                state.skipped.append(task.agent_id)
                logger.info(
                    "Skipped %s (depends on failed agent)", task.agent_id
                )
                continue

            start = time.monotonic_ns()
            try:
                result = executor(task)
            except Exception as exc:
                elapsed_ms = (time.monotonic_ns() - start) // 1_000_000
                result = AgentResult(
                    agent_id=task.agent_id,
                    success=False,
                    output=None,
                    error=str(exc),
                    duration_ms=int(elapsed_ms),
                )

            if result.success:
                state.completed.append(result)
                logger.debug("Completed %s", task.agent_id)
            else:
                state.failed.append(result)
                failed_ids.add(task.agent_id)
                logger.warning("Failed %s: %s", task.agent_id, result.error)

    return state


def get_ready_agents(
    state: PipelineState,
    all_tasks: list[AgentTask],
) -> list[AgentTask]:
    """Get tasks that are ready to execute (all deps satisfied).

    A task is ready when:
    - It has not been completed, failed, or skipped.
    - All of its dependencies are in state.completed.
    """
    completed_ids = {r.agent_id for r in state.completed}
    failed_ids = {r.agent_id for r in state.failed}
    done_ids = completed_ids | failed_ids | set(state.skipped)

    ready: list[AgentTask] = []
    for task in all_tasks:
        if task.agent_id in done_ids:
            continue
        deps_in_set = [d for d in task.depends_on if _is_known_task(d, all_tasks)]
        if all(d in completed_ids for d in deps_in_set):
            ready.append(task)

    ready.sort(key=lambda t: (t.priority, t.agent_id))
    return ready


def summarize_pipeline(state: PipelineState) -> dict:
    """Generate summary report of pipeline execution.

    Returns:
        Dictionary with total_scheduled, completed, failed, skipped,
        success_rate, categories_completed, and failed_agents.
    """
    total = len(state.scheduled)
    completed = len(state.completed)
    failed = len(state.failed)
    skipped = len(state.skipped)
    attempted = completed + failed
    success_rate = (completed / attempted) if attempted > 0 else 0.0

    categories_completed = sorted(
        {r.agent_id.rsplit("_", 1)[0] for r in state.completed}
        if state.completed
        else set()
    )

    return {
        "total_scheduled": total,
        "completed": completed,
        "failed": failed,
        "skipped": skipped,
        "success_rate": round(success_rate, 4),
        "categories_completed": categories_completed,
        "failed_agents": [r.agent_id for r in state.failed],
    }


# ── Internal helpers ─────────────────────────────────────────────────


def _filter_agents(
    agents: list[dict],
    mode: str,
    instrument: str | None,
    schedule_filter: str | None,
) -> list[dict]:
    """Filter agent dicts by mode, instrument, and schedule."""
    result = list(agents)

    if mode == "instrument" and instrument is not None:
        result = [
            a for a in result
            if instrument in (a.get("instrument") or [])
            or not a.get("instrument")
        ]

    if schedule_filter is not None:
        result = [
            a for a in result
            if a.get("schedule", "every_run") == schedule_filter
        ]

    return result


def _build_tasks(agents: list[dict]) -> list[AgentTask]:
    """Convert agent dicts to AgentTask instances with dependency info."""
    # Collect all agent IDs grouped by category
    ids_by_category: dict[str, list[str]] = {}
    for a in agents:
        cat = a.get("category", "unknown")
        ids_by_category.setdefault(cat, []).append(a["id"])

    tasks: list[AgentTask] = []
    for a in agents:
        cat = a.get("category", "unknown")
        dep_categories = _CATEGORY_DEPENDENCIES.get(cat, [])

        # Depend on all agents from required categories
        depends_on: list[str] = []
        for dep_cat in dep_categories:
            depends_on.extend(ids_by_category.get(dep_cat, []))

        instruments = a.get("instrument") or []
        if isinstance(instruments, str):
            instruments = [instruments]

        task = AgentTask(
            agent_id=a["id"],
            category=cat,
            subcategory=a.get("subcategory", ""),
            schedule=a.get("schedule", "every_run"),
            instruments=instruments,
            depends_on=depends_on,
            priority=_CATEGORY_PRIORITY.get(cat, 5),
        )
        tasks.append(task)

    return tasks


def _has_failed_dependency(task: AgentTask, failed_ids: set[str]) -> bool:
    """Check if any dependency (direct) has failed."""
    return bool(set(task.depends_on) & failed_ids)


def _is_known_task(agent_id: str, all_tasks: list[AgentTask]) -> bool:
    """Check if an agent_id is among the known tasks."""
    return any(t.agent_id == agent_id for t in all_tasks)
