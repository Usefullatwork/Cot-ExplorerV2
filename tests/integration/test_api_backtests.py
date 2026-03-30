"""Integration tests for /api/v1/backtests endpoints."""

from __future__ import annotations

import pytest


# ---------------------------------------------------------------------------
# /backtests/summary
# ---------------------------------------------------------------------------


async def test_backtests_summary_no_data(app_client):
    """GET /api/v1/backtests/summary returns zero-trade summary when DB is empty."""
    r = await app_client.get("/api/v1/backtests/summary")
    assert r.status_code == 200
    body = r.json()
    assert body["total_trades"] == 0
    assert "message" in body
    await app_client.aclose()


async def test_backtests_summary_is_dict(app_client):
    """GET /api/v1/backtests/summary response is a dict."""
    r = await app_client.get("/api/v1/backtests/summary")
    assert r.status_code == 200
    assert isinstance(r.json(), dict)
    await app_client.aclose()


# ---------------------------------------------------------------------------
# /backtests/stats
# ---------------------------------------------------------------------------


async def test_backtests_stats_empty(app_client):
    """GET /api/v1/backtests/stats returns zeroed stats when DB is empty."""
    r = await app_client.get("/api/v1/backtests/stats")
    assert r.status_code == 200
    body = r.json()
    assert body["total_trades"] == 0
    assert body["wins"] == 0
    assert body["losses"] == 0
    assert body["win_rate"] == 0.0
    assert body["equity_curve"] == []
    assert body["by_instrument"] == []
    assert body["by_grade"] == []
    await app_client.aclose()


async def test_backtests_stats_has_all_fields(app_client):
    """GET /api/v1/backtests/stats response contains all expected metric fields."""
    r = await app_client.get("/api/v1/backtests/stats")
    assert r.status_code == 200
    body = r.json()
    expected_keys = {
        "total_trades", "wins", "losses", "win_rate",
        "avg_win_rr", "avg_loss_rr", "profit_factor",
        "max_drawdown_rr", "avg_rr", "best_trade_rr",
        "worst_trade_rr", "avg_duration_hours",
        "equity_curve", "by_instrument", "by_grade",
    }
    assert expected_keys.issubset(set(body.keys()))
    await app_client.aclose()


# ---------------------------------------------------------------------------
# /backtests/trades
# ---------------------------------------------------------------------------


async def test_backtests_trades_empty(app_client):
    """GET /api/v1/backtests/trades returns empty list when DB is empty."""
    r = await app_client.get("/api/v1/backtests/trades")
    assert r.status_code == 200
    body = r.json()
    assert isinstance(body, list)
    assert len(body) == 0
    await app_client.aclose()


async def test_backtests_trades_accepts_limit(app_client):
    """GET /api/v1/backtests/trades respects the limit query param."""
    r = await app_client.get("/api/v1/backtests/trades", params={"limit": 10})
    assert r.status_code == 200
    assert isinstance(r.json(), list)
    await app_client.aclose()


async def test_backtests_trades_rejects_invalid_instrument(app_client):
    """GET /api/v1/backtests/trades returns 400 for invalid instrument."""
    r = await app_client.get(
        "/api/v1/backtests/trades",
        params={"instrument": "DROP;TABLE"},
    )
    assert r.status_code == 400
    await app_client.aclose()
