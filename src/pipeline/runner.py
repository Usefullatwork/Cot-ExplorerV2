"""Pipeline orchestrator — runs all stages in order.

Stages:
  1. calendar      — fetch economic calendar
  2. cot           — fetch CFTC COT data
  3. combine       — merge COT reports into combined file
  4. fundamentals  — fetch FRED macro indicators
  5. prices+analysis — fetch prices and run technical analysis
  6. scoring       — run 12-point confluence scoring
  7. output        — generate static JSON
  8. push          — send signals to Telegram / Discord
"""

from __future__ import annotations

import logging
import sys
import time
from typing import Callable

from src.security.audit_log import log_event

logger = logging.getLogger(__name__)


def _stage_calendar() -> None:
    """Fetch economic calendar from ForexFactory."""
    import subprocess
    subprocess.run([sys.executable, "fetch_calendar.py"], check=False)


def _stage_cot() -> None:
    """Fetch CFTC COT reports."""
    import subprocess
    subprocess.run([sys.executable, "fetch_cot.py"], check=False)


def _stage_combine() -> None:
    """Combine COT reports — already handled by fetch_cot.py."""
    pass


def _stage_fundamentals() -> None:
    """Fetch FRED fundamental macro data."""
    import subprocess
    subprocess.run([sys.executable, "fetch_fundamentals.py"], check=False)


def _stage_prices() -> None:
    """Fetch prices and run technical analysis."""
    import subprocess
    subprocess.run([sys.executable, "fetch_prices.py"], check=False)


def _stage_scoring() -> None:
    """Run 12-point confluence scoring.

    This stage is currently handled inline by fetch_all.py.
    When the scoring module is extracted, this will call it directly.
    """
    import subprocess
    subprocess.run([sys.executable, "fetch_all.py"], check=False)


def _stage_output() -> None:
    """Generate static JSON for the frontend."""
    from src.publishers.json_file import publish_static_json

    import json
    from pathlib import Path

    macro_path = Path("data/macro/latest.json")
    if macro_path.exists():
        with open(macro_path) as f:
            data = json.load(f)
        publish_static_json(data)
    else:
        logger.warning("No macro data found — skipping static JSON output")


def _stage_push() -> None:
    """Send signals to configured push targets."""
    import subprocess
    subprocess.run([sys.executable, "push_signals.py"], check=False)


# Ordered list of pipeline stages
_STAGES: list[tuple[str, Callable[[], None]]] = [
    ("calendar", _stage_calendar),
    ("cot", _stage_cot),
    ("combine", _stage_combine),
    ("fundamentals", _stage_fundamentals),
    ("prices", _stage_prices),
    ("scoring", _stage_scoring),
    ("output", _stage_output),
    ("push", _stage_push),
]


def run_full_pipeline() -> dict[str, str]:
    """Execute all pipeline stages in order.

    Each stage runs independently — a failure in one stage is logged but
    does not prevent subsequent stages from running.

    Returns
    -------
    dict[str, str]
        Mapping of stage name to outcome (``"ok"`` or ``"error: ..."``)
    """
    log_event("pipeline_start", {"stages": [s[0] for s in _STAGES]})
    results: dict[str, str] = {}

    for name, fn in _STAGES:
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
