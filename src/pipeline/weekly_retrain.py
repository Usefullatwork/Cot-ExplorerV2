"""Friday weekly retrain pipeline orchestrator.

Loads recent signal performance data, computes updated signal weights,
checks for distribution drift, and saves reports.  This module DOES
perform I/O (read/write JSON files).

Best-effort pipeline -- failures in any step are logged, not raised.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import date
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class RetrainResult:
    """Result of weekly retrain pipeline."""

    date: str
    signal_weights_updated: bool
    drift_detected: bool
    drift_details: list[str]
    rebalance_actions: int
    quality_score: float
    errors: list[str]


def _load_signal_log(data_dir: Path) -> dict[str, list[bool]] | None:
    """Load signal_log.json and convert to outcome dict.

    Expected format: list of objects with "signal_id" and "outcome" keys.
    Returns {signal_id: [bool outcomes]} or None if file missing/invalid.
    """
    log_path = data_dir / "signal_log.json"
    if not log_path.exists():
        logger.info("No signal_log.json found at %s -- skipping", log_path)
        return None

    try:
        with open(log_path, encoding="utf-8") as f:
            records = json.load(f)
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Failed to read signal_log.json: %s", exc)
        return None

    if not isinstance(records, list):
        logger.warning("signal_log.json is not a list -- skipping")
        return None

    outcomes: dict[str, list[bool]] = {}
    for rec in records:
        sig_id = rec.get("signal_id")
        outcome = rec.get("outcome")
        if sig_id is not None and isinstance(outcome, bool):
            outcomes.setdefault(sig_id, []).append(outcome)

    return outcomes if outcomes else None


def _save_json(path: Path, data: dict) -> bool:
    """Write JSON data to path, creating parent dirs as needed.

    Returns True on success, False on failure.
    """
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        logger.info("Saved %s", path)
        return True
    except OSError as exc:
        logger.error("Failed to write %s: %s", path, exc)
        return False


def run_weekly_retrain(
    data_dir: str | Path = "data",
    output_dir: str | Path = "data/retrain",
) -> RetrainResult:
    """Run the Friday weekly retrain pipeline.

    Steps:
    1. Load recent signal performance data from data/signal_log.json
    2. Compute signal weights via signal_monitor.compute_signal_weights()
    3. Check for drift via drift_detector.detect_feature_drift()
    4. Save updated weights to data/retrain/{date}_weights.json
    5. Generate rebalance recommendations (placeholder: log only)
    6. Save full report to data/retrain/{date}_report.json

    Best-effort -- failures in any step are logged but don't block.
    If data files don't exist, skip gracefully.

    Args:
        data_dir: Directory containing signal_log.json.
        output_dir: Directory to write retrain output files.

    Returns:
        RetrainResult summarizing the pipeline run.
    """
    data_path = Path(data_dir)
    out_path = Path(output_dir)
    today = date.today().isoformat()
    errors: list[str] = []
    weights_updated = False
    drift_detected = False
    drift_details: list[str] = []
    quality_score = 0.0

    # Step 1: Load signal log
    signal_outcomes = _load_signal_log(data_path)
    if signal_outcomes is None:
        errors.append("No signal log data available")
        return RetrainResult(
            date=today,
            signal_weights_updated=False,
            drift_detected=False,
            drift_details=[],
            rebalance_actions=0,
            quality_score=0.0,
            errors=errors,
        )

    # Step 2: Compute signal weights
    weights_data: dict = {}
    try:
        from src.analysis.signal_monitor import compute_signal_weights

        weights = compute_signal_weights(signal_outcomes)
        weights_data = {
            w.signal_id: {
                "weight": w.weight,
                "p_value": w.p_value,
                "win_rate": w.win_rate,
                "n_trades": w.n_trades,
                "is_significant": w.is_significant,
                "is_decayed": w.is_decayed,
            }
            for w in weights
        }
        active = sum(1 for w in weights if w.weight > 0.0)
        total = len(weights)
        quality_score = active / total if total > 0 else 0.0
        weights_updated = True
        logger.info(
            "Signal weights computed: %d/%d active (quality=%.2f)",
            active, total, quality_score,
        )
    except Exception as exc:
        errors.append(f"Weight computation failed: {exc}")
        logger.error("Weight computation failed: %s", exc)

    # Step 3: Check for drift
    try:
        from src.analysis.drift_detector import detect_feature_drift

        # Build numeric feature windows from outcomes (win rate per signal)
        # Split each signal's outcomes into first/second half for comparison
        current_win: dict[str, list[float]] = {}
        historical_win: dict[str, list[float]] = {}
        for sig_id, outcomes in signal_outcomes.items():
            if len(outcomes) >= 10:
                mid = len(outcomes) // 2
                historical_win[sig_id] = [
                    float(o) for o in outcomes[:mid]
                ]
                current_win[sig_id] = [
                    float(o) for o in outcomes[mid:]
                ]

        if current_win and historical_win:
            report = detect_feature_drift(current_win, historical_win)
            drift_detected = report.any_drift
            drift_details = [r.description for r in report.results if r.is_drifted]
            logger.info(
                "Drift check: any=%s, critical=%d, warning=%d",
                report.any_drift, report.critical_drifts, report.warning_drifts,
            )
        else:
            logger.info("Insufficient data for drift detection")
    except Exception as exc:
        errors.append(f"Drift detection failed: {exc}")
        logger.error("Drift detection failed: %s", exc)

    # Step 4: Save weights
    if weights_data:
        weights_path = out_path / f"{today}_weights.json"
        if not _save_json(weights_path, weights_data):
            errors.append("Failed to save weights file")

    # Step 5: Rebalance placeholder
    rebalance_actions = 0
    logger.info("Rebalance recommendations: placeholder (0 actions)")

    # Step 6: Save full report
    report_data = {
        "date": today,
        "signal_weights_updated": weights_updated,
        "drift_detected": drift_detected,
        "drift_details": drift_details,
        "rebalance_actions": rebalance_actions,
        "quality_score": quality_score,
        "weights": weights_data,
        "errors": errors,
    }
    report_path = out_path / f"{today}_report.json"
    if not _save_json(report_path, report_data):
        errors.append("Failed to save report file")

    return RetrainResult(
        date=today,
        signal_weights_updated=weights_updated,
        drift_detected=drift_detected,
        drift_details=drift_details,
        rebalance_actions=rebalance_actions,
        quality_score=quality_score,
        errors=errors,
    )
