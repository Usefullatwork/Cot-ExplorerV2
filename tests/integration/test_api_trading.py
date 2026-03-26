"""Integration tests for /api/v1/trading endpoints and /api/v1/webhook/tv-alert."""

from __future__ import annotations

from src.db import repository as repo


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _auth_header():
    return {"X-API-Key": "test-secret-key"}


# ---------------------------------------------------------------------------
# Auth tests (require app_client_with_auth)
# ---------------------------------------------------------------------------


async def test_get_status_no_auth(app_client_with_auth):
    """GET /api/v1/trading/status without API key returns 401."""
    r = await app_client_with_auth.get("/api/v1/trading/status")
    assert r.status_code == 401
    await app_client_with_auth.aclose()


async def test_get_status_with_auth(app_client_with_auth):
    """GET /api/v1/trading/status with valid key returns 200."""
    r = await app_client_with_auth.get(
        "/api/v1/trading/status", headers=_auth_header()
    )
    assert r.status_code == 200
    body = r.json()
    assert "active" in body
    assert "kill_switch_active" in body
    assert "open_positions" in body
    await app_client_with_auth.aclose()


# ---------------------------------------------------------------------------
# Public mode tests (app_client, no auth required)
# ---------------------------------------------------------------------------


async def test_get_positions_empty(app_client):
    """GET /api/v1/trading/positions on empty DB returns empty list."""
    r = await app_client.get("/api/v1/trading/positions")
    assert r.status_code == 200
    assert r.json() == []
    await app_client.aclose()


async def test_get_signals_empty(app_client):
    """GET /api/v1/trading/signals on empty DB returns empty list."""
    r = await app_client.get("/api/v1/trading/signals")
    assert r.status_code == 200
    assert r.json() == []
    await app_client.aclose()


async def test_get_history_empty(app_client):
    """GET /api/v1/trading/history on empty DB returns empty list."""
    r = await app_client.get("/api/v1/trading/history")
    assert r.status_code == 200
    assert r.json() == []
    await app_client.aclose()


# ---------------------------------------------------------------------------
# TV alert webhook
# ---------------------------------------------------------------------------


async def test_post_tv_alert_valid(app_client, seed_instrument):
    """POST /api/v1/webhook/tv-alert with valid payload creates signal."""
    payload = {
        "instrument": "EURUSD",
        "direction": "bull",
        "score": 9,
        "grade": "A",
        "entry": 1.1000,
        "sl": 1.0950,
        "t1": 1.1050,
    }
    r = await app_client.post("/api/v1/webhook/tv-alert", json=payload)
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert "signal_id" in body
    assert isinstance(body["signal_id"], int)
    await app_client.aclose()


async def test_post_tv_alert_invalid_direction(app_client, seed_instrument):
    """POST /api/v1/webhook/tv-alert with invalid direction returns 400."""
    payload = {
        "instrument": "EURUSD",
        "direction": "sideways",
        "score": 9,
        "grade": "A",
        "entry": 1.1000,
        "sl": 1.0950,
        "t1": 1.1050,
    }
    r = await app_client.post("/api/v1/webhook/tv-alert", json=payload)
    assert r.status_code == 400
    await app_client.aclose()


async def test_post_tv_alert_missing_fields(app_client):
    """POST /api/v1/webhook/tv-alert with missing required fields returns 422."""
    payload = {"instrument": "EURUSD"}  # missing direction, score, grade, entry, sl, t1
    r = await app_client.post("/api/v1/webhook/tv-alert", json=payload)
    assert r.status_code == 422
    await app_client.aclose()


# ---------------------------------------------------------------------------
# Kill switch (invalidate)
# ---------------------------------------------------------------------------


async def test_post_invalidate(app_client):
    """POST /api/v1/trading/invalidate activates kill switch."""
    r = await app_client.post(
        "/api/v1/trading/invalidate",
        json={"reason": "emergency stop"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert "Kill switch activated" in body["message"]
    await app_client.aclose()


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------


async def test_get_config(app_client):
    """GET /api/v1/trading/config returns default configuration."""
    r = await app_client.get("/api/v1/trading/config")
    assert r.status_code == 200
    body = r.json()
    assert "active" in body
    assert "broker_mode" in body
    assert "max_positions" in body
    assert "risk_pct" in body
    await app_client.aclose()


async def test_post_config_update(app_client):
    """POST /api/v1/trading/config updates configuration fields."""
    r = await app_client.post(
        "/api/v1/trading/config",
        json={"max_positions": 5, "risk_pct": 0.02},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["max_positions"] == 5
    assert body["risk_pct"] == 0.02
    await app_client.aclose()


async def test_post_config_invalid_broker_mode(app_client):
    """POST /api/v1/trading/config with invalid broker_mode returns 400."""
    r = await app_client.post(
        "/api/v1/trading/config",
        json={"broker_mode": "turbo"},
    )
    assert r.status_code == 400
    await app_client.aclose()


# ---------------------------------------------------------------------------
# Start / Stop
# ---------------------------------------------------------------------------


async def test_post_start(app_client):
    """POST /api/v1/trading/start sets active=True."""
    r = await app_client.post("/api/v1/trading/start")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert "started" in body["message"].lower()
    await app_client.aclose()


async def test_post_stop(app_client):
    """POST /api/v1/trading/stop sets active=False."""
    r = await app_client.post("/api/v1/trading/stop")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert "stopped" in body["message"].lower()
    await app_client.aclose()
