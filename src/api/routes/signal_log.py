"""Signal performance log API routes."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select

from src.db.engine import session_scope
from src.db.models import SignalPerformance

router = APIRouter(prefix="/api/v1/signal-log", tags=["signal-log"])


# ── Response models ──────────────────────────────────────────────────────────

class SignalPerfResponse(BaseModel):
    id: int; signal_id: int; instrument: str; direction: str; grade: str; score: int
    entry_price: float; result: str; closed_at: Optional[str] = None
    pnl_pips: Optional[float] = None; created_at: Optional[str] = None

class SignalPerfStatsResponse(BaseModel):
    total: int; hits: int; misses: int; pending: int; neutral: int
    hit_rate: Optional[float] = None; avg_pnl_pips: Optional[float] = None

class SignalLogListResponse(BaseModel):
    stats: SignalPerfStatsResponse; history: list[SignalPerfResponse]

class ResultUpdateRequest(BaseModel):
    result: str = Field(..., description="HIT, MISS, or NEUTRAL")
    pnl_pips: Optional[float] = Field(None, description="Profit/loss in pips")


def _perf_to_dict(r: Any) -> dict:
    return {"id": r.id, "signal_id": r.signal_id, "instrument": r.instrument,
            "direction": r.direction, "grade": r.grade, "score": r.score,
            "entry_price": r.entry_price, "result": r.result,
            "closed_at": r.closed_at.isoformat() if r.closed_at else None,
            "pnl_pips": r.pnl_pips,
            "created_at": r.created_at.isoformat() if r.created_at else None}


# ── Endpoints ────────────────────────────────────────────────────────────────

@router.get("", response_model=SignalLogListResponse, summary="Signal performance history")
def list_signal_log(
    instrument: Optional[str] = Query(None, description="Filter by instrument"),
    result: Optional[str] = Query(None, description="Filter: HIT, MISS, PENDING, NEUTRAL"),
    limit: int = Query(100, ge=1, le=500, description="Max records"),
) -> dict:
    """Return signal performance history with stats."""
    gen = session_scope()
    session = next(gen)
    try:
        total = session.execute(select(func.count(SignalPerformance.id))).scalar() or 0
        hits = session.execute(select(func.count(SignalPerformance.id)).where(
            SignalPerformance.result == "HIT")).scalar() or 0
        misses = session.execute(select(func.count(SignalPerformance.id)).where(
            SignalPerformance.result == "MISS")).scalar() or 0
        pending = session.execute(select(func.count(SignalPerformance.id)).where(
            SignalPerformance.result == "PENDING")).scalar() or 0
        neutral = session.execute(select(func.count(SignalPerformance.id)).where(
            SignalPerformance.result == "NEUTRAL")).scalar() or 0
        avg_pnl = session.execute(select(func.avg(SignalPerformance.pnl_pips)).where(
            SignalPerformance.pnl_pips.isnot(None))).scalar()

        closed = hits + misses
        stats: dict[str, Any] = {
            "total": total, "hits": hits, "misses": misses, "pending": pending, "neutral": neutral,
            "hit_rate": round(hits / closed * 100, 1) if closed > 0 else None,
            "avg_pnl_pips": round(float(avg_pnl), 2) if avg_pnl is not None else None,
        }

        stmt = select(SignalPerformance).order_by(SignalPerformance.created_at.desc())
        if instrument:
            stmt = stmt.where(SignalPerformance.instrument == instrument)
        if result:
            stmt = stmt.where(SignalPerformance.result == result.upper())
        rows = session.execute(stmt.limit(limit)).scalars().all()

        response = {"stats": stats, "history": [_perf_to_dict(r) for r in rows]}
        try:
            gen.send(None)
        except StopIteration:
            pass
        return response
    except Exception:
        try:
            gen.throw(Exception)
        except StopIteration:
            pass
        raise


@router.post("/{signal_id}/result", response_model=SignalPerfResponse, summary="Update signal result")
def update_signal_result(signal_id: int, body: ResultUpdateRequest) -> dict:
    """Mark a signal as HIT, MISS, or NEUTRAL with optional PnL."""
    if body.result.upper() not in ("HIT", "MISS", "NEUTRAL"):
        raise HTTPException(status_code=400, detail="Result must be HIT, MISS, or NEUTRAL")

    gen = session_scope()
    session = next(gen)
    try:
        row = session.execute(
            select(SignalPerformance).where(SignalPerformance.signal_id == signal_id)
        ).scalar()
        if not row:
            try:
                gen.throw(Exception)
            except StopIteration:
                pass
            raise HTTPException(status_code=404, detail=f"No performance record for signal {signal_id}")

        row.result = body.result.upper()
        row.pnl_pips = body.pnl_pips
        row.closed_at = datetime.now(timezone.utc)
        result = _perf_to_dict(row)
        try:
            gen.send(None)
        except StopIteration:
            pass
        return result
    except HTTPException:
        raise
    except Exception:
        try:
            gen.throw(Exception)
        except StopIteration:
            pass
        raise
