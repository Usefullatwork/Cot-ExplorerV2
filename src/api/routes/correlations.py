"""Correlation matrix API routes."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field
from sqlalchemy import select

from src.db.engine import session_scope
from src.db.models import CorrelationSnapshot

router = APIRouter(prefix="/api/v1/correlations", tags=["correlations"])


# ── Response models ──────────────────────────────────────────────────────────


class CorrelationResponse(BaseModel):
    """A single correlation pair."""

    instrument_a: str = Field(..., description="First instrument key")
    instrument_b: str = Field(..., description="Second instrument key")
    correlation: float = Field(..., description="Pearson correlation coefficient (-1 to 1)")
    window_days: int = Field(..., description="Rolling window in days")
    calculated_at: Optional[str] = Field(None, description="ISO timestamp of calculation")


# ── Endpoints ────────────────────────────────────────────────────────────────


@router.get(
    "",
    response_model=list[CorrelationResponse],
    summary="Latest correlation matrix",
    description="Returns the latest cross-instrument correlation snapshots.",
)
def get_correlations(
    window: Optional[int] = Query(None, ge=5, le=252, description="Filter by window size in days"),
    limit: int = Query(100, ge=1, le=500, description="Maximum pairs to return"),
) -> list[dict]:
    """Return latest correlation snapshots."""
    gen = session_scope()
    session = next(gen)
    try:
        stmt = select(CorrelationSnapshot).order_by(CorrelationSnapshot.calculated_at.desc())
        if window:
            stmt = stmt.where(CorrelationSnapshot.window_days == window)
        stmt = stmt.limit(limit)
        rows = session.execute(stmt).scalars().all()

        result = [
            {
                "instrument_a": r.instrument_a,
                "instrument_b": r.instrument_b,
                "correlation": r.correlation,
                "window_days": r.window_days,
                "calculated_at": r.calculated_at.isoformat() if r.calculated_at else None,
            }
            for r in rows
        ]

        try:
            gen.send(None)
        except StopIteration:
            pass
        return result
    except Exception:
        try:
            gen.throw(Exception)
        except StopIteration:
            pass
        raise
