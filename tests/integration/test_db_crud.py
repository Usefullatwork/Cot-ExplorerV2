"""Integration tests for src.db.repository CRUD operations."""

from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest

from src.db import repository as repo
from src.db.models import AuditLog, CotPosition, MacroSnapshot, PriceDaily, Signal


# ===========================================================================
# Signals
# ===========================================================================

class TestSaveSignal:

    def test_save_minimal(self, db_session, seed_instrument):
        """Save a signal with only required fields."""
        sig = repo.save_signal(
            {
                "instrument": "EURUSD",
                "generated_at": datetime(2026, 3, 25, tzinfo=timezone.utc),
                "direction": "bull",
                "grade": "A",
                "score": 9,
                "timeframe_bias": "weekly",
            },
            db=db_session,
        )
        db_session.commit()
        assert sig.id is not None
        assert sig.instrument == "EURUSD"
        assert sig.score == 9

    def test_save_with_json_fields(self, db_session, seed_instrument):
        """Save signal with score_details and metadata as dicts."""
        sig = repo.save_signal(
            {
                "instrument": "EURUSD",
                "generated_at": datetime(2026, 3, 25, tzinfo=timezone.utc),
                "direction": "bear",
                "grade": "B",
                "score": 6,
                "timeframe_bias": "daily",
                "score_details": {"cot": 2, "smc": 1, "calendar": 3},
                "metadata": {"notes": "test run"},
            },
            db=db_session,
        )
        db_session.commit()
        assert json.loads(sig.score_details) == {"cot": 2, "smc": 1, "calendar": 3}
        assert json.loads(sig.metadata_) == {"notes": "test run"}

    def test_save_with_all_fields(self, db_session, seed_instrument):
        """Save a fully populated signal."""
        sig = repo.save_signal(
            {
                "instrument": "EURUSD",
                "generated_at": datetime(2026, 3, 25, tzinfo=timezone.utc),
                "direction": "bull",
                "grade": "A+",
                "score": 11,
                "timeframe_bias": "weekly",
                "entry_price": 1.08,
                "stop_loss": 1.075,
                "target_1": 1.09,
                "target_2": 1.10,
                "rr_t1": 2.0,
                "rr_t2": 4.0,
                "entry_weight": 50,
                "t1_weight": 30,
                "sl_type": "structure",
                "at_level_now": True,
                "vix_regime": "low",
                "pos_size": "full",
            },
            db=db_session,
        )
        db_session.commit()
        assert sig.entry_price == 1.08
        assert sig.at_level_now is True
        assert sig.vix_regime == "low"


class TestGetSignals:

    def _seed(self, session, seed_instrument):
        for i, (grade, score) in enumerate([("A+", 11), ("A", 9), ("B", 6), ("C", 3)]):
            repo.save_signal(
                {
                    "instrument": "EURUSD",
                    "generated_at": datetime(2026, 3, 25 - i, tzinfo=timezone.utc),
                    "direction": "bull" if i % 2 == 0 else "bear",
                    "grade": grade,
                    "score": score,
                    "timeframe_bias": "weekly",
                },
                db=session,
            )
        session.commit()

    def test_get_all(self, db_session, seed_instrument):
        """Get all signals without filters."""
        self._seed(db_session, seed_instrument)
        results = repo.get_signals(db=db_session)
        assert len(results) == 4

    def test_filter_instrument(self, db_session, seed_instrument):
        """Filter by instrument key."""
        self._seed(db_session, seed_instrument)
        results = repo.get_signals(instrument="EURUSD", db=db_session)
        assert len(results) == 4
        results = repo.get_signals(instrument="NOPE", db=db_session)
        assert len(results) == 0

    def test_filter_min_score(self, db_session, seed_instrument):
        """Filter by minimum score."""
        self._seed(db_session, seed_instrument)
        results = repo.get_signals(min_score=9, db=db_session)
        assert len(results) == 2

    def test_filter_grades(self, db_session, seed_instrument):
        """Filter by grade list."""
        self._seed(db_session, seed_instrument)
        results = repo.get_signals(grades=["A+", "A"], db=db_session)
        assert len(results) == 2
        assert all(r.grade in ("A+", "A") for r in results)

    def test_limit(self, db_session, seed_instrument):
        """Limit caps result count."""
        self._seed(db_session, seed_instrument)
        results = repo.get_signals(limit=2, db=db_session)
        assert len(results) == 2

    def test_order_desc(self, db_session, seed_instrument):
        """Results are ordered by generated_at descending."""
        self._seed(db_session, seed_instrument)
        results = repo.get_signals(db=db_session)
        dates = [r.generated_at for r in results]
        assert dates == sorted(dates, reverse=True)


