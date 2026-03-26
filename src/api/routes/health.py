"""Health and metrics endpoints."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field
from sqlalchemy import func, select

from src.db.engine import get_engine, get_session
from src.db.models import CotPosition, PriceDaily, Signal

router = APIRouter(tags=["health"])

_VERSION = "2.0.0"


# ── Response models ──────────────────────────────────────────────────────────

class HealthResponse(BaseModel):
    """Response for the health check endpoint."""

    status: str = Field(
        ..., description="Service status", examples=["ok"]
    )
    version: str = Field(
        ..., description="API version string", examples=["2.0.0"]
    )
    last_run: Optional[str] = Field(
        None,
        description="ISO timestamp of the most recent signal generation",
        examples=["2026-03-25T14:30:00+00:00"],
    )
    timestamp: str = Field(
        ...,
        description="Current server UTC timestamp in ISO format",
        examples=["2026-03-26T08:00:00+00:00"],
    )


class MetricsResponse(BaseModel):
    """Response for the metrics endpoint."""

    signals: int = Field(
        0, description="Total number of trading signals in the database", examples=[142]
    )
    prices_daily: int = Field(
        0, description="Total number of daily price bars stored", examples=[5840]
    )
    cot_positions: int = Field(
        0, description="Total number of COT position records", examples=[1200]
    )


# ── Endpoints ────────────────────────────────────────────────────────────────

@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Health check",
    description="Returns service status, API version, and the timestamp of the most recent signal run.",
)
def health() -> HealthResponse:
    """Basic health check -- status, version, last_run timestamp."""
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

    return HealthResponse(
        status="ok",
        version=_VERSION,
        last_run=last_run,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


@router.get(
    "/metrics",
    response_model=MetricsResponse,
    summary="Database metrics",
    description="Returns row counts for core tables: signals, daily prices, and COT positions.",
)
def metrics() -> MetricsResponse:
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
    return MetricsResponse(**counts)
