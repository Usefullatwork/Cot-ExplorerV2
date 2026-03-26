"""Signal listing and detail routes."""

from __future__ import annotations

import json
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from src.db import repository as repo
from src.security.input_validator import sanitize_string, validate_symbol

router = APIRouter(prefix="/api/v1", tags=["signals"])


# ── Response models ──────────────────────────────────────────────────────────


class SignalResponse(BaseModel):
    """A single trading signal with trade levels and scoring details."""

    id: int = Field(..., description="Unique signal ID")
    instrument: str = Field(..., description="Instrument key", examples=["EURUSD"])
    generated_at: Optional[str] = Field(None, description="ISO timestamp of signal generation")
    direction: str = Field(..., description="Trade direction", examples=["bull"])
    grade: str = Field(..., description="Confluence grade", examples=["A+"])
    score: int = Field(..., description="Confluence score (0-12)", examples=[10])
    timeframe_bias: str = Field(..., description="Timeframe classification", examples=["SWING"])
    entry_price: Optional[float] = Field(None, description="Suggested entry price")
    stop_loss: Optional[float] = Field(None, description="Stop loss price")
    target_1: Optional[float] = Field(None, description="First take-profit target")
    target_2: Optional[float] = Field(None, description="Second take-profit target")
    rr_t1: Optional[float] = Field(None, description="Risk-reward ratio to T1")
    rr_t2: Optional[float] = Field(None, description="Risk-reward ratio to T2")
    entry_weight: Optional[int] = Field(None, description="Entry level weight")
    t1_weight: Optional[int] = Field(None, description="T1 level weight")
    sl_type: Optional[str] = Field(None, description="Stop loss type", examples=["structure"])
    at_level_now: Optional[bool] = Field(None, description="Whether price is currently at entry level")
    vix_regime: Optional[str] = Field(None, description="VIX volatility regime", examples=["normal"])
    pos_size: Optional[str] = Field(None, description="Position size recommendation", examples=["full"])
    score_details: Optional[Any] = Field(None, description="Breakdown of individual scoring criteria")
    metadata: Optional[Any] = Field(None, description="Additional signal metadata")


# ── Endpoints ────────────────────────────────────────────────────────────────


@router.get(
    "/signals",
    response_model=list[SignalResponse],
    summary="List trading signals",
    description="Returns trading signals with optional filters for grade, direction, timeframe, score, and instrument.",
)
def list_signals(
    grade: Optional[str] = Query(None, description="Filter by grade (A+, A, B, C)"),
    timeframe: Optional[str] = Query(None, description="Filter by timeframe bias"),
    min_score: Optional[int] = Query(None, ge=0, le=12, description="Minimum confluence score (0-12)"),
    direction: Optional[str] = Query(None, description="Trade direction: bull or bear"),
    active_only: bool = Query(False, description="Only return signals where price is at entry level now"),
    instrument: Optional[str] = Query(None, description="Filter by instrument key (e.g. EURUSD)"),
    limit: int = Query(100, ge=1, le=500, description="Maximum number of signals to return"),
) -> list[dict]:
    """List signals with optional filters."""
    try:
        if instrument:
            instrument = validate_symbol(instrument)
        if grade:
            grade = sanitize_string(grade, max_length=5)
        if timeframe:
            timeframe = sanitize_string(timeframe, max_length=20)
        if direction:
            direction = sanitize_string(direction, max_length=10)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    grades = [grade] if grade else None
    signals = repo.get_signals(
        instrument=instrument,
        min_score=min_score,
        grades=grades,
        limit=limit,
    )
    results = []
    for sig in signals:
        row = _signal_to_dict(sig)
        # Apply filters not handled by the DB query
        if direction and row.get("direction") != direction:
            continue
        if timeframe and row.get("timeframe_bias") != timeframe:
            continue
        if active_only and not row.get("at_level_now"):
            continue
        results.append(row)
    return results


@router.get(
    "/signals/{key}",
    response_model=SignalResponse,
    summary="Signal detail by instrument",
    description="Returns the latest trading signal for a given instrument key.",
)
def signal_detail(key: str) -> dict:
    """Full signal detail by instrument key (returns latest signal for that key)."""
    try:
        key = validate_symbol(key)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    signals = repo.get_signals(instrument=key, limit=1)
    if not signals:
        raise HTTPException(status_code=404, detail=f"No signals found for {key}")
    return _signal_to_dict(signals[0])


def _signal_to_dict(sig: object) -> dict:
    """Convert a Signal ORM object to a JSON-friendly dict."""
    return {
        "id": sig.id,  # type: ignore[attr-defined]
        "instrument": sig.instrument,  # type: ignore[attr-defined]
        "generated_at": sig.generated_at.isoformat() if sig.generated_at else None,  # type: ignore[attr-defined]
        "direction": sig.direction,  # type: ignore[attr-defined]
        "grade": sig.grade,  # type: ignore[attr-defined]
        "score": sig.score,  # type: ignore[attr-defined]
        "timeframe_bias": sig.timeframe_bias,  # type: ignore[attr-defined]
        "entry_price": sig.entry_price,  # type: ignore[attr-defined]
        "stop_loss": sig.stop_loss,  # type: ignore[attr-defined]
        "target_1": sig.target_1,  # type: ignore[attr-defined]
        "target_2": sig.target_2,  # type: ignore[attr-defined]
        "rr_t1": sig.rr_t1,  # type: ignore[attr-defined]
        "rr_t2": sig.rr_t2,  # type: ignore[attr-defined]
        "entry_weight": sig.entry_weight,  # type: ignore[attr-defined]
        "t1_weight": sig.t1_weight,  # type: ignore[attr-defined]
        "sl_type": sig.sl_type,  # type: ignore[attr-defined]
        "at_level_now": sig.at_level_now,  # type: ignore[attr-defined]
        "vix_regime": sig.vix_regime,  # type: ignore[attr-defined]
        "pos_size": sig.pos_size,  # type: ignore[attr-defined]
        "score_details": json.loads(sig.score_details) if sig.score_details else None,  # type: ignore[attr-defined]
        "metadata": json.loads(sig.metadata_) if sig.metadata_ else None,  # type: ignore[attr-defined]
    }
