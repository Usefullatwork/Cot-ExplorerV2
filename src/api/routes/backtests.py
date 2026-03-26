"""Backtest results API routes."""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.db.engine import session_scope
from src.db.models import BacktestResult
from src.security.input_validator import validate_symbol

router = APIRouter(prefix="/api/v1/backtests", tags=["backtests"])


# ── Response models ──────────────────────────────────────────────────────────

class BacktestSummaryResponse(BaseModel):
    """Aggregate backtest performance statistics."""

    total_trades: int = Field(..., description="Total number of backtested trades", examples=[50])
    wins: Optional[int] = Field(None, description="Number of winning trades (T1 or T2 hit)")
    losses: Optional[int] = Field(None, description="Number of losing trades (stopped out or expired)")
    win_rate: Optional[float] = Field(None, description="Win rate percentage", examples=[64.0])
    avg_pnl_rr: Optional[float] = Field(None, description="Average PnL in risk-reward multiples", examples=[1.35])
    avg_duration_hours: Optional[float] = Field(None, description="Average trade duration in hours", examples=[48.5])
    message: Optional[str] = Field(None, description="Status message when no data is available")


class BacktestTradeResponse(BaseModel):
    """A single backtest trade result."""

    id: int = Field(..., description="Unique trade ID")
    instrument: str = Field(..., description="Instrument key", examples=["EURUSD"])
    direction: str = Field(..., description="Trade direction", examples=["bull"])
    grade: str = Field(..., description="Signal grade at entry", examples=["A"])
    score: int = Field(..., description="Confluence score at entry", examples=[9])
    entry_date: Any = Field(..., description="Entry datetime")
    entry_price: float = Field(..., description="Entry price", examples=[1.0850])
    exit_date: Optional[Any] = Field(None, description="Exit datetime")
    exit_price: Optional[float] = Field(None, description="Exit price")
    exit_reason: Optional[str] = Field(None, description="Exit reason: t1_hit, t2_hit, stopped_out, or expired")
    pnl_pips: Optional[float] = Field(None, description="Profit/loss in pips")
    pnl_rr: Optional[float] = Field(None, description="Profit/loss in risk-reward multiples")
    duration_hours: Optional[float] = Field(None, description="Trade duration in hours")


# ── Endpoints ────────────────────────────────────────────────────────────────

@router.get(
    "/summary",
    response_model=BacktestSummaryResponse,
    summary="Backtest summary",
    description="Returns aggregate backtest statistics including win rate, average PnL, and average duration.",
)
def backtest_summary() -> dict:
    """Aggregate backtest statistics."""
    gen = session_scope()
    session = next(gen)
    try:
        total = session.execute(select(func.count(BacktestResult.id))).scalar() or 0

        if total == 0:
            result = {"total_trades": 0, "message": "No backtest data yet"}
            try:
                gen.send(None)
            except StopIteration:
                pass
            return result

        wins = (
            session.execute(
                select(func.count(BacktestResult.id)).where(
                    BacktestResult.exit_reason.in_(["t1_hit", "t2_hit"])
                )
            ).scalar()
            or 0
        )
        avg_pnl_rr = (
            session.execute(select(func.avg(BacktestResult.pnl_rr))).scalar() or 0.0
        )
        avg_duration = (
            session.execute(select(func.avg(BacktestResult.duration_hours))).scalar()
            or 0.0
        )

        result = {
            "total_trades": total,
            "wins": wins,
            "losses": total - wins,
            "win_rate": round(wins / total * 100, 1) if total else 0,
            "avg_pnl_rr": round(float(avg_pnl_rr), 2),
            "avg_duration_hours": round(float(avg_duration), 1),
        }

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


@router.get(
    "/trades",
    response_model=list[BacktestTradeResponse],
    summary="List backtest trades",
    description="Returns individual backtest trade results, ordered by entry date descending.",
)
def backtest_trades(
    instrument: Optional[str] = Query(None, description="Filter by instrument key (e.g. EURUSD)"),
    limit: int = Query(50, ge=1, le=500, description="Maximum number of trades to return"),
) -> list[dict]:
    """List recent backtest trade results."""
    if instrument:
        try:
            instrument = validate_symbol(instrument)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))

    gen = session_scope()
    session = next(gen)
    try:
        stmt = select(BacktestResult).order_by(BacktestResult.entry_date.desc())
        if instrument:
            stmt = stmt.where(BacktestResult.instrument == instrument)
        stmt = stmt.limit(limit)
        rows = session.execute(stmt).scalars().all()

        trades = [
            {
                "id": r.id,
                "instrument": r.instrument,
                "direction": r.direction,
                "grade": r.grade,
                "score": r.score,
                "entry_date": r.entry_date,
                "entry_price": r.entry_price,
                "exit_date": r.exit_date,
                "exit_price": r.exit_price,
                "exit_reason": r.exit_reason,
                "pnl_pips": r.pnl_pips,
                "pnl_rr": r.pnl_rr,
                "duration_hours": r.duration_hours,
            }
            for r in rows
        ]

        try:
            gen.send(None)
        except StopIteration:
            pass
        return trades
    except Exception:
        try:
            gen.throw(Exception)
        except StopIteration:
            pass
        raise
