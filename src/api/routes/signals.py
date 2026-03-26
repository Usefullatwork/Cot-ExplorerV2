"""Signal listing and detail routes."""

from __future__ import annotations

import json
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from src.db import repository as repo
from src.security.input_validator import sanitize_string, validate_symbol

router = APIRouter(prefix="/api/v1", tags=["signals"])


@router.get("/signals")
def list_signals(
    grade: Optional[str] = Query(None, description="Filter by grade (A+, A, B, C)"),
    timeframe: Optional[str] = Query(None, description="Filter by timeframe bias"),
    min_score: Optional[int] = Query(None, ge=0, le=12, description="Minimum score"),
    direction: Optional[str] = Query(None, description="bull or bear"),
    active_only: bool = Query(False, description="Only signals at level now"),
    instrument: Optional[str] = Query(None, description="Filter by instrument key"),
    limit: int = Query(100, ge=1, le=500),
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


@router.get("/signals/{key}")
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