# ===========================================================================
# PriceDaily
# ===========================================================================

class TestPriceDaily:

    def test_save_new(self, db_session, seed_instrument):
        """Insert a new daily price bar."""
        row = repo.save_price_daily(
            instrument="EURUSD",
            date="2026-03-25",
            ohlcv={"open": 1.07, "high": 1.09, "low": 1.065, "close": 1.085, "volume": 10000, "source": "test"},
            db=db_session,
        )
        db_session.commit()
        assert row.id is not None
        assert row.close == 1.085
        assert row.source == "test"

    def test_upsert_existing(self, db_session, seed_instrument):
        """Saving same instrument+date updates the existing row."""
        repo.save_price_daily(
            instrument="EURUSD",
            date="2026-03-25",
            ohlcv={"high": 1.09, "low": 1.065, "close": 1.085},
            db=db_session,
        )
        db_session.commit()

        repo.save_price_daily(
            instrument="EURUSD",
            date="2026-03-25",
            ohlcv={"high": 1.10, "low": 1.07, "close": 1.095},
            db=db_session,
        )
        db_session.commit()

        history = repo.get_price_history(instrument="EURUSD", db=db_session)
        assert len(history) == 1
        assert history[0].close == 1.095

    def test_get_price_history_ordered(self, db_session, seed_instrument):
        """Price history returns rows ordered by date ascending."""
        for d in ("2026-03-23", "2026-03-25", "2026-03-24"):
            repo.save_price_daily(
                instrument="EURUSD",
                date=d,
                ohlcv={"high": 1.09, "low": 1.07, "close": 1.08},
                db=db_session,
            )
        db_session.commit()

        history = repo.get_price_history(instrument="EURUSD", db=db_session)
        dates = [h.date for h in history]
        assert dates == ["2026-03-23", "2026-03-24", "2026-03-25"]

    def test_get_price_history_date_range(self, db_session, seed_instrument):
        """Filter price history by start/end dates."""
        for d in ("2026-03-20", "2026-03-22", "2026-03-24"):
            repo.save_price_daily(
                instrument="EURUSD",
                date=d,
                ohlcv={"high": 1.09, "low": 1.07, "close": 1.08},
                db=db_session,
            )
        db_session.commit()

        history = repo.get_price_history(
            instrument="EURUSD", start="2026-03-21", end="2026-03-23", db=db_session
        )
        assert len(history) == 1
        assert history[0].date == "2026-03-22"


# ===========================================================================
# CotPosition
# ===========================================================================

