"""Integration tests for /api/v1/backtests/wfo endpoints."""

from __future__ import annotations

import pytest


# ---------------------------------------------------------------------------
# /backtests/wfo/runs — list
# ---------------------------------------------------------------------------


async def test_wfo_list_runs_empty(app_client):
    """GET /api/v1/backtests/wfo/runs returns empty list when no runs exist."""
    r = await app_client.get("/api/v1/backtests/wfo/runs")
    assert r.status_code == 200
    body = r.json()
    assert isinstance(body, list)
    assert len(body) == 0
    await app_client.aclose()


async def test_wfo_list_runs_with_filter(app_client):
    """GET /api/v1/backtests/wfo/runs with instrument filter returns 200."""
    r = await app_client.get("/api/v1/backtests/wfo/runs?instrument=EURUSD")
    assert r.status_code == 200
    assert isinstance(r.json(), list)
    await app_client.aclose()


# ---------------------------------------------------------------------------
# /backtests/wfo/{run_id} — get by ID
# ---------------------------------------------------------------------------


async def test_wfo_get_run_not_found(app_client):
    """GET /api/v1/backtests/wfo/999 returns 404 for missing run."""
    r = await app_client.get("/api/v1/backtests/wfo/999")
    assert r.status_code == 404
    await app_client.aclose()


# ---------------------------------------------------------------------------
# /backtests/wfo/{run_id}/windows
# ---------------------------------------------------------------------------


async def test_wfo_windows_not_found(app_client):
    """GET /api/v1/backtests/wfo/999/windows returns 404 for missing run."""
    r = await app_client.get("/api/v1/backtests/wfo/999/windows")
    assert r.status_code == 404
    await app_client.aclose()


# ---------------------------------------------------------------------------
# /backtests/wfo/run — POST trigger
# ---------------------------------------------------------------------------


async def test_wfo_run_no_data(app_client):
    """POST /api/v1/backtests/wfo/run with no price data returns a run with 0 windows."""
    r = await app_client.post(
        "/api/v1/backtests/wfo/run",
        json={"instrument": "EURUSD"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["instrument"] == "EURUSD"
    assert body["status"] == "ok"
    assert body["total_windows"] == 0
    await app_client.aclose()


async def test_wfo_run_invalid_mode(app_client):
    """POST /api/v1/backtests/wfo/run with invalid window_mode returns 400."""
    r = await app_client.post(
        "/api/v1/backtests/wfo/run",
        json={"instrument": "EURUSD", "window_mode": "INVALID"},
    )
    assert r.status_code == 400
    await app_client.aclose()


async def test_wfo_run_response_structure(app_client):
    """POST /api/v1/backtests/wfo/run response has expected fields."""
    r = await app_client.post(
        "/api/v1/backtests/wfo/run",
        json={"instrument": "EURUSD"},
    )
    assert r.status_code == 200
    body = r.json()
    expected_keys = {
        "id", "instrument", "status", "started_at",
        "train_months", "test_months", "window_mode",
        "total_windows", "total_combinations",
    }
    assert expected_keys.issubset(set(body.keys()))
    await app_client.aclose()


async def test_wfo_run_then_list(app_client):
    """After triggering a WFO run, it appears in the runs list."""
    # Trigger run
    r1 = await app_client.post(
        "/api/v1/backtests/wfo/run",
        json={"instrument": "GBPUSD"},
    )
    assert r1.status_code == 200
    run_id = r1.json()["id"]

    # List runs
    r2 = await app_client.get("/api/v1/backtests/wfo/runs")
    assert r2.status_code == 200
    runs = r2.json()
    assert any(r["id"] == run_id for r in runs)
    await app_client.aclose()


async def test_wfo_run_then_get_by_id(app_client):
    """After triggering a WFO run, it can be retrieved by ID."""
    r1 = await app_client.post(
        "/api/v1/backtests/wfo/run",
        json={"instrument": "USDJPY"},
    )
    assert r1.status_code == 200
    run_id = r1.json()["id"]

    r2 = await app_client.get(f"/api/v1/backtests/wfo/{run_id}")
    assert r2.status_code == 200
    assert r2.json()["id"] == run_id
    assert r2.json()["instrument"] == "USDJPY"
    await app_client.aclose()
