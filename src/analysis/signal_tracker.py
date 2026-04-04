"""Signal performance tracking — record outcomes and compute hit-rate stats.

All functions follow the repository pattern established in ``src.db.repository``:
accept an optional ``db`` session, falling back to ``session_ctx()`` when None.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.db.engine import session_ctx
from src.db.models import SignalPerformance

_VALID_RESULTS = {"HIT", "MISS", "NEUTRAL", "PENDING"}
_RESOLVED_RESULTS = {"HIT", "MISS", "NEUTRAL"}


def record_signal(
    signal_id: int,
    instrument: str,
    direction: str,
    grade: str,
    score: int,
    entry_price: float,
    db: Session | None = None,
) -> dict[str, Any]:
    """Record a new signal in the SignalPerformance table.

    Returns the record as a plain dict.
    """

    def _do(session: Session) -> dict[str, Any]:
        row = SignalPerformance(
            signal_id=signal_id,
            instrument=instrument,
            direction=direction,
            grade=grade,
            score=score,
            entry_price=entry_price,
            result="PENDING",
        )
        session.add(row)
        session.flush()
        return _row_to_dict(row)

    if db is not None:
        return _do(db)
    with session_ctx() as session:
        return _do(session)


def update_result(
    signal_id: int,
    result: str,
    pnl_pips: float | None = None,
    db: Session | None = None,
) -> dict[str, Any]:
    """Update signal result (HIT/MISS/NEUTRAL) and optional PnL.

    Returns the updated record as a dict.
    Raises ``ValueError`` if the result string is invalid or the signal is not found.
    """
    if result.upper() not in _VALID_RESULTS:
        raise ValueError(f"Invalid result '{result}', must be one of {_VALID_RESULTS}")

    def _do(session: Session) -> dict[str, Any]:
        stmt = select(SignalPerformance).where(SignalPerformance.signal_id == signal_id)
        row = session.execute(stmt).scalar_one_or_none()
        if row is None:
            raise ValueError(f"SignalPerformance with signal_id={signal_id} not found")
        row.result = result.upper()
        if pnl_pips is not None:
            row.pnl_pips = pnl_pips
        if result.upper() in _RESOLVED_RESULTS:
            row.closed_at = datetime.now(timezone.utc)
        session.flush()
        return _row_to_dict(row)

    if db is not None:
        return _do(db)
    with session_ctx() as session:
        return _do(session)


def get_stats(db: Session | None = None) -> dict[str, Any]:
    """Return aggregate signal performance statistics.

    Returns a dict with:
    - total_signals: count of resolved signals (result != PENDING)
    - overall_hit_rate: fraction of HIT among resolved signals
    - per_grade_stats: dict keyed by grade (A+, A, B, C) with count and hit_rate
    """

    def _do(session: Session) -> dict[str, Any]:
        # Only count resolved signals.
        resolved_filter = SignalPerformance.result.in_(list(_RESOLVED_RESULTS))

        total_stmt = select(func.count(SignalPerformance.id)).where(resolved_filter)
        total: int = session.execute(total_stmt).scalar_one() or 0

        hit_stmt = select(func.count(SignalPerformance.id)).where(
            resolved_filter,
            SignalPerformance.result == "HIT",
        )
        hits: int = session.execute(hit_stmt).scalar_one() or 0

        overall_hit_rate = (hits / total) if total > 0 else 0.0

        # Per-grade breakdown.
        per_grade: dict[str, dict[str, Any]] = {}
        for grade in ("A+", "A", "B", "C"):
            grade_total_stmt = select(func.count(SignalPerformance.id)).where(
                resolved_filter,
                SignalPerformance.grade == grade,
            )
            grade_total: int = session.execute(grade_total_stmt).scalar_one() or 0

            grade_hit_stmt = select(func.count(SignalPerformance.id)).where(
                resolved_filter,
                SignalPerformance.grade == grade,
                SignalPerformance.result == "HIT",
            )
            grade_hits: int = session.execute(grade_hit_stmt).scalar_one() or 0

            per_grade[grade] = {
                "count": grade_total,
                "hit_rate": (grade_hits / grade_total) if grade_total > 0 else 0.0,
            }

        return {
            "total_signals": total,
            "overall_hit_rate": round(overall_hit_rate, 4),
            "per_grade_stats": per_grade,
        }

    if db is not None:
        return _do(db)
    with session_ctx() as session:
        return _do(session)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------
def _row_to_dict(row: SignalPerformance) -> dict[str, Any]:
    """Convert an ORM row to a plain dict."""
    return {
        "id": row.id,
        "signal_id": row.signal_id,
        "instrument": row.instrument,
        "direction": row.direction,
        "grade": row.grade,
        "score": row.score,
        "entry_price": row.entry_price,
        "result": row.result,
        "pnl_pips": row.pnl_pips,
        "created_at": str(row.created_at) if row.created_at else None,
        "closed_at": str(row.closed_at) if row.closed_at else None,
    }
