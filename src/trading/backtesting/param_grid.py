"""
Parameter grid definitions for walk-forward optimization.

Defines default parameter ranges and utilities for generating
all combinations (grid search) and estimating runtime.
"""

import itertools
from typing import Any

# Default parameter grid for optimization.
# Each key maps to a list of candidate values to test.
DEFAULT_PARAM_GRID: dict[str, list[Any]] = {
    "sl_atr_multiplier": [1.5, 2.0, 2.5, 3.0],
    "tp_rr_ratio": [1.5, 2.0, 2.5, 3.0],
    "min_score": [4, 5, 6, 7, 8],
    "candle_exit_bars": [6, 8, 10, 12],
    "ema_filter": [True, False],
}

# Timeframes supported by the optimizer.
# The backtesting engine operates on weekly COT data,
# so these represent conceptual analysis windows, not bar intervals.
TIMEFRAMES: list[str] = ["5m", "15m", "1H", "4H", "D1"]


def generate_combinations(param_grid: dict[str, list[Any]]) -> list[dict[str, Any]]:
    """Generate all parameter combinations from a grid.

    Uses itertools.product to create the Cartesian product of all
    parameter value lists. Each combination is returned as a dict.

    Args:
        param_grid: Mapping of parameter names to lists of candidate values.

    Returns:
        List of dicts, each representing one parameter combination.

    Example:
        >>> grid = {"a": [1, 2], "b": [True, False]}
        >>> combos = generate_combinations(grid)
        >>> len(combos)
        4
    """
    if not param_grid:
        return [{}]

    keys = sorted(param_grid.keys())
    values = [param_grid[k] for k in keys]

    combinations = []
    for combo in itertools.product(*values):
        combinations.append(dict(zip(keys, combo)))

    return combinations


def estimate_runtime(
    n_instruments: int,
    n_combinations: int,
    n_windows: int,
    n_strategies: int = 1,
    n_timeframes: int = 1,
    seconds_per_run: float = 0.05,
) -> str:
    """Estimate total runtime for user feedback.

    Args:
        n_instruments: Number of instruments to optimize.
        n_combinations: Number of parameter combinations per strategy.
        n_windows: Number of walk-forward windows.
        n_strategies: Number of strategies to test.
        n_timeframes: Number of timeframes to test.
        seconds_per_run: Estimated seconds per single backtest run.

    Returns:
        Human-readable runtime estimate string.
    """
    total_runs = n_instruments * n_strategies * n_timeframes * n_combinations * n_windows
    total_seconds = total_runs * seconds_per_run

    if total_seconds < 60:
        return f"~{total_seconds:.0f}s ({total_runs:,} backtests)"
    elif total_seconds < 3600:
        minutes = total_seconds / 60
        return f"~{minutes:.1f}m ({total_runs:,} backtests)"
    else:
        hours = total_seconds / 3600
        return f"~{hours:.1f}h ({total_runs:,} backtests)"
