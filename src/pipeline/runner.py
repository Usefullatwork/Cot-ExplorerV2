"""Pipeline orchestrator — runs all stages in order.

Stages:
  0. quality       — validate incoming data quality
  1. calendar      — fetch economic calendar
  2. cot           — fetch CFTC COT data
  3. combine       — merge COT reports into combined file
  4. fundamentals  — fetch FRED macro indicators
  5. prices+analysis — fetch prices and run technical analysis
  6. scoring       — run 12-point confluence scoring
  7. output        — generate static JSON
  8. push          — send signals to Telegram / Discord
  9. rebalance     — weekly retrain placeholder (Fridays only)
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Callable

from src.security.audit_log import log_event

logger = logging.getLogger(__name__)


def _stage_quality() -> None:
    """Validate incoming data quality before pipeline runs.

    Reads combined COT and macro price files (if they exist), runs
    validation, logs quality scores, and writes a report to
    ``data/quality_report.json``.  Never blocks the pipeline.
    """
    from src.data.quality import (
        QualityReport,
        compute_aggregate_quality,
        validate_cot_data,
        validate_price_data,
    )

    reports: list[QualityReport] = []

    cot_path = Path("data/cot/combined/latest.json")
    if cot_path.exists():
        try:
            with open(cot_path, encoding="utf-8") as f:
                cot_records = json.load(f)
            if isinstance(cot_records, list):
                rpt = validate_cot_data(cot_records)
                reports.append(rpt)
                logger.info(
                    "COT quality: score=%.2f errors=%d warnings=%d (%d records)",
                    rpt.quality_score, rpt.error_count, rpt.warning_count,
                    rpt.total_records,
                )
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Could not read COT data for quality check: %s", exc)
    else:
        logger.info("Quality stage: no COT data file found — skipping COT validation")

    macro_path = Path("data/prices/macro_latest.json")
    if macro_path.exists():
        try:
            with open(macro_path, encoding="utf-8") as f:
                price_records = json.load(f)
            if isinstance(price_records, list):
                rpt = validate_price_data(price_records)
                reports.append(rpt)
                logger.info(
                    "Price quality: score=%.2f errors=%d warnings=%d (%d records)",
                    rpt.quality_score, rpt.error_count, rpt.warning_count,
                    rpt.total_records,
                )
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Could not read price data for quality check: %s", exc)
    else:
        logger.info("Quality stage: no price data file found — skipping price validation")

    if reports:
        agg = compute_aggregate_quality(reports)
        logger.info("Aggregate data quality: %.2f", agg)

        report_path = Path("data/quality_report.json")
        report_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "aggregate_quality": agg,
            "reports": [
                {
                    "source": r.source,
                    "total_records": r.total_records,
                    "error_count": r.error_count,
                    "warning_count": r.warning_count,
                    "quality_score": r.quality_score,
                    "issues": [
                        {
                            "severity": i.severity,
                            "field": i.field,
                            "message": i.message,
                            "record_date": i.record_date,
                        }
                        for i in r.issues
                    ],
                }
                for r in reports
            ],
        }
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
        logger.info("Quality report written to %s", report_path)
    else:
        logger.info("Quality stage: no data files to validate")


def _stage_calendar() -> None:
    """Fetch economic calendar from ForexFactory."""
    from src.trading.core.fetch_calendar import main as calendar_main

    calendar_main()


def _stage_cot() -> None:
    """Fetch CFTC COT reports (includes combine step)."""
    from src.trading.core.fetch_cot import main as cot_main

    cot_main()


def _stage_combine() -> None:
    """Combine COT reports into data/combined/latest.json."""
    from src.trading.core.build_combined import build_combined

    build_combined()


def _stage_fundamentals() -> None:
    """Fetch FRED fundamental macro data."""
    from src.trading.core.fetch_fundamentals import main as fundamentals_main

    fundamentals_main()


def _stage_prices() -> None:
    """Fetch prices and run technical analysis."""
    from src.trading.core.fetch_prices import main as prices_main

    prices_main()


def _stage_scoring() -> None:
    """Scoring is computed as part of the prices+analysis stage (fetch_all.main).

    This stage is a no-op.
    """
    logger.info("Scoring stage: full pipeline handled by prices + fundamentals stages")


def _stage_output() -> None:
    """Generate static JSON for the frontend."""
    from src.publishers.json_file import publish_static_json

    macro_path = Path("data/macro/latest.json")
    if macro_path.exists():
        with open(macro_path, encoding="utf-8") as f:
            data = json.load(f)
        publish_static_json(data)
    else:
        logger.warning("No macro data found — skipping static JSON output")


def _stage_push() -> None:
    """Send signals to configured push targets."""
    from src.trading.core.push_signals import main as push_main

    push_main()


def _stage_rebalance() -> None:
    """Weekly rebalance placeholder — only runs on Fridays."""
    from datetime import date

    if date.today().weekday() != 4:  # 4 = Friday
        logger.info("Rebalance stage: skipped (not Friday)")
        return
    logger.info("Rebalance stage: placeholder for weekly_retrain integration")


# Ordered list of pipeline stage names — functions are resolved at runtime
# via ``_get_stage_fn`` so that ``unittest.mock.patch`` works correctly.
_STAGE_NAMES: list[str] = [
    "quality",
    "calendar",
    "cot",
    "combine",
    "fundamentals",
    "prices",
    "scoring",
    "output",
    "push",
    "rebalance",
]

import sys as _sys  # noqa: E402 – needed for dynamic lookup


def _get_stage_fn(name: str) -> Callable[[], None]:
    """Resolve a stage function by name from this module at call time."""
    mod = _sys.modules[__name__]
    return getattr(mod, f"_stage_{name}")


def run_full_pipeline() -> dict[str, str]:
    """Execute all pipeline stages in order.

    Each stage runs independently — a failure in one stage is logged but
    does not prevent subsequent stages from running.

    Returns
    -------
    dict[str, str]
        Mapping of stage name to outcome (``"ok"`` or ``"error: ..."``)
    """
    log_event("pipeline_start", {"stages": _STAGE_NAMES})
    results: dict[str, str] = {}

    for name in _STAGE_NAMES:
        fn = _get_stage_fn(name)
        logger.info("Pipeline stage: %s", name)
        t0 = time.time()
        try:
            fn()
            elapsed = round(time.time() - t0, 1)
            results[name] = "ok"
            logger.info("  %s completed in %.1fs", name, elapsed)
        except Exception as exc:
            elapsed = round(time.time() - t0, 1)
            msg = f"error: {exc}"
            results[name] = msg
            logger.error("  %s failed in %.1fs: %s", name, elapsed, exc)
            log_event("pipeline_stage_error", {"stage": name, "error": str(exc)})

    log_event("pipeline_complete", {"results": results})
    return results


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    results = run_full_pipeline()
    logger.info("=== Pipeline Results ===")
    for stage, outcome in results.items():
        status = "OK" if outcome == "ok" else "FAIL"
        logger.info("[%s] %s: %s", status, stage, outcome)
