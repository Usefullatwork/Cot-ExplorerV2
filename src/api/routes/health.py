"""Health and metrics endpoints."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter
from sqlalchemy import func, select

from src.db.engine import get_engine, get_session
from src.db.models import CotPosition, PriceDaily, Signal

router = APIRouter(tags=["health"])

_VERSION = "2.0.0"


@router.get("/health")
def health() -> dict:
    """Basic health check — status, version, last_run timestamp."""
    last_run = None
    try:
        factory = get_session()
        session = factory()
        row = session.execute(
            select(Signal.generated_at).order_by(Signal.generated_at.desc()).limit(1)
        ).scalar_one_or_none()
        if row:
            last_run = row.isoformat()
        session.close()
    except Exception:
        pass

    return {
        "status": "ok",
        "version": _VERSION,
        "last_run": last_run,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/metrics")
def metrics() -> dict:
    """Basic counts: signals, prices, COT records."""
    counts: dict[str, int] = {"signals": 0, "prices_daily": 0, "cot_positions": 0}
    try:
        factory = get_session()
        session = factory()
        counts["signals"] = session.execute(select(func.count(Signal.id))).scalar_one()
        counts["prices_daily"] = session.execute(select(func.count(PriceDaily.id))).scalar_one()
        counts["cot_positions"] = session.execute(select(func.count(CotPosition.id))).scalar_one()
        session.close()
    except Exception:
        pass
    return counts
