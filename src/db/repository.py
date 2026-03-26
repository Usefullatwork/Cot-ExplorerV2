"""CRUD operations for all database models."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Optional, Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.db.engine import session_scope
from src.db.models import (
    AuditLog,
    BotConfig,
    BotPosition,
    BotSignal,
    BotTradeLog,
    CotPosition,
    MacroSnapshot,
    PriceDaily,
    Signal,
)


# ---------------------------------------------------------------------------
# Signals
# ---------------------------------------------------------------------------
def save_signal(signal_data: dict[str, Any], db: Session | None = None) -> Signal:
    """Persist a signal dict and return the ORM object."""

    def _do(session: Session) -> Signal:
        score_details = signal_data.pop("score_details", None)
        metadata = signal_data.pop("metadata", None)
        sig = Signal(
            **signal_data,
            score_details=json.dumps(score_details) if score_details else None,
            metadata_=json.dumps(metadata) if metadata else None,
        )
        session.add(sig)
        session.flush()
        return sig

    if db is not None:
        return _do(db)
    gen = session_scope()
    session = next(gen)
    try:
        result = _do(session)
        gen.send(None)  # trigger commit
    except StopIteration:
        pass
    return result


def get_signals(
    instrument: str | None = None,
    start: str | None = None,
    end: str | None = None,
    min_score: int | None = None,
    grades: list[str] | None = None,
    limit: int = 100,
    db: Session | None = None,
) -> Sequence[Signal]:
    """Query signals with optional filters."""

    def _do(session: Session) -> Sequence[Signal]:
        stmt = select(Signal).order_by(Signal.generated_at.desc())
        if instrument:
            stmt = stmt.where(Signal.instrument == instrument)
        if start:
            stmt = stmt.where(Signal.generated_at >= datetime.fromisoformat(start))
        if end:
            stmt = stmt.where(Signal.generated_at <= datetime.fromisoformat(end))
        if min_score is not None:
            stmt = stmt.where(Signal.score >= min_score)
        if grades:
            stmt = stmt.where(Signal.grade.in_(grades))
        stmt = stmt.limit(limit)
        return session.execute(stmt).scalars().all()

    if db is not None:
        return _do(db)
    gen = session_scope()
    session = next(gen)
    try:
        result = _do(session)
        try:
            gen.send(None)
        except StopIteration:
            pass
    except Exception:
        try:
            gen.throw(Exception)
        except StopIteration:
            pass
        raise
    return result


# ---------------------------------------------------------------------------
# PriceDaily
# ---------------------------------------------------------------------------
def save_price_daily(
    instrument: str,
    date: str,
    ohlcv: dict[str, Any],
    db: Session | None = None,
) -> PriceDaily:
    """Upsert a daily price bar."""

    def _do(session: Session) -> PriceDaily:
        existing = session.execute(
            select(PriceDaily).where(
                PriceDaily.instrument == instrument,
                PriceDaily.date == date,
            )
        ).scalar_one_or_none()
        if existing:
            existing.open_ = ohlcv.get("open")
            existing.high = ohlcv["high"]
            existing.low = ohlcv["low"]
            existing.close = ohlcv["close"]
            existing.volume = ohlcv.get("volume")
            existing.source = ohlcv.get("source")
            session.flush()
            return existing
        row = PriceDaily(
            instrument=instrument,
            date=date,
            open_=ohlcv.get("open"),
            high=ohlcv["high"],
            low=ohlcv["low"],
            close=ohlcv["close"],
            volume=ohlcv.get("volume"),
            source=ohlcv.get("source"),
        )
        session.add(row)
        session.flush()
        return row

    if db is not None:
        return _do(db)
    gen = session_scope()
    session = next(gen)
    try:
        result = _do(session)
        try:
            gen.send(None)
        except StopIteration:
            pass
    except Exception:
        try:
            gen.throw(Exception)
        except StopIteration:
            pass
        raise
    return result


def get_price_history(
    instrument: str,
    start: str | None = None,
    end: str | None = None,
    db: Session | None = None,
) -> Sequence[PriceDaily]:
    """Return daily price bars for an instrument, ordered by date ascending."""

    def _do(session: Session) -> Sequence[PriceDaily]:
        stmt = select(PriceDaily).where(PriceDaily.instrument == instrument).order_by(PriceDaily.date.asc())
        if start:
            stmt = stmt.where(PriceDaily.date >= start)
        if end:
            stmt = stmt.where(PriceDaily.date <= end)
        return session.execute(stmt).scalars().all()

    if db is not None:
        return _do(db)
    gen = session_scope()
    session = next(gen)
    try:
        result = _do(session)
        try:
            gen.send(None)
        except StopIteration:
            pass
    except Exception:
        try:
            gen.throw(Exception)
        except StopIteration:
            pass
        raise
    return result


# ---------------------------------------------------------------------------
# CotPosition
# ---------------------------------------------------------------------------
def save_cot_position(data: dict[str, Any], db: Session | None = None) -> CotPosition:
    """Upsert a COT position record."""

    def _do(session: Session) -> CotPosition:
        existing = session.execute(
            select(CotPosition).where(
                CotPosition.symbol == data["symbol"],
                CotPosition.report_type == data["report_type"],
                CotPosition.date == data["date"],
            )
        ).scalar_one_or_none()
        if existing:
            for col in (
                "market",
                "open_interest",
                "change_oi",
                "spec_long",
                "spec_short",
                "spec_net",
                "comm_long",
                "comm_short",
                "comm_net",
                "nonrept_long",
                "nonrept_short",
                "nonrept_net",
                "change_spec_net",
                "category",
            ):
                if col in data:
                    setattr(existing, col, data[col])
            session.flush()
            return existing
        row = CotPosition(**data)
        session.add(row)
        session.flush()
        return row

    if db is not None:
        return _do(db)
    gen = session_scope()
    session = next(gen)
    try:
        result = _do(session)
        try:
            gen.send(None)
        except StopIteration:
            pass
    except Exception:
        try:
            gen.throw(Exception)
        except StopIteration:
            pass
        raise
    return result


def get_cot_history(
    symbol: str,
    start: str | None = None,
    end: str | None = None,
    report_type: str | None = None,
    db: Session | None = None,
) -> Sequence[CotPosition]:
    """Return COT history for a symbol, ordered by date ascending."""

    def _do(session: Session) -> Sequence[CotPosition]:
        stmt = select(CotPosition).where(CotPosition.symbol == symbol).order_by(CotPosition.date.asc())
        if start:
            stmt = stmt.where(CotPosition.date >= start)
        if end:
            stmt = stmt.where(CotPosition.date <= end)
        if report_type:
            stmt = stmt.where(CotPosition.report_type == report_type)
        return session.execute(stmt).scalars().all()

    if db is not None:
        return _do(db)
    gen = session_scope()
    session = next(gen)
    try:
        result = _do(session)
        try:
            gen.send(None)
        except StopIteration:
            pass
    except Exception:
        try:
            gen.throw(Exception)
        except StopIteration:
            pass
        raise
    return result


# ---------------------------------------------------------------------------
# MacroSnapshot
# ---------------------------------------------------------------------------
def save_macro_snapshot(data: dict[str, Any], db: Session | None = None) -> MacroSnapshot:
    """Persist a macro snapshot."""

    def _do(session: Session) -> MacroSnapshot:
        news = data.pop("news_sentiment", None)
        conflicts = data.pop("conflicts", None)
        full_json = data.pop("full_json", None)
        snap = MacroSnapshot(
            **data,
            news_sentiment=json.dumps(news) if news else None,
            conflicts=json.dumps(conflicts) if conflicts else None,
            full_json=json.dumps(full_json) if full_json else None,
        )
        session.add(snap)
        session.flush()
        return snap

    if db is not None:
        return _do(db)
    gen = session_scope()
    session = next(gen)
    try:
        result = _do(session)
        try:
            gen.send(None)
        except StopIteration:
            pass
    except Exception:
        try:
            gen.throw(Exception)
        except StopIteration:
            pass
        raise
    return result


def get_latest_macro(db: Session | None = None) -> Optional[MacroSnapshot]:
    """Return the most recent macro snapshot."""

    def _do(session: Session) -> Optional[MacroSnapshot]:
        stmt = select(MacroSnapshot).order_by(MacroSnapshot.generated_at.desc()).limit(1)
        return session.execute(stmt).scalar_one_or_none()

    if db is not None:
        return _do(db)
    gen = session_scope()
    session = next(gen)
    try:
        result = _do(session)
        try:
            gen.send(None)
        except StopIteration:
            pass
    except Exception:
        try:
            gen.throw(Exception)
        except StopIteration:
            pass
        raise
    return result


# ---------------------------------------------------------------------------
# AuditLog
# ---------------------------------------------------------------------------
def save_audit_log(
    event_type: str,
    details: dict[str, Any] | None = None,
    db: Session | None = None,
) -> AuditLog:
    """Write an entry to the audit log."""

    def _do(session: Session) -> AuditLog:
        entry = AuditLog(
            event_type=event_type,
            details=json.dumps(details) if details else None,
        )
        session.add(entry)
        session.flush()
        return entry

    if db is not None:
        return _do(db)
    gen = session_scope()
    session = next(gen)
    try:
        result = _do(session)
        try:
            gen.send(None)
        except StopIteration:
            pass
    except Exception:
        try:
            gen.throw(Exception)
        except StopIteration:
            pass
        raise
    return result


# ---------------------------------------------------------------------------
# BotConfig
# ---------------------------------------------------------------------------
def get_bot_config(db: Session | None = None) -> BotConfig:
    """Return the single bot config row, creating a default if none exists."""

    def _do(session: Session) -> BotConfig:
        stmt = select(BotConfig).limit(1)
        config = session.execute(stmt).scalar_one_or_none()
        if config is None:
            config = BotConfig()
            session.add(config)
            session.flush()
        return config

    if db is not None:
        return _do(db)
    gen = session_scope()
    session = next(gen)
    try:
        result = _do(session)
        try:
            gen.send(None)
        except StopIteration:
            pass
    except Exception:
        try:
            gen.throw(Exception)
        except StopIteration:
            pass
        raise
    return result


def update_bot_config(db: Session | None = None, **kwargs: Any) -> BotConfig:
    """Update bot config fields and return the updated row."""

    def _do(session: Session) -> BotConfig:
        stmt = select(BotConfig).limit(1)
        config = session.execute(stmt).scalar_one_or_none()
        if config is None:
            config = BotConfig()
            session.add(config)
        for key, value in kwargs.items():
            if hasattr(config, key):
                setattr(config, key, value)
        session.flush()
        return config

    if db is not None:
        return _do(db)
    gen = session_scope()
    session = next(gen)
    try:
        result = _do(session)
        try:
            gen.send(None)
        except StopIteration:
            pass
    except Exception:
        try:
            gen.throw(Exception)
        except StopIteration:
            pass
        raise
    return result


# ---------------------------------------------------------------------------
# BotSignal
# ---------------------------------------------------------------------------
def save_bot_signal(db: Session | None = None, **kwargs: Any) -> BotSignal:
    """Create a new bot signal record."""

    def _do(session: Session) -> BotSignal:
        tv_payload = kwargs.pop("tv_payload", None)
        sig = BotSignal(
            **kwargs,
            tv_payload=json.dumps(tv_payload) if isinstance(tv_payload, dict) else tv_payload,
        )
        session.add(sig)
        session.flush()
        return sig

    if db is not None:
        return _do(db)
    gen = session_scope()
    session = next(gen)
    try:
        result = _do(session)
        try:
            gen.send(None)
        except StopIteration:
            pass
    except Exception:
        try:
            gen.throw(Exception)
        except StopIteration:
            pass
        raise
    return result


def get_bot_signals(
    status: str | None = None,
    instrument: str | None = None,
    limit: int = 50,
    db: Session | None = None,
) -> Sequence[BotSignal]:
    """List bot signals with optional status and instrument filters."""

    def _do(session: Session) -> Sequence[BotSignal]:
        stmt = select(BotSignal).order_by(BotSignal.received_at.desc())
        if status:
            stmt = stmt.where(BotSignal.status == status)
        if instrument:
            stmt = stmt.where(BotSignal.instrument == instrument)
        stmt = stmt.limit(limit)
        return session.execute(stmt).scalars().all()

    if db is not None:
        return _do(db)
    gen = session_scope()
    session = next(gen)
    try:
        result = _do(session)
        try:
            gen.send(None)
        except StopIteration:
            pass
    except Exception:
        try:
            gen.throw(Exception)
        except StopIteration:
            pass
        raise
    return result


def update_bot_signal(
    signal_id: int,
    db: Session | None = None,
    **kwargs: Any,
) -> Optional[BotSignal]:
    """Update fields on a bot signal by id."""

    def _do(session: Session) -> Optional[BotSignal]:
        stmt = select(BotSignal).where(BotSignal.id == signal_id)
        sig = session.execute(stmt).scalar_one_or_none()
        if sig is None:
            return None
        for key, value in kwargs.items():
            if hasattr(sig, key):
                setattr(sig, key, value)
        session.flush()
        return sig

    if db is not None:
        return _do(db)
    gen = session_scope()
    session = next(gen)
    try:
        result = _do(session)
        try:
            gen.send(None)
        except StopIteration:
            pass
    except Exception:
        try:
            gen.throw(Exception)
        except StopIteration:
            pass
        raise
    return result


# ---------------------------------------------------------------------------
# BotPosition
# ---------------------------------------------------------------------------
def save_bot_position(db: Session | None = None, **kwargs: Any) -> BotPosition:
    """Create a new bot position record."""

    def _do(session: Session) -> BotPosition:
        pos = BotPosition(**kwargs)
        session.add(pos)
        session.flush()
        return pos

    if db is not None:
        return _do(db)
    gen = session_scope()
    session = next(gen)
    try:
        result = _do(session)
        try:
            gen.send(None)
        except StopIteration:
            pass
    except Exception:
        try:
            gen.throw(Exception)
        except StopIteration:
            pass
        raise
    return result


def get_bot_positions(
    status: str | None = None,
    instrument: str | None = None,
    db: Session | None = None,
) -> Sequence[BotPosition]:
    """List bot positions with optional status and instrument filters."""

    def _do(session: Session) -> Sequence[BotPosition]:
        stmt = select(BotPosition).order_by(BotPosition.opened_at.desc())
        if status:
            stmt = stmt.where(BotPosition.status == status)
        if instrument:
            stmt = stmt.where(BotPosition.instrument == instrument)
        return session.execute(stmt).scalars().all()

    if db is not None:
        return _do(db)
    gen = session_scope()
    session = next(gen)
    try:
        result = _do(session)
        try:
            gen.send(None)
        except StopIteration:
            pass
    except Exception:
        try:
            gen.throw(Exception)
        except StopIteration:
            pass
        raise
    return result


def get_bot_position(
    position_id: int,
    db: Session | None = None,
) -> Optional[BotPosition]:
    """Return a single bot position by id."""

    def _do(session: Session) -> Optional[BotPosition]:
        stmt = select(BotPosition).where(BotPosition.id == position_id)
        return session.execute(stmt).scalar_one_or_none()

    if db is not None:
        return _do(db)
    gen = session_scope()
    session = next(gen)
    try:
        result = _do(session)
        try:
            gen.send(None)
        except StopIteration:
            pass
    except Exception:
        try:
            gen.throw(Exception)
        except StopIteration:
            pass
        raise
    return result


def update_bot_position(
    position_id: int,
    db: Session | None = None,
    **kwargs: Any,
) -> Optional[BotPosition]:
    """Update fields on a bot position by id."""

    def _do(session: Session) -> Optional[BotPosition]:
        stmt = select(BotPosition).where(BotPosition.id == position_id)
        pos = session.execute(stmt).scalar_one_or_none()
        if pos is None:
            return None
        for key, value in kwargs.items():
            if hasattr(pos, key):
                setattr(pos, key, value)
        session.flush()
        return pos

    if db is not None:
        return _do(db)
    gen = session_scope()
    session = next(gen)
    try:
        result = _do(session)
        try:
            gen.send(None)
        except StopIteration:
            pass
    except Exception:
        try:
            gen.throw(Exception)
        except StopIteration:
            pass
        raise
    return result


# ---------------------------------------------------------------------------
# BotTradeLog
# ---------------------------------------------------------------------------
def save_bot_trade_log(
    position_id: int | None,
    event_type: str,
    details: dict[str, Any] | str | None = None,
    db: Session | None = None,
) -> BotTradeLog:
    """Create a new bot trade log entry."""

    def _do(session: Session) -> BotTradeLog:
        entry = BotTradeLog(
            position_id=position_id,
            event_type=event_type,
            details=json.dumps(details) if isinstance(details, dict) else details,
        )
        session.add(entry)
        session.flush()
        return entry

    if db is not None:
        return _do(db)
    gen = session_scope()
    session = next(gen)
    try:
        result = _do(session)
        try:
            gen.send(None)
        except StopIteration:
            pass
    except Exception:
        try:
            gen.throw(Exception)
        except StopIteration:
            pass
        raise
    return result


def get_bot_trade_log(
    position_id: int | None = None,
    event_type: str | None = None,
    limit: int = 100,
    db: Session | None = None,
) -> Sequence[BotTradeLog]:
    """List bot trade log entries with optional filters."""

    def _do(session: Session) -> Sequence[BotTradeLog]:
        stmt = select(BotTradeLog).order_by(BotTradeLog.timestamp.desc())
        if position_id is not None:
            stmt = stmt.where(BotTradeLog.position_id == position_id)
        if event_type:
            stmt = stmt.where(BotTradeLog.event_type == event_type)
        stmt = stmt.limit(limit)
        return session.execute(stmt).scalars().all()

    if db is not None:
        return _do(db)
    gen = session_scope()
    session = next(gen)
    try:
        result = _do(session)
        try:
            gen.send(None)
        except StopIteration:
            pass
    except Exception:
        try:
            gen.throw(Exception)
        except StopIteration:
            pass
        raise
    return result
