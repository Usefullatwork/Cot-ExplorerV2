"""Unit tests for src.analysis.signal_tracker — signal performance tracking."""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from src.db.models import Base, SignalPerformance
from src.analysis.signal_tracker import (
    _VALID_RESULTS,
    get_stats,
    record_signal,
    update_result,
)


# ---------------------------------------------------------------------------
# Fixtures: in-memory SQLite database
# ---------------------------------------------------------------------------


@pytest.fixture
def db_session():
    """Create an in-memory SQLite session with the SignalPerformance table."""
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)
    Session_ = sessionmaker(bind=engine)
    session = Session_()
    yield session
    session.close()
    engine.dispose()


# ===== record_signal =======================================================


class TestRecordSignal:
    """Recording new signals."""

    def test_creates_entry(self, db_session):
        """record_signal creates a new row and returns a dict."""
        result = record_signal(
            signal_id=101,
            instrument="EURUSD",
            direction="LONG",
            grade="A+",
            score=14,
            entry_price=1.08500,
            db=db_session,
        )
        assert result["signal_id"] == 101
        assert result["instrument"] == "EURUSD"
        assert result["direction"] == "LONG"
        assert result["grade"] == "A+"
        assert result["score"] == 14
        assert result["entry_price"] == 1.08500
        assert result["result"] == "PENDING"

    def test_creates_entry_with_all_fields(self, db_session):
        """Returned dict has all expected keys."""
        result = record_signal(
            signal_id=102, instrument="XAUUSD", direction="SHORT",
            grade="B", score=10, entry_price=2050.0, db=db_session,
        )
        expected_keys = {
            "id", "signal_id", "instrument", "direction", "grade",
            "score", "entry_price", "result", "pnl_pips", "created_at", "closed_at",
        }
        assert expected_keys == set(result.keys())


# ===== update_result =======================================================


class TestUpdateResult:
    """Updating signal results."""

    def test_updates_result_to_hit(self, db_session):
        """update_result changes result from PENDING to HIT."""
        record_signal(
            signal_id=201, instrument="GBPUSD", direction="LONG",
            grade="A", score=12, entry_price=1.26000, db=db_session,
        )
        updated = update_result(signal_id=201, result="HIT", pnl_pips=25.0, db=db_session)
        assert updated["result"] == "HIT"
        assert updated["pnl_pips"] == 25.0
        assert updated["closed_at"] is not None

    def test_updates_result_to_miss(self, db_session):
        """update_result changes result to MISS."""
        record_signal(
            signal_id=202, instrument="USDJPY", direction="SHORT",
            grade="B", score=9, entry_price=150.50, db=db_session,
        )
        updated = update_result(signal_id=202, result="MISS", pnl_pips=-30.0, db=db_session)
        assert updated["result"] == "MISS"

    def test_invalid_result_raises(self, db_session):
        """Invalid result string raises ValueError."""
        record_signal(
            signal_id=203, instrument="AUDUSD", direction="LONG",
            grade="C", score=5, entry_price=0.6550, db=db_session,
        )
        with pytest.raises(ValueError, match="Invalid result"):
            update_result(signal_id=203, result="INVALID", db=db_session)

    def test_nonexistent_signal_raises(self, db_session):
        """Updating a non-existent signal_id raises ValueError."""
        with pytest.raises(ValueError, match="not found"):
            update_result(signal_id=999, result="HIT", db=db_session)


# ===== get_stats ===========================================================


class TestGetStats:
    """Aggregate signal performance statistics."""

    def test_stats_with_mixed_results(self, db_session):
        """Stats correctly count resolved signals and compute hit rate."""
        # Create 4 signals: 2 HIT, 1 MISS, 1 PENDING
        for i, (result, grade) in enumerate([
            ("HIT", "A+"), ("HIT", "A"), ("MISS", "B"), ("PENDING", "C"),
        ]):
            record_signal(
                signal_id=300 + i, instrument="EURUSD", direction="LONG",
                grade=grade, score=10, entry_price=1.0, db=db_session,
            )
            if result != "PENDING":
                update_result(signal_id=300 + i, result=result, db=db_session)

        stats = get_stats(db=db_session)
        assert stats["total_signals"] == 3  # only resolved (HIT, MISS, NEUTRAL)
        # 2 HIT out of 3 resolved = 0.6667
        assert abs(stats["overall_hit_rate"] - 0.6667) < 0.001

    def test_stats_with_no_signals(self, db_session):
        """Empty table returns zero stats."""
        stats = get_stats(db=db_session)
        assert stats["total_signals"] == 0
        assert stats["overall_hit_rate"] == 0.0
        for grade_stats in stats["per_grade_stats"].values():
            assert grade_stats["count"] == 0
            assert grade_stats["hit_rate"] == 0.0

    def test_per_grade_breakdown(self, db_session):
        """Per-grade stats track individual grade performance."""
        # 2 A+ signals: 1 HIT, 1 MISS
        record_signal(signal_id=400, instrument="EURUSD", direction="LONG",
                      grade="A+", score=16, entry_price=1.0, db=db_session)
        update_result(signal_id=400, result="HIT", db=db_session)

        record_signal(signal_id=401, instrument="GBPUSD", direction="SHORT",
                      grade="A+", score=15, entry_price=1.0, db=db_session)
        update_result(signal_id=401, result="MISS", db=db_session)

        stats = get_stats(db=db_session)
        aplus = stats["per_grade_stats"]["A+"]
        assert aplus["count"] == 2
        assert abs(aplus["hit_rate"] - 0.5) < 0.001

    def test_hit_rate_calculation_accuracy(self, db_session):
        """Hit rate is accurate for edge cases: all HIT."""
        for i in range(5):
            record_signal(signal_id=500 + i, instrument="XAUUSD", direction="LONG",
                          grade="A", score=14, entry_price=2000.0, db=db_session)
            update_result(signal_id=500 + i, result="HIT", db=db_session)

        stats = get_stats(db=db_session)
        assert stats["total_signals"] == 5
        assert stats["overall_hit_rate"] == 1.0
