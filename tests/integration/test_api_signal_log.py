"""Integration tests for /api/v1/signal-log endpoints."""

from __future__ import annotations


async def test_signal_log_returns_200(app_client):
    """GET /api/v1/signal-log returns 200 with stats + history shape."""
    r = await app_client.get("/api/v1/signal-log")
    assert r.status_code == 200
    body = r.json()
    assert "stats" in body
    assert "history" in body
    assert isinstance(body["history"], list)
    await app_client.aclose()


async def test_signal_log_stats_shape(app_client):
    """Stats response has total, hits, misses, pending, neutral, hit_rate, avg_pnl_pips."""
    r = await app_client.get("/api/v1/signal-log")
    body = r.json()
    stats = body["stats"]
    assert "total" in stats
    assert "hits" in stats
    assert "misses" in stats
    assert "pending" in stats
    assert "neutral" in stats
    assert "hit_rate" in stats
    assert "avg_pnl_pips" in stats
    await app_client.aclose()


async def test_signal_log_empty_db(app_client):
    """Signal log returns zero counts when DB is empty."""
    r = await app_client.get("/api/v1/signal-log")
    body = r.json()
    stats = body["stats"]
    assert stats["total"] == 0
    assert stats["hits"] == 0
    assert stats["misses"] == 0
    assert stats["pending"] == 0
    assert stats["neutral"] == 0
    assert stats["hit_rate"] is None
    assert stats["avg_pnl_pips"] is None
    assert body["history"] == []
    await app_client.aclose()


async def test_signal_log_filter_instrument(app_client):
    """Filtering by instrument returns 200 (empty when no matching records)."""
    r = await app_client.get("/api/v1/signal-log?instrument=EURUSD")
    assert r.status_code == 200
    body = r.json()
    assert isinstance(body["history"], list)
    await app_client.aclose()


async def test_signal_log_filter_result(app_client):
    """Filtering by result=HIT returns 200."""
    r = await app_client.get("/api/v1/signal-log?result=HIT")
    assert r.status_code == 200
    body = r.json()
    assert isinstance(body["history"], list)
    await app_client.aclose()


async def test_signal_log_limit_param(app_client):
    """Limit param is accepted and returns 200."""
    r = await app_client.get("/api/v1/signal-log?limit=10")
    assert r.status_code == 200
    body = r.json()
    assert isinstance(body["history"], list)
    await app_client.aclose()


async def test_signal_log_combined_filters(app_client):
    """Multiple query params together return 200."""
    r = await app_client.get("/api/v1/signal-log?instrument=EURUSD&result=HIT&limit=10")
    assert r.status_code == 200
    body = r.json()
    assert isinstance(body["history"], list)
    await app_client.aclose()


async def test_analytics_returns_200(app_client):
    """GET /api/v1/signal-log/analytics returns 200 with expected shape."""
    r = await app_client.get("/api/v1/signal-log/analytics")
    assert r.status_code == 200
    body = r.json()
    assert "by_instrument" in body
    assert "by_grade" in body
    assert "streak" in body
    assert "total_signals" in body
    assert "total_closed" in body
    await app_client.aclose()


async def test_analytics_streak_shape(app_client):
    """Analytics streak has longest_win, longest_loss, current_streak, current_type."""
    r = await app_client.get("/api/v1/signal-log/analytics")
    body = r.json()
    streak = body["streak"]
    assert "longest_win" in streak
    assert "longest_loss" in streak
    assert "current_streak" in streak
    assert "current_type" in streak
    await app_client.aclose()


async def test_analytics_empty_db(app_client):
    """Analytics returns zero counts when DB is empty."""
    r = await app_client.get("/api/v1/signal-log/analytics")
    body = r.json()
    assert body["total_signals"] == 0
    assert body["total_closed"] == 0
    assert body["by_instrument"] == []
    assert body["by_grade"] == []
    assert body["streak"]["longest_win"] == 0
    assert body["streak"]["longest_loss"] == 0
    assert body["streak"]["current_streak"] == 0
    assert body["streak"]["current_type"] == "none"
    await app_client.aclose()
