"""
Optimization report generator.

Produces JSON reports, human-readable summaries, per-instrument/per-strategy
rankings, and stability analysis from walk-forward optimization results.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict
from typing import Any

from .wfo_models import OptimizationResult, WindowResult


class OptimizationReport:
    """Generate reports from walk-forward optimization results."""

    # ------------------------------------------------------------------ JSON
    def generate_json(self, results: OptimizationResult) -> dict[str, Any]:
        """Full JSON-serializable report with all results and metadata.

        Args:
            results: Output from WalkForwardOptimizer.run().

        Returns:
            Dict containing instrument, rankings, best combo, and all
            window-level results.
        """
        return {
            "instrument": results.instrument,
            "total_windows": results.total_windows,
            "total_combinations": results.total_combinations,
            "runtime_seconds": round(results.runtime_seconds, 2),
            "best_combo": results.best_combo,
            "ranking": results.ranking[:20],  # top 20
            "train_results": [asdict(w) for w in results.train_results],
            "test_results": [asdict(w) for w in results.test_results],
        }

    # -------------------------------------------------------------- Summary
    def generate_summary(self, results: OptimizationResult) -> str:
        """Human-readable text summary of top 5 combos.

        Args:
            results: Output from WalkForwardOptimizer.run().

        Returns:
            Multi-line formatted string.
        """
        lines = []
        sep = "=" * 70
        lines.append(sep)
        lines.append(f"  WALK-FORWARD OPTIMIZATION: {results.instrument}")
        lines.append(sep)
        lines.append(f"  Windows:       {results.total_windows}")
        lines.append(f"  Combinations:  {results.total_combinations}")
        lines.append(f"  Runtime:       {results.runtime_seconds:.1f}s")
        lines.append("")

        if results.best_combo:
            lines.append("-" * 70)
            lines.append("  BEST COMBINATION (out-of-sample)")
            lines.append("-" * 70)
            bc = results.best_combo
            lines.append(f"  Strategy:    {bc.get('strategy', '?')}")
            lines.append(f"  Timeframe:   {bc.get('timeframe', '?')}")
            lines.append(f"  Avg Score:   {bc.get('avg_test_score', 0):.4f}")
            params = bc.get("params", {})
            if params:
                lines.append(f"  Parameters:  {_format_params(params)}")
            lines.append("")

        lines.append("-" * 70)
        lines.append("  TOP 5 RANKED COMBINATIONS")
        lines.append("-" * 70)
        lines.append(
            f"  {'Rank':<5} {'Strategy':<18} {'TF':<5} "
            f"{'Score':>8} {'Sharpe':>8} {'WinR':>6} {'DD':>6}"
        )
        lines.append(f"  {'-' * 5} {'-' * 18} {'-' * 5} {'-' * 8} {'-' * 8} {'-' * 6} {'-' * 6}")

        for i, r in enumerate(results.ranking[:5], 1):
            lines.append(
                f"  {i:<5} {r.get('strategy', '?'):<18} "
                f"{r.get('timeframe', '?'):<5} "
                f"{r.get('avg_test_score', 0):>8.4f} "
                f"{r.get('avg_sharpe', 0):>8.3f} "
                f"{r.get('avg_win_rate', 0):>5.1f}% "
                f"{r.get('avg_max_dd', 0):>5.1f}%"
            )

        lines.append("")
        lines.append(sep)
        return "\n".join(lines)

    # ------------------------------------------------------- Per instrument
    def best_per_instrument(
        self, all_results: dict[str, OptimizationResult]
    ) -> dict[str, dict[str, Any]]:
        """For each instrument, return the best strategy + timeframe + params.

        Args:
            all_results: Mapping of instrument name to OptimizationResult.

        Returns:
            Dict mapping instrument to its best combo dict.
        """
        out: dict[str, dict[str, Any]] = {}
        for inst, result in all_results.items():
            if result.best_combo:
                out[inst] = {
                    "instrument": inst,
                    **result.best_combo,
                }
        return out

    # -------------------------------------------------------- Per strategy
    def best_per_strategy(
        self, all_results: dict[str, OptimizationResult]
    ) -> dict[str, dict[str, Any]]:
        """For each strategy, return the best timeframe + params across instruments.

        Aggregates all ranking entries across instruments, groups by strategy,
        and picks the combo with the highest average test score.

        Args:
            all_results: Mapping of instrument name to OptimizationResult.

        Returns:
            Dict mapping strategy name to its best combo.
        """
        strategy_scores: dict[str, list[dict[str, Any]]] = {}

        for inst, result in all_results.items():
            for entry in result.ranking:
                strat = entry.get("strategy", "?")
                strategy_scores.setdefault(strat, []).append(
                    {"instrument": inst, **entry}
                )

        out: dict[str, dict[str, Any]] = {}
        for strat, entries in strategy_scores.items():
            best = max(entries, key=lambda e: e.get("avg_test_score", 0))
            out[strat] = best

        return out

    # ---------------------------------------------------- Stability analysis
    def stability_analysis(self, results: OptimizationResult) -> dict[str, Any]:
        """Check if best params are stable across walk-forward windows.

        Flags parameter sets that only performed well in a single window,
        indicating overfitting risk.

        Args:
            results: Output from WalkForwardOptimizer.run().

        Returns:
            Dict with stability metrics and warnings.
        """
        if not results.test_results:
            return {"stable": False, "reason": "no_test_results", "warnings": []}

        best = results.best_combo
        if not best:
            return {"stable": False, "reason": "no_best_combo", "warnings": []}

        best_strat = best.get("strategy")
        best_tf = best.get("timeframe")
        best_params = best.get("params", {})

        # Find all test windows for the best combo
        matching_windows: list[WindowResult] = []
        for w in results.test_results:
            if w.strategy == best_strat and w.timeframe == best_tf and w.params == best_params:
                matching_windows.append(w)

        warnings: list[str] = []
        n_windows = len(matching_windows)

        if n_windows <= 1:
            warnings.append("Best params only tested in 1 window -- high overfitting risk")

        # Check score variance across windows
        scores = [w.composite_score for w in matching_windows]
        if len(scores) >= 2:
            mean_score = sum(scores) / len(scores)
            variance = sum((s - mean_score) ** 2 for s in scores) / (len(scores) - 1)
            std_dev = variance ** 0.5
            cv = std_dev / mean_score if mean_score != 0 else float("inf")

            if cv > 0.5:
                warnings.append(
                    f"High score variance across windows (CV={cv:.2f}) -- unstable"
                )

        # Check for negative test windows
        negative_count = sum(1 for s in scores if s < 0)
        if negative_count > 0:
            warnings.append(
                f"{negative_count}/{n_windows} test windows had negative scores"
            )

        return {
            "stable": len(warnings) == 0,
            "n_test_windows": n_windows,
            "scores_by_window": scores,
            "warnings": warnings,
        }

    # --------------------------------------------------------- Save to disk
    def save(
        self, results: OptimizationResult, output_dir: str, prefix: str = "wfo"
    ) -> dict[str, str]:
        """Save optimization report files to disk.

        Args:
            results: Optimization results.
            output_dir: Directory to write to.
            prefix: Filename prefix.

        Returns:
            Dict mapping file type to path.
        """
        os.makedirs(output_dir, exist_ok=True)

        json_path = os.path.join(output_dir, f"{prefix}_results.json")
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(self.generate_json(results), f, indent=2, default=str)

        txt_path = os.path.join(output_dir, f"{prefix}_summary.txt")
        with open(txt_path, "w", encoding="utf-8") as f:
            f.write(self.generate_summary(results))

        return {"json": json_path, "summary": txt_path}


def _format_params(params: dict[str, Any]) -> str:
    """Format parameter dict as a compact string."""
    parts = [f"{k}={v}" for k, v in sorted(params.items())]
    return ", ".join(parts)
