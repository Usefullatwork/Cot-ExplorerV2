"""Integration tests for /api/v1/webhook/push-alert endpoint."""

from __future__ import annotations


async def test_push_alert_valid(app_client):
    """POST /api/v1/webhook/push-alert with signals returns ok."""
    payload = {
        "signals": [
            {"instrument": "EURUSD", "direction": "bull", "score": 9},
            {"instrument": "USDJPY", "direction": "bear", "score": 7},
        ],
        "generated": "2026-03-25T12:00:00Z",
    }
    r = await app_client.post("/api/v1/webhook/push-alert", json=payload)
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["received"] == 2
    await app_client.aclose()


async def test_push_alert_empty_signals(app_client):
    """POST with empty signals list returns received=0."""
    payload = {"signals": [], "generated": "2026-03-25T12:00:00Z"}
    r = await app_client.post("/api/v1/webhook/push-alert", json=payload)
    assert r.status_code == 200
    body = r.json()
    assert body["received"] == 0
    await app_client.aclose()


async def test_push_alert_no_signals_key(app_client):
    """POST with missing signals key defaults to received=0."""
    r = await app_client.post("/api/v1/webhook/push-alert", json={"generated": "now"})
    assert r.status_code == 200
    body = r.json()
    assert body["received"] == 0
    await app_client.aclose()


async def test_push_alert_writes_audit_log(app_client, db_session):
    """Verify push-alert writes an audit log entry."""
    from sqlalchemy import select

    from src.db.models import AuditLog

    payload = {
        "signals": [{"instrument": "EURUSD"}],
        "generated": "2026-03-25",
    }
    r = await app_client.post("/api/v1/webhook/push-alert", json=payload)
    assert r.status_code == 200

    # Check audit log in DB
    rows = db_session.execute(select(AuditLog).where(AuditLog.event_type == "push_alert_received")).scalars().all()
    assert len(rows) >= 1
    await app_client.aclose()
