"""Integration tests for /health and /metrics endpoints."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from src.db import repository as repo


async def test_health_returns_200(app_client):
    """GET /health returns 200 with status ok."""
    r = await app_client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    await app_client.aclose()


async def test_health_has_version(app_client):
    """GET /health includes version 2.0.0."""
    r = await app_client.get("/health")
    body = r.json()
    assert body["version"] == "2.0.0"
    await app_client.aclose()


async def test_health_has_timestamp(app_client):
    """GET /health includes a timestamp in ISO format."""
    r = await app_client.get("/health")
    body = r.json()
    assert "timestamp" in body
    # Should parse as ISO datetime
    datetime.fromisoformat(body["timestamp"])
    await app_client.aclose()


async def test_health_last_run_null_empty_db(app_client):
    """GET /health returns last_run=null when DB has no signals."""
    r = await app_client.get("/health")
    body = r.json()
    assert body["last_run"] is None
    await app_client.aclose()


async def test_health_last_run_populated(app_client, db_session, seed_instrument):
    """GET /health returns last_run when signals exist."""
    now = datetime(2026, 3, 25, 12, 0, 0, tzinfo=timezone.utc)
    repo.save_signal(
        {
            "instrument": "EURUSD",
            "generated_at": now,
            "direction": "bull",
            "grade": "A",
            "score": 9,
            "timeframe_bias": "weekly",
        },
        db=db_session,
    )
    db_session.commit()

    r = await app_client.get("/health")
    body = r.json()
    assert body["last_run"] is not None
    assert "2026-03-25" in body["last_run"]
    await app_client.aclose()


async def test_metrics_returns_counts(app_client):
    """GET /metrics returns dict with signal/price/cot counts."""
    r = await app_client.get("/metrics")
    assert r.status_code == 200
    body = r.json()
    assert "signals" in body
    assert "prices_daily" in body
    assert "cot_positions" in body
    assert body["signals"] == 0
    assert body["prices_daily"] == 0
    assert body["cot_positions"] == 0
    await app_client.aclose()
