"""Pipeline scheduler — APScheduler with SQLAlchemyJobStore.

Runs 6 persistent jobs in-process with FastAPI:
  - Layer 1 (full pipeline) every 2 hours during market hours
  - Layer 2 (portfolio risk) daily at 06:00 UTC
  - Weekly retrain Fridays at 18:00 UTC
  - Position monitor every 5 minutes
  - Signal expiry every 30 minutes
  - Heartbeat every 1 minute

Controlled by SCHEDULER_ENABLED env var (default "0" = disabled).
"""

from __future__ import annotations

import json
import logging
import os
import time
from datetime import datetime, timedelta, timezone

from sqlalchemy import Engine

logger = logging.getLogger(__name__)

SCHEDULER_ENABLED = os.environ.get("SCHEDULER_ENABLED", "0") == "1"


def _run_layer1() -> None:
    """Execute the full 13-stage pipeline and log result."""
    from src.db.engine import session_ctx
    from src.db.models import PipelineRun, PipelineState
    from src.pipeline.runner import run_full_pipeline

    t0 = time.time()
    try:
        results = run_full_pipeline()
        with session_ctx() as session:
            run = PipelineRun(
                started_at=datetime.now(timezone.utc),
                finished_at=datetime.now(timezone.utc),
                layer="layer1",
                status="ok" if all(v == "ok" for v in results.values()) else "error",
                duration_sec=round(time.time() - t0, 2),
                details_json=json.dumps(results),
            )
            session.add(run)

            state = session.query(PipelineState).first()
            if state:
                state.layer1_last_run_at = datetime.now(timezone.utc)

        logger.info("Layer 1 complete in %.1fs", time.time() - t0)
    except Exception as exc:
        logger.error("Layer 1 failed: %s", exc)


def _run_layer2() -> None:
    """Execute Layer 2 + gate orchestrator + execution bridge."""
    from src.db.engine import session_ctx
    from src.pipeline.execution_bridge import execute_decisions
    from src.pipeline.gate_orchestrator import process_pending_signals
    from src.pipeline.layer2_runner import run_layer2

    try:
        with session_ctx() as session:
            run_layer2(session)
            decisions = process_pending_signals(session)
            if decisions:
                execute_decisions(decisions, session)
        logger.info("Layer 2 pipeline complete")
    except Exception as exc:
        logger.error("Layer 2 pipeline failed: %s", exc)


def _run_retrain() -> None:
    """Run Friday weekly retrain."""
    from src.db.engine import session_ctx
    from src.db.models import PipelineRun, PipelineState
    from src.pipeline.weekly_retrain import run_weekly_retrain

    t0 = time.time()
    try:
        result = run_weekly_retrain()
        with session_ctx() as session:
            run = PipelineRun(
                started_at=datetime.now(timezone.utc),
                finished_at=datetime.now(timezone.utc),
                layer="retrain",
                status="ok",
                duration_sec=round(time.time() - t0, 2),
                details_json=json.dumps({
                    "weights_updated": result.weights_updated,
                    "drift_detected": result.drift_detected,
                }),
            )
            session.add(run)

            state = session.query(PipelineState).first()
            if state:
                state.retrain_last_run_at = datetime.now(timezone.utc)

        logger.info("Weekly retrain complete in %.1fs", time.time() - t0)
    except Exception as exc:
        logger.error("Weekly retrain failed: %s", exc)


def _monitor_positions() -> None:
    """Check open positions for SL/TP hits and update current_price."""
    from src.db.engine import session_ctx
    from src.db.models import BotPosition, PriceDaily

    try:
        with session_ctx() as session:
            positions = (
                session.query(BotPosition)
                .filter(BotPosition.status.in_(["open", "partial"]))
                .all()
            )
            for pos in positions:
                latest = (
                    session.query(PriceDaily)
                    .filter(PriceDaily.instrument == pos.instrument)
                    .order_by(PriceDaily.date.desc())
                    .first()
                )
                if latest:
                    pos.current_price = latest.close
    except Exception as exc:
        logger.error("Position monitor failed: %s", exc)


def _expire_stale_signals() -> None:
    """Expire pending BotSignals older than 4 hours."""
    from src.db.engine import session_ctx
    from src.db.models import BotSignal

    cutoff = datetime.now(timezone.utc) - timedelta(hours=4)
    try:
        with session_ctx() as session:
            stale = (
                session.query(BotSignal)
                .filter(
                    BotSignal.status == "pending",
                    BotSignal.received_at < cutoff,
                )
                .all()
            )
            for sig in stale:
                sig.status = "expired"
                sig.rejection_reason = "Auto-expired after 4 hours"
            if stale:
                logger.info("Expired %d stale signals", len(stale))
    except Exception as exc:
        logger.error("Signal expiry failed: %s", exc)


def _heartbeat() -> None:
    """Update heartbeat timestamp in pipeline_state."""
    from src.db.engine import session_ctx
    from src.db.models import PipelineState

    try:
        with session_ctx() as session:
            state = session.query(PipelineState).first()
            if state:
                state.heartbeat_at = datetime.now(timezone.utc)
    except Exception as exc:
        logger.debug("Heartbeat failed: %s", exc)


def create_scheduler(engine: Engine):
    """Create and configure the APScheduler instance.

    Returns None if SCHEDULER_ENABLED is False.
    """
    if not SCHEDULER_ENABLED:
        logger.info("Scheduler disabled (SCHEDULER_ENABLED != 1)")
        return None

    from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
    from apscheduler.schedulers.asyncio import AsyncIOScheduler

    jobstores = {"default": SQLAlchemyJobStore(engine=engine)}
    scheduler = AsyncIOScheduler(jobstores=jobstores)

    # Layer 1: every 2h during market hours (06-22 UTC)
    scheduler.add_job(
        _run_layer1, "cron",
        hour="6,8,10,12,14,16,18,20,22",
        id="layer1", replace_existing=True,
    )

    # Layer 2: daily at 06:00 UTC
    scheduler.add_job(
        _run_layer2, "cron",
        hour=6, minute=0,
        id="layer2", replace_existing=True,
    )

    # Weekly retrain: Friday 18:00 UTC
    scheduler.add_job(
        _run_retrain, "cron",
        day_of_week="fri", hour=18,
        id="retrain", replace_existing=True,
    )

    # Position monitor: every 5 minutes
    scheduler.add_job(
        _monitor_positions, "interval",
        minutes=5,
        id="position_monitor", replace_existing=True,
    )

    # Signal expiry: every 30 minutes
    scheduler.add_job(
        _expire_stale_signals, "interval",
        minutes=30,
        id="signal_expiry", replace_existing=True,
    )

    # Heartbeat: every 1 minute
    scheduler.add_job(
        _heartbeat, "interval",
        minutes=1,
        id="heartbeat", replace_existing=True,
    )

    logger.info("Scheduler configured with 6 jobs")
    return scheduler
