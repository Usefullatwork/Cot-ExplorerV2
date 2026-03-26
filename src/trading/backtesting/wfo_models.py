"""
Data models for walk-forward optimization.

Dataclasses for window-level results and aggregated optimization output.
Kept separate from backtesting models to avoid circular imports.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class WindowResult:
    """Result of a single backtest run within one walk-forward window.

    Attributes:
        window_start: ISO date string for window start.
        window_end: ISO date string for window end.
        is_train: True if this is in-sample (train), False if out-of-sample (test).
        strategy: Strategy class name.
        timeframe: Timeframe label (e.g. "D1", "4H").
        params: Parameter dict used for this run.
        metrics: Performance metrics dict (sharpe, win_rate, etc.).
        composite_score: Weighted composite score for ranking.
    """

    window_start: str
    window_end: str
    is_train: bool
    strategy: str
    timeframe: str
    params: dict[str, Any]
    metrics: dict[str, float]
    composite_score: float


@dataclass
class OptimizationResult:
    """Aggregated result of a full walk-forward optimization for one instrument.

    Attributes:
        instrument: Instrument key (e.g. "eurusd").
        total_windows: Number of walk-forward windows used.
        total_combinations: Total strategy x timeframe x param combos tested.
        runtime_seconds: Wall-clock time for the full optimization.
        train_results: All in-sample window results.
        test_results: All out-of-sample window results.
        best_combo: Dict with best strategy, timeframe, params, and avg test score.
        ranking: List of combo dicts sorted by average out-of-sample score.
    """

    instrument: str
    total_windows: int
    total_combinations: int
    runtime_seconds: float
    train_results: list[WindowResult] = field(default_factory=list)
    test_results: list[WindowResult] = field(default_factory=list)
    best_combo: dict[str, Any] = field(default_factory=dict)
    ranking: list[dict[str, Any]] = field(default_factory=list)
