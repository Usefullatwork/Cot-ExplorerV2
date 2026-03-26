"""Health and metrics endpoints."""

from __future__ import annotations

import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field
from sqlalchemy import func, select, text

from src.db.engine import get_engine, get_session
from src.db.models import AuditLog, CotPosition, PriceDaily, Signal

router = APIRouter(tags=["health"])

_VERSION = "2.0.0"
_START_TIME = time.monotonic()
_START_UTC = datetime.now(timezone.utc)


# ── Response models ──────────────────────────────────────────────────────────


class HealthResponse(BaseModel):
    """Response for the health check endpoint."""

    status: str = Field(..., description="Service status", examples=["ok"])
    version: str = Field(..., description="API version string", examples=["2.0.0"])
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


class DetailedHealthResponse(BaseModel):
    """Response for the detailed health check endpoint."""

    status: str = Field(..., description="Service status")
    version: str = Field(..., description="API version string")
    timestamp: str = Field(..., description="Current server UTC timestamp")

    # Uptime
    uptime_seconds: float = Field(..., description="Seconds since the API process started", examples=[3661.4])
    started_at: str = Field(
        ...,
        description="UTC timestamp when the process started",
        examples=["2026-03-26T06:00:00+00:00"],
    )

    # Database
    db_size_mb: Optional[float] = Field(None, description="SQLite database file size in MB", examples=[12.4])
    db_tables: Optional[int] = Field(None, description="Number of tables in the database", examples=[10])

    # Pipeline
    last_pipeline_run: Optional[str] = Field(
        None,
        description="ISO timestamp of the last pipeline_start audit event",
    )
    last_signal_generated: Optional[str] = Field(
        None,
        description="ISO timestamp of the most recent signal",
    )
    total_signals: int = Field(0, description="Total signal count")
    total_prices: int = Field(0, description="Total daily price bar count")
    total_cot: int = Field(0, description="Total COT position count")

    # Memory
    memory_rss_mb: Optional[float] = Field(None, description="Resident set size (RSS) of the process in MB")


class MetricsResponse(BaseModel):
    """Response for the metrics endpoint."""

    signals: int = Field(0, description="Total number of trading signals in the database", examples=[142])
    prices_daily: int = Field(0, description="Total number of daily price bars stored", examples=[5840])
    cot_positions: int = Field(0, description="Total number of COT position records", examples=[1200])


# ── Helpers ──────────────────────────────────────────────────────────────────


def _get_memory_rss_mb() -> Optional[float]:
    """Return current process RSS in MB, or None if unavailable."""
    try:
        # Try psutil first (most reliable cross-platform)
        import psutil  # noqa: F811

        proc = psutil.Process(os.getpid())
        return round(proc.memory_info().rss / (1024 * 1024), 2)
    except ImportError:
        pass
    try:
        # Linux fallback: read /proc/self/status
        status = Path("/proc/self/status").read_text()
        for line in status.splitlines():
            if line.startswith("VmRSS:"):
                kb = int(line.split()[1])
                return round(kb / 1024, 2)
    except (FileNotFoundError, ValueError, IndexError):
        pass
    return None


def _get_db_size_mb() -> Optional[float]:
    """Return the SQLite file size in MB, or None if unavailable."""
    try:
        engine = get_engine()
        url = str(engine.url)
        if url.startswith("sqlite"):
            # Extract path from sqlite:///path or sqlite:////abs/path
            db_path = url.replace("sqlite:///", "")
            p = Path(db_path)
            if p.exists():
                return round(p.stat().st_size / (1024 * 1024), 2)
    except Exception:
        pass
    return None


# ── Endpoints ────────────────────────────────────────────────────────────────


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Health check",
    description="Returns service status, API version, and the timestamp of the most recent signal run.",
)
def health() -> HealthResponse:
    """Basic health check -- status, version, last_run timestamp.

    Designed to be fast: single lightweight DB query.
    """
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
    "/health/detailed",
    response_model=DetailedHealthResponse,
    summary="Detailed health check",
    description=(
        "Returns comprehensive system diagnostics: uptime, DB size, "
        "row counts, last pipeline run, and process memory usage."
    ),
)
def health_detailed() -> DetailedHealthResponse:
    """Detailed health check with system metrics."""
    now = datetime.now(timezone.utc)
    uptime = time.monotonic() - _START_TIME

    # Database metrics — gathered in one session
    last_signal: Optional[str] = None
    last_pipeline: Optional[str] = None
    total_signals = 0
    total_prices = 0
    total_cot = 0
    db_tables: Optional[int] = None

    try:
        factory = get_session()
        session = factory()

        # Last signal
        sig_ts = session.execute(
            select(Signal.generated_at).order_by(Signal.generated_at.desc()).limit(1)
        ).scalar_one_or_none()
        if sig_ts:
            last_signal = sig_ts.isoformat()

        # Last pipeline run (from audit log)
        pipeline_ts = session.execute(
            select(AuditLog.timestamp)
            .where(AuditLog.event_type == "pipeline_start")
            .order_by(AuditLog.timestamp.desc())
            .limit(1)
        ).scalar_one_or_none()
        if pipeline_ts:
            last_pipeline = pipeline_ts.isoformat()

        # Row counts
        total_signals = session.execute(select(func.count(Signal.id))).scalar_one()
        total_prices = session.execute(select(func.count(PriceDaily.id))).scalar_one()
        total_cot = session.execute(select(func.count(CotPosition.id))).scalar_one()

        # Table count via SQLite pragma
        try:
            rows = session.execute(text("SELECT count(*) FROM sqlite_master WHERE type='table'")).scalar_one()
            db_tables = rows
        except Exception:
            pass

        session.close()
    except Exception:
        pass

    return DetailedHealthResponse(
        status="ok",
        version=_VERSION,
        timestamp=now.isoformat(),
        uptime_seconds=round(uptime, 1),
        started_at=_START_UTC.isoformat(),
        db_size_mb=_get_db_size_mb(),
        db_tables=db_tables,
        last_pipeline_run=last_pipeline,
        last_signal_generated=last_signal,
        total_signals=total_signals,
        total_prices=total_prices,
        total_cot=total_cot,
        memory_rss_mb=_get_memory_rss_mb(),
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
