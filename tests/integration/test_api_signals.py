"""Integration tests for /api/v1/signals endpoints."""

from __future__ import annotations

from datetime import datetime, timezone

from src.db import repository as repo

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_signal(instrument: str = "EURUSD", **overrides) -> dict:
    """Return a minimal valid signal dict."""
    base = {
        "instrument": instrument,
        "generated_at": datetime(2026, 3, 25, 10, 0, 0, tzinfo=timezone.utc),
        "direction": "bull",
        "grade": "A",
        "score": 9,
        "timeframe_bias": "weekly",
    }
    base.update(overrides)
    return base


def _seed_signals(session, seed_instrument):
    """Insert a variety of signals for filtering tests."""
    repo.save_signal(_make_signal(grade="A+", score=11, direction="bull"), db=session)
    repo.save_signal(
        _make_signal(
            grade="A",
            score=9,
            direction="bear",
            generated_at=datetime(2026, 3, 24, 10, 0, 0, tzinfo=timezone.utc),
        ),
        db=session,
    )
    repo.save_signal(
        _make_signal(
            grade="B",
            score=6,
            direction="bull",
            generated_at=datetime(2026, 3, 23, 10, 0, 0, tzinfo=timezone.utc),
        ),
        db=session,
    )
    repo.save_signal(
        _make_signal(
            grade="C",
            score=3,
            direction="bear",
            generated_at=datetime(2026, 3, 22, 10, 0, 0, tzinfo=timezone.utc),
        ),
        db=session,
    )
    session.commit()


# ---------------------------------------------------------------------------
# Tests — empty DB
# ---------------------------------------------------------------------------


async def test_list_signals_empty(app_client):
    """GET /api/v1/signals on empty DB returns empty list."""
    r = await app_client.get("/api/v1/signals")
    assert r.status_code == 200
    assert r.json() == []
    await app_client.aclose()


# ---------------------------------------------------------------------------
# Tests — with seeded data
# ---------------------------------------------------------------------------


async def test_list_signals_returns_all(app_client, db_session, seed_instrument):
    """All seeded signals appear in unfiltered listing."""
    _seed_signals(db_session, seed_instrument)
    r = await app_client.get("/api/v1/signals")
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 4
    await app_client.aclose()


async def test_filter_by_grade(app_client, db_session, seed_instrument):
    """Filter signals by grade=A+."""
    _seed_signals(db_session, seed_instrument)
    r = await app_client.get("/api/v1/signals", params={"grade": "A+"})
    data = r.json()
    assert len(data) == 1
    assert data[0]["grade"] == "A+"
    await app_client.aclose()


async def test_filter_by_min_score(app_client, db_session, seed_instrument):
    """Filter signals with min_score=9 returns only high-scoring."""
    _seed_signals(db_session, seed_instrument)
    r = await app_client.get("/api/v1/signals", params={"min_score": 9})
    data = r.json()
    assert all(s["score"] >= 9 for s in data)
    assert len(data) == 2  # A+ (11) and A (9)
    await app_client.aclose()


async def test_filter_by_instrument(app_client, db_session, seed_instrument):
    """Filter by instrument=EURUSD."""
    _seed_signals(db_session, seed_instrument)
    r = await app_client.get("/api/v1/signals", params={"instrument": "EURUSD"})
    data = r.json()
    assert len(data) == 4
    assert all(s["instrument"] == "EURUSD" for s in data)
    await app_client.aclose()


async def test_filter_by_direction(app_client, db_session, seed_instrument):
    """Filter by direction=bear."""
    _seed_signals(db_session, seed_instrument)
    r = await app_client.get("/api/v1/signals", params={"direction": "bear"})
    data = r.json()
    assert all(s["direction"] == "bear" for s in data)
    assert len(data) == 2
    await app_client.aclose()


async def test_filter_by_limit(app_client, db_session, seed_instrument):
    """Limit query parameter caps result count."""
    _seed_signals(db_session, seed_instrument)
    r = await app_client.get("/api/v1/signals", params={"limit": 2})
    data = r.json()
    assert len(data) == 2
    await app_client.aclose()


async def test_signal_detail_found(app_client, db_session, seed_instrument):
    """GET /api/v1/signals/EURUSD returns latest signal for that instrument."""
    _seed_signals(db_session, seed_instrument)
    r = await app_client.get("/api/v1/signals/EURUSD")
    assert r.status_code == 200
    body = r.json()
    assert body["instrument"] == "EURUSD"
    # Latest by generated_at is the A+ signal
    assert body["grade"] == "A+"
    await app_client.aclose()


async def test_signal_detail_not_found(app_client):
    """GET /api/v1/signals/NOPE returns 404."""
    r = await app_client.get("/api/v1/signals/NOPE")
    assert r.status_code == 404
    await app_client.aclose()


async def test_signal_response_shape(app_client, db_session, seed_instrument):
    """Verify that signal dict has all expected keys."""
    repo.save_signal(
        _make_signal(
            entry_price=1.08,
            stop_loss=1.075,
            target_1=1.09,
            target_2=1.10,
            score_details={"cot": 2, "smc": 3},
            metadata={"note": "test"},
        ),
        db=db_session,
    )
    db_session.commit()

    r = await app_client.get("/api/v1/signals/EURUSD")
    body = r.json()
    expected_keys = {
        "id",
        "instrument",
        "generated_at",
        "direction",
        "grade",
        "score",
        "timeframe_bias",
        "entry_price",
        "stop_loss",
        "target_1",
        "target_2",
        "rr_t1",
        "rr_t2",
        "entry_weight",
        "t1_weight",
        "sl_type",
        "at_level_now",
        "vix_regime",
        "pos_size",
        "score_details",
        "metadata",
    }
    assert expected_keys == set(body.keys())
    assert body["score_details"] == {"cot": 2, "smc": 3}
    assert body["metadata"] == {"note": "test"}
    await app_client.aclose()
