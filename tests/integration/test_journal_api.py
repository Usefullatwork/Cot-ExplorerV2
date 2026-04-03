"""Integration tests for the trade journal API endpoint."""

import json
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from src.api.app import create_app
from src.db.engine import get_engine, session_scope
from src.db.models import Base, TradeJournal


@pytest.fixture(scope="module")
def client():
    """Create test client with fresh DB."""
    app = create_app()
    # Ensure tables exist
    engine = get_engine()
    Base.metadata.create_all(engine)
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture(autouse=True)
def seed_journal():
    """Seed journal entries for tests."""
    gen = session_scope()
    session = next(gen)
    try:
        # Clear existing
        session.query(TradeJournal).delete()
        session.flush()

        # Add test entries
        entries = [
            TradeJournal(
                instrument="EURUSD", direction="bull", grade="A+", score=17,
                entry_reasoning=json.dumps({
                    "narrative": "EURUSD Long — A+ grade (17/19). Strengths: D1 trend above SMA200.",
                    "confidence": "very high",
                    "criteria_met": [{"label": "test", "passed": True, "narrative": "test pass"}],
                    "criteria_missed": [],
                }),
                gate_reasoning=json.dumps([
                    {"gate_name": "kill_switch", "passed": True, "reason": "Kill switch off", "detail": "Kill switch: OFF"},
                ]),
                outcome="win", pnl_pips=45.2, pnl_rr=2.1,
                created_at=datetime(2026, 4, 1, tzinfo=timezone.utc),
            ),
            TradeJournal(
                instrument="XAUUSD", direction="bear", grade="B", score=11,
                entry_reasoning=json.dumps({
                    "narrative": "XAUUSD Short — B grade (11/19).",
                    "confidence": "moderate",
                }),
                outcome="loss", pnl_pips=-22.5, pnl_rr=-1.0,
                created_at=datetime(2026, 4, 2, tzinfo=timezone.utc),
            ),
            TradeJournal(
                instrument="EURUSD", direction="bull", grade="A", score=14,
                outcome="pending",
                created_at=datetime(2026, 4, 3, tzinfo=timezone.utc),
            ),
        ]
        for e in entries:
            session.add(e)
        session.flush()
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

    yield

    # Cleanup
    gen2 = session_scope()
    session2 = next(gen2)
    try:
        session2.query(TradeJournal).delete()
        try:
            gen2.send(None)
        except StopIteration:
            pass
    except Exception:
        try:
            gen2.throw(Exception)
        except StopIteration:
            pass


class TestJournalAPI:
    """Test GET /api/v1/journal endpoint."""

    def test_list_all(self, client):
        resp = client.get("/api/v1/journal")
        assert resp.status_code == 200
        data = resp.json()
        assert "stats" in data
        assert "entries" in data
        assert data["stats"]["total"] == 3
        assert data["stats"]["wins"] == 1
        assert data["stats"]["losses"] == 1
        assert data["stats"]["pending"] == 1
        assert len(data["entries"]) == 3

    def test_filter_by_instrument(self, client):
        resp = client.get("/api/v1/journal?instrument=EURUSD")
        assert resp.status_code == 200
        entries = resp.json()["entries"]
        assert len(entries) == 2
        assert all(e["instrument"] == "EURUSD" for e in entries)

    def test_filter_by_outcome(self, client):
        resp = client.get("/api/v1/journal?outcome=win")
        assert resp.status_code == 200
        entries = resp.json()["entries"]
        assert len(entries) == 1
        assert entries[0]["outcome"] == "win"

    def test_entry_has_reasoning(self, client):
        resp = client.get("/api/v1/journal?outcome=win")
        assert resp.status_code == 200
        entry = resp.json()["entries"][0]
        assert entry["entry_reasoning"] is not None
        assert "narrative" in entry["entry_reasoning"]
        assert entry["gate_reasoning"] is not None
        assert isinstance(entry["gate_reasoning"], list)

    def test_entry_shape(self, client):
        resp = client.get("/api/v1/journal")
        assert resp.status_code == 200
        entry = resp.json()["entries"][0]
        required_keys = {
            "id", "created_at", "instrument", "direction", "grade",
            "score", "outcome", "pnl_pips", "pnl_rr",
        }
        assert required_keys.issubset(set(entry.keys()))

    def test_win_rate_calculation(self, client):
        resp = client.get("/api/v1/journal")
        assert resp.status_code == 200
        stats = resp.json()["stats"]
        # 1 win out of 2 closed (1 win + 1 loss) = 50%
        assert stats["win_rate"] == 50.0

    def test_limit_param(self, client):
        resp = client.get("/api/v1/journal?limit=1")
        assert resp.status_code == 200
        assert len(resp.json()["entries"]) == 1

    def test_entries_ordered_by_created_desc(self, client):
        resp = client.get("/api/v1/journal")
        entries = resp.json()["entries"]
        dates = [e["created_at"] for e in entries]
        assert dates == sorted(dates, reverse=True)
