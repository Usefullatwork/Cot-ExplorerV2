"""Kill switch management — activate, deactivate, and query.

Operates on a SQLAlchemy session against the ``bot_config`` table.
All mutations are flushed but NOT committed — the caller owns the
transaction boundary.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from src.db.models import BotConfig


def _get_or_create_config(session: Session) -> BotConfig:
    """Return the single BotConfig row, creating one if absent."""
    config = session.query(BotConfig).first()
    if config is None:
        config = BotConfig(active=False)
        session.add(config)
        session.flush()
    return config


def activate_kill_switch(session: Session, reason: str) -> None:
    """Activate the kill switch, recording reason and timestamp.

    Args:
        session: Active SQLAlchemy session.
        reason: Human-readable reason for activation (e.g. "geo_spike",
            "manual", "drawdown_limit").
    """
    config = _get_or_create_config(session)
    config.kill_switch_active = True
    config.kill_switch_reason = reason
    config.kill_switch_at = datetime.now(timezone.utc)
    config.updated_at = datetime.now(timezone.utc)
    session.flush()


def deactivate_kill_switch(session: Session) -> None:
    """Deactivate the kill switch, clearing reason and timestamp.

    Args:
        session: Active SQLAlchemy session.
    """
    config = _get_or_create_config(session)
    config.kill_switch_active = False
    config.kill_switch_reason = None
    config.kill_switch_at = None
    config.updated_at = datetime.now(timezone.utc)
    session.flush()


def is_kill_switch_active(session: Session) -> bool:
    """Check whether the kill switch is currently active.

    Args:
        session: Active SQLAlchemy session.

    Returns:
        True if the kill switch is active, False otherwise.
    """
    config = session.query(BotConfig).first()
    if config is None:
        return False
    return bool(config.kill_switch_active)
