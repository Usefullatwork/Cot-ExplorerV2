#!/usr/bin/env python3
"""Run WFO backtests for all default instruments with 5-year data.

Usage:
    python scripts/run_wfo.py
    python scripts/run_wfo.py --instrument EURUSD
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.db.engine import init_db, session_ctx
from src.trading.backtesting.runner_service import WfoRunnerService, DEFAULT_INSTRUMENTS

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run WFO backtests")
    parser.add_argument("--instrument", type=str, help="Single instrument to run")
    parser.add_argument("--train", type=int, default=6, help="Train window months")
    parser.add_argument("--test", type=int, default=2, help="Test window months")
    parser.add_argument("--min-trades", type=int, default=3, help="Min trades per window")
    args = parser.parse_args()

    init_db()

    instruments = [args.instrument] if args.instrument else DEFAULT_INSTRUMENTS

    with session_ctx() as session:
        svc = WfoRunnerService(session)

        for inst in instruments:
            log.info("=== Running WFO for %s (train=%dm, test=%dm) ===", inst, args.train, args.test)
            try:
                run = svc.run_wfo(
                    instrument=inst,
                    train_months=args.train,
                    test_months=args.test,
                    min_trades=args.min_trades,
                )
                log.info(
                    "  %s: status=%s windows=%d PBO=%.3f best=%s/%s",
                    inst, run.status, run.total_windows,
                    run.pbo_score or 0, run.best_strategy, run.best_timeframe,
                )
            except Exception as exc:
                log.error("  %s: FAILED — %s", inst, exc)

    log.info("Done.")


if __name__ == "__main__":
    main()
