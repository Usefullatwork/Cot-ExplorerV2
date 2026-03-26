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

import json
import logging
import time
from pathlib import Path
from typing import Callable

from src.security.audit_log import log_event

logger = logging.getLogger(__name__)


def _stage_calendar() -> None:
    """Fetch economic calendar from ForexFactory."""
    from src.trading.core.fetch_calendar import main as calendar_main

    calendar_main()


def _stage_cot() -> None:
    """Fetch CFTC COT reports (includes combine step)."""
    from src.trading.core.fetch_cot import main as cot_main

    cot_main()


def _stage_combine() -> None:
    """Combine COT reports — already handled by fetch_cot.main()."""
    logger.debug("Combine stage is a no-op; handled within cot stage")


def _stage_fundamentals() -> None:
    """Fetch FRED fundamental macro data."""
    from src.trading.core.fetch_fundamentals import main as fundamentals_main

    fundamentals_main()


def _stage_prices() -> None:
    """Fetch prices and run technical analysis."""
    from src.trading.core.fetch_prices import main as prices_main

    prices_main()


def _stage_scoring() -> None:
    """Run 12-point confluence scoring.

    TODO: Extract scoring loop from fetch_all.py into
    src.analysis.scoring so this stage can call it directly.
    Currently delegates to the monolithic fetch_all.py main block
    via the src/trading/core copy which exposes a main() function.
    The pure scoring function already lives in src.analysis.scoring
    (calculate_confluence), but the full orchestration that feeds it
    instrument data still lives in fetch_all.py.
    """
    logger.info("Scoring stage: full pipeline handled by prices + fundamentals stages")


def _stage_output() -> None:
    """Generate static JSON for the frontend."""
    from src.publishers.json_file import publish_static_json

    macro_path = Path("data/macro/latest.json")
    if macro_path.exists():
        with open(macro_path) as f:
            data = json.load(f)
        publish_static_json(data)
    else:
        logger.warning("No macro data found — skipping static JSON output")


def _stage_push() -> None:
    """Send signals to configured push targets."""
    from src.trading.core.push_signals import main as push_main

    push_main()


# Ordered list of pipeline stage names — functions are resolved at runtime
# via ``_get_stage_fn`` so that ``unittest.mock.patch`` works correctly.
_STAGE_NAMES: list[str] = [
    "calendar",
    "cot",
    "combine",
    "fundamentals",
    "prices",
    "scoring",
    "output",
    "push",
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
