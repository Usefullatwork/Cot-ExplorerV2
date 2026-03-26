"""Unit tests for src.trading.bot.kill_switch — activate, deactivate, query."""

from __future__ import annotations

from src.db.models import BotConfig
from src.trading.bot.kill_switch import (
    activate_kill_switch,
    deactivate_kill_switch,
    is_kill_switch_active,
)


class TestKillSwitch:
    """Kill switch database operations using in-memory SQLite session."""

    def test_activate_sets_flag(self, db_session):
        """activate_kill_switch sets kill_switch_active=True."""
        activate_kill_switch(db_session, reason="test_reason")
        config = db_session.query(BotConfig).first()
        assert config is not None
        assert config.kill_switch_active is True

    def test_activate_records_reason(self, db_session):
        """activate_kill_switch stores the reason string."""
        activate_kill_switch(db_session, reason="geo_spike_detected")
        config = db_session.query(BotConfig).first()
        assert config.kill_switch_reason == "geo_spike_detected"

    def test_activate_records_timestamp(self, db_session):
        """activate_kill_switch sets kill_switch_at."""
        activate_kill_switch(db_session, reason="drawdown")
        config = db_session.query(BotConfig).first()
        assert config.kill_switch_at is not None

    def test_deactivate_clears_flag(self, db_session):
        """deactivate_kill_switch sets kill_switch_active=False."""
        activate_kill_switch(db_session, reason="test")
        deactivate_kill_switch(db_session)
        config = db_session.query(BotConfig).first()
        assert config.kill_switch_active is False

    def test_deactivate_clears_reason(self, db_session):
        """deactivate_kill_switch clears reason and timestamp."""
        activate_kill_switch(db_session, reason="test")
        deactivate_kill_switch(db_session)
        config = db_session.query(BotConfig).first()
        assert config.kill_switch_reason is None
        assert config.kill_switch_at is None

    def test_is_active_true(self, db_session):
        """is_kill_switch_active returns True after activation."""
        activate_kill_switch(db_session, reason="manual")
        assert is_kill_switch_active(db_session) is True

    def test_is_active_false(self, db_session):
        """is_kill_switch_active returns False after deactivation."""
        activate_kill_switch(db_session, reason="test")
        deactivate_kill_switch(db_session)
        assert is_kill_switch_active(db_session) is False

    def test_default_config_not_active(self, db_session):
        """Empty DB returns False (no config row exists)."""
        assert is_kill_switch_active(db_session) is False
