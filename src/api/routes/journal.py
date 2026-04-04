"""Trade journal API routes — reasoning-enriched trade history."""

from __future__ import annotations

import json
from typing import Any, Optional

from fastapi import APIRouter, Query
from pydantic import BaseModel
from sqlalchemy import func, select

from src.db.engine import session_ctx
from src.db.models import TradeJournal

router = APIRouter(prefix="/api/v1/journal", tags=["journal"])


# ── Response models ──────────────────────────────────────────────────────────


class JournalEntryResponse(BaseModel):
    id: int
    created_at: str
    instrument: str
    direction: str
    grade: str
    score: int
    entry_reasoning: Optional[dict] = None
    gate_reasoning: Optional[list] = None
    exit_reasoning: Optional[dict] = None
    outcome: Optional[str] = None
    pnl_pips: Optional[float] = None
    pnl_rr: Optional[float] = None
    lessons: Optional[str] = None


class JournalStatsResponse(BaseModel):
    total: int
    wins: int
    losses: int
    breakeven: int
    pending: int
    win_rate: Optional[float] = None
    avg_pnl_pips: Optional[float] = None


class JournalListResponse(BaseModel):
    stats: JournalStatsResponse
    entries: list[JournalEntryResponse]


def _entry_to_dict(row: Any) -> dict:
    """Convert a TradeJournal row to a JSON-friendly dict."""

    def _parse_json(val: str | None) -> Any:
        if val is None:
            return None
        try:
            return json.loads(val)
        except (json.JSONDecodeError, TypeError):
            return None

    return {
        "id": row.id,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "instrument": row.instrument,
        "direction": row.direction,
        "grade": row.grade,
        "score": row.score,
        "entry_reasoning": _parse_json(row.entry_reasoning),
        "gate_reasoning": _parse_json(row.gate_reasoning),
        "exit_reasoning": _parse_json(row.exit_reasoning),
        "outcome": row.outcome,
        "pnl_pips": row.pnl_pips,
        "pnl_rr": row.pnl_rr,
        "lessons": row.lessons,
    }


# ── Endpoints ────────────────────────────────────────────────────────────────


@router.get(
    "",
    response_model=JournalListResponse,
    summary="Trade journal with reasoning",
)
def list_journal(
    instrument: Optional[str] = Query(None, description="Filter by instrument"),
    outcome: Optional[str] = Query(None, description="Filter: win, loss, breakeven, pending"),
    limit: int = Query(50, ge=1, le=200, description="Max entries"),
) -> dict:
    """Return trade journal entries with reasoning and stats."""
    with session_ctx() as session:
        total = session.execute(
            select(func.count(TradeJournal.id))
        ).scalar() or 0
        wins = session.execute(
            select(func.count(TradeJournal.id)).where(TradeJournal.outcome == "win")
        ).scalar() or 0
        losses = session.execute(
            select(func.count(TradeJournal.id)).where(TradeJournal.outcome == "loss")
        ).scalar() or 0
        breakeven = session.execute(
            select(func.count(TradeJournal.id)).where(TradeJournal.outcome == "breakeven")
        ).scalar() or 0
        pending_count = session.execute(
            select(func.count(TradeJournal.id)).where(TradeJournal.outcome == "pending")
        ).scalar() or 0
        avg_pnl = session.execute(
            select(func.avg(TradeJournal.pnl_pips)).where(TradeJournal.pnl_pips.isnot(None))
        ).scalar()

        closed = wins + losses
        stats: dict[str, Any] = {
            "total": total,
            "wins": wins,
            "losses": losses,
            "breakeven": breakeven,
            "pending": pending_count,
            "win_rate": round(wins / closed * 100, 1) if closed > 0 else None,
            "avg_pnl_pips": round(float(avg_pnl), 2) if avg_pnl is not None else None,
        }

        stmt = select(TradeJournal).order_by(TradeJournal.created_at.desc())
        if instrument:
            stmt = stmt.where(TradeJournal.instrument == instrument)
        if outcome:
            stmt = stmt.where(TradeJournal.outcome == outcome.lower())
        rows = session.execute(stmt.limit(limit)).scalars().all()

        return {"stats": stats, "entries": [_entry_to_dict(r) for r in rows]}