class TestCotPosition:

    _BASE = {
        "symbol": "GOLD",
        "market": "Gold Futures",
        "report_type": "tff",
        "date": "2026-03-20",
        "open_interest": 500000,
        "change_oi": 1000,
        "spec_long": 200000,
        "spec_short": 100000,
        "spec_net": 100000,
        "comm_long": 150000,
        "comm_short": 200000,
        "comm_net": -50000,
        "nonrept_long": 50000,
        "nonrept_short": 50000,
        "nonrept_net": 0,
        "change_spec_net": 5000,
        "category": "metals",
    }

    def test_save_new(self, db_session):
        """Insert a new COT position."""
        row = repo.save_cot_position(dict(self._BASE), db=db_session)
        db_session.commit()
        assert row.id is not None
        assert row.spec_net == 100000

    def test_upsert_existing(self, db_session):
        """Saving same symbol+report_type+date updates existing."""
        repo.save_cot_position(dict(self._BASE), db=db_session)
        db_session.commit()

        updated = dict(self._BASE)
        updated["spec_net"] = 120000
        repo.save_cot_position(updated, db=db_session)
        db_session.commit()

        history = repo.get_cot_history(symbol="GOLD", db=db_session)
        assert len(history) == 1
        assert history[0].spec_net == 120000

    def test_get_cot_history(self, db_session):
        """Get COT history returns ordered rows."""
        for d in ("2026-03-18", "2026-03-20", "2026-03-19"):
            data = dict(self._BASE)
            data["date"] = d
            repo.save_cot_position(data, db=db_session)
        db_session.commit()

        history = repo.get_cot_history(symbol="GOLD", db=db_session)
        assert len(history) == 3
        dates = [h.date for h in history]
        assert dates == ["2026-03-18", "2026-03-19", "2026-03-20"]

    def test_get_cot_history_filter_report_type(self, db_session):
        """Filter COT history by report type."""
        for rt in ("tff", "legacy"):
            data = dict(self._BASE)
            data["report_type"] = rt
            repo.save_cot_position(data, db=db_session)
        db_session.commit()

        history = repo.get_cot_history(symbol="GOLD", report_type="legacy", db=db_session)
        assert len(history) == 1
        assert history[0].report_type == "legacy"


# ===========================================================================
# MacroSnapshot
# ===========================================================================

class TestMacroSnapshot:

    def test_save_and_get(self, db_session):
        """Save a macro snapshot and retrieve it."""
        snap = repo.save_macro_snapshot(
            {
                "vix_price": 15.5,
                "vix_regime": "low",
                "dollar_smile": "risk-on",
                "full_json": {"prices": {"HYG": 78.5}},
            },
            db=db_session,
        )
        db_session.commit()
        assert snap.id is not None
        assert snap.vix_regime == "low"

        latest = repo.get_latest_macro(db=db_session)
        assert latest is not None
        assert latest.vix_price == 15.5
        assert json.loads(latest.full_json) == {"prices": {"HYG": 78.5}}

    def test_get_latest_returns_newest(self, db_session):
        """get_latest_macro returns the most recent snapshot."""
        repo.save_macro_snapshot(
            {
                "vix_regime": "old",
                "generated_at": datetime(2026, 3, 20, tzinfo=timezone.utc),
            },
            db=db_session,
        )
        repo.save_macro_snapshot(
            {
                "vix_regime": "new",
                "generated_at": datetime(2026, 3, 25, tzinfo=timezone.utc),
            },
            db=db_session,
        )
        db_session.commit()

        latest = repo.get_latest_macro(db=db_session)
        assert latest.vix_regime == "new"

    def test_get_latest_empty(self, db_session):
        """get_latest_macro returns None when table is empty."""
        result = repo.get_latest_macro(db=db_session)
        assert result is None


# ===========================================================================
# AuditLog
# ===========================================================================

class TestAuditLog:

    def test_save_audit_log(self, db_session):
        """Save an audit log entry."""
        entry = repo.save_audit_log(
            event_type="test_event",
            details={"key": "value"},
            db=db_session,
        )
        db_session.commit()
        assert entry.id is not None
        assert entry.event_type == "test_event"
        assert json.loads(entry.details) == {"key": "value"}

    def test_save_audit_log_no_details(self, db_session):
        """Save audit log entry with no details."""
        entry = repo.save_audit_log(event_type="simple_event", db=db_session)
        db_session.commit()
        assert entry.details is None
