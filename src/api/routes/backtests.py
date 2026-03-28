"""Backtest results API routes."""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import case, func, select

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
                select(func.count(BacktestResult.id)).where(BacktestResult.exit_reason.in_(["t1_hit", "t2_hit"]))
            ).scalar()
            or 0
        )
        avg_pnl_rr = session.execute(select(func.avg(BacktestResult.pnl_rr))).scalar() or 0.0
        avg_duration = session.execute(select(func.avg(BacktestResult.duration_hours))).scalar() or 0.0

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


# ── Enhanced stats endpoint ──────────────────────────────────────────────


class InstrumentBreakdown(BaseModel):
    """Per-instrument backtest stats."""

    instrument: str
    trades: int
    wins: int
    win_rate: float
    avg_pnl: float
    total_pnl: float


class GradeBreakdown(BaseModel):
    """Per-grade backtest stats."""

    grade: str
    trades: int
    wins: int
    win_rate: float


class BacktestStatsResponse(BaseModel):
    """Full backtest statistics with breakdowns."""

    total_trades: int
    wins: int
    losses: int
    win_rate: float
    avg_win_rr: float
    avg_loss_rr: float
    profit_factor: float
    max_drawdown_rr: float
    avg_rr: float
    best_trade_rr: float
    worst_trade_rr: float
    avg_duration_hours: float
    equity_curve: list[float]
    by_instrument: list[InstrumentBreakdown]
    by_grade: list[GradeBreakdown]


@router.get(
    "/stats",
    response_model=BacktestStatsResponse,
    summary="Full backtest statistics",
    description="Returns 12 performance metrics, equity curve, per-instrument and per-grade breakdowns.",
)
def backtest_stats() -> dict:
    """Full backtest stats with equity curve and breakdowns."""
    gen = session_scope()
    session = next(gen)
    try:
        rows = session.execute(
            select(BacktestResult).order_by(BacktestResult.entry_date.asc())
        ).scalars().all()

        if not rows:
            result = {
                "total_trades": 0, "wins": 0, "losses": 0, "win_rate": 0.0,
                "avg_win_rr": 0.0, "avg_loss_rr": 0.0, "profit_factor": 0.0,
                "max_drawdown_rr": 0.0, "avg_rr": 0.0, "best_trade_rr": 0.0,
                "worst_trade_rr": 0.0, "avg_duration_hours": 0.0,
                "equity_curve": [], "by_instrument": [], "by_grade": [],
            }
            try:
                gen.send(None)
            except StopIteration:
                pass
            return result

        # Core stats
        pnls = [r.pnl_rr or 0.0 for r in rows]
        win_pnls = [p for p in pnls if p > 0]
        loss_pnls = [p for p in pnls if p <= 0]
        total = len(rows)
        wins = len(win_pnls)
        losses = total - wins

        # Equity curve (cumulative PnL)
        equity = []
        cumulative = 0.0
        for p in pnls:
            cumulative += p
            equity.append(round(cumulative, 2))

        # Max drawdown
        peak = 0.0
        max_dd = 0.0
        for eq in equity:
            if eq > peak:
                peak = eq
            dd = peak - eq
            if dd > max_dd:
                max_dd = dd

        # Profit factor
        gross_profit = sum(win_pnls) if win_pnls else 0.0
        gross_loss = abs(sum(loss_pnls)) if loss_pnls else 0.001

        # Per-instrument breakdown
        inst_map: dict[str, list] = {}
        for r in rows:
            inst_map.setdefault(r.instrument, []).append(r)

        by_instrument = []
        for inst, trades in sorted(inst_map.items()):
            inst_pnls = [t.pnl_rr or 0.0 for t in trades]
            inst_wins = sum(1 for p in inst_pnls if p > 0)
            by_instrument.append({
                "instrument": inst,
                "trades": len(trades),
                "wins": inst_wins,
                "win_rate": round(inst_wins / len(trades) * 100, 1) if trades else 0,
                "avg_pnl": round(sum(inst_pnls) / len(inst_pnls), 2) if inst_pnls else 0,
                "total_pnl": round(sum(inst_pnls), 2),
            })

        # Per-grade breakdown
        grade_map: dict[str, list] = {}
        for r in rows:
            grade_map.setdefault(r.grade or "?", []).append(r)

        by_grade = []
        for grade, trades in sorted(grade_map.items()):
            grade_wins = sum(1 for t in trades if (t.pnl_rr or 0) > 0)
            by_grade.append({
                "grade": grade,
                "trades": len(trades),
                "wins": grade_wins,
                "win_rate": round(grade_wins / len(trades) * 100, 1) if trades else 0,
            })

        durations = [r.duration_hours or 0.0 for r in rows if r.duration_hours]

        result = {
            "total_trades": total,
            "wins": wins,
            "losses": losses,
            "win_rate": round(wins / total * 100, 1) if total else 0,
            "avg_win_rr": round(sum(win_pnls) / len(win_pnls), 2) if win_pnls else 0,
            "avg_loss_rr": round(sum(loss_pnls) / len(loss_pnls), 2) if loss_pnls else 0,
            "profit_factor": round(gross_profit / gross_loss, 2),
            "max_drawdown_rr": round(max_dd, 2),
            "avg_rr": round(sum(pnls) / len(pnls), 2) if pnls else 0,
            "best_trade_rr": round(max(pnls), 2) if pnls else 0,
            "worst_trade_rr": round(min(pnls), 2) if pnls else 0,
            "avg_duration_hours": round(sum(durations) / len(durations), 1) if durations else 0,
            "equity_curve": equity,
            "by_instrument": by_instrument,
            "by_grade": by_grade,
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
