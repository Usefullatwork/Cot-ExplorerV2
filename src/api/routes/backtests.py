"""Backtest results API routes."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.db.engine import session_scope
from src.db.models import BacktestResult
from src.security.input_validator import validate_instrument_key

router = APIRouter(prefix="/api/v1/backtests", tags=["backtests"])


@router.get("/summary")
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


@router.get("/trades")
def backtest_trades(
    instrument: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=500),
) -> list[dict]:
    """List recent backtest trade results."""
    if instrument:
        try:
            instrument = validate_instrument_key(instrument)
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
