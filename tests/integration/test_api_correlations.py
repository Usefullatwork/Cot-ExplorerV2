"""Integration tests for /api/v1/correlations endpoint."""

from __future__ import annotations

import pytest


# ---------------------------------------------------------------------------
# /correlations
# ---------------------------------------------------------------------------


async def test_correlations_returns_200(app_client):
    """GET /api/v1/correlations returns 200."""
    r = await app_client.get("/api/v1/correlations")
    assert r.status_code == 200
    await app_client.aclose()


async def test_correlations_empty_is_list(app_client):
    """GET /api/v1/correlations returns an empty list when DB has no snapshots."""
    r = await app_client.get("/api/v1/correlations")
    assert r.status_code == 200
    body = r.json()
    assert isinstance(body, list)
    assert len(body) == 0
    await app_client.aclose()


async def test_correlations_accepts_window_param(app_client):
    """GET /api/v1/correlations?window=20 returns 200 with list."""
    r = await app_client.get("/api/v1/correlations", params={"window": 20})
    assert r.status_code == 200
    assert isinstance(r.json(), list)
    await app_client.aclose()


async def test_correlations_accepts_limit_param(app_client):
    """GET /api/v1/correlations?limit=10 returns 200 with list."""
    r = await app_client.get("/api/v1/correlations", params={"limit": 10})
    assert r.status_code == 200
    assert isinstance(r.json(), list)
    await app_client.aclose()


async def test_correlations_rejects_invalid_window(app_client):
    """GET /api/v1/correlations?window=1 returns 422 (below ge=5)."""
    r = await app_client.get("/api/v1/correlations", params={"window": 1})
    assert r.status_code == 422
    await app_client.aclose()
