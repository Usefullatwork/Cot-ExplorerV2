"""Integration tests for API key authentication middleware."""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Public mode (SCALP_API_KEY="")
# ---------------------------------------------------------------------------


async def test_public_mode_signals(app_client):
    """In public mode, /api/v1/signals is accessible without key."""
    r = await app_client.get("/api/v1/signals")
    assert r.status_code == 200
    await app_client.aclose()


async def test_public_mode_health(app_client):
    """In public mode, /health is accessible."""
    r = await app_client.get("/health")
    assert r.status_code == 200
    await app_client.aclose()


# ---------------------------------------------------------------------------
# Auth mode (SCALP_API_KEY="test-secret-key")
# ---------------------------------------------------------------------------


async def test_auth_rejects_no_key(app_client_with_auth):
    """/api/v1/* returns 401 without X-API-Key header."""
    r = await app_client_with_auth.get("/api/v1/signals")
    assert r.status_code == 401
    body = r.json()
    assert "Invalid or missing API key" in body["detail"]
    await app_client_with_auth.aclose()


async def test_auth_accepts_valid_key(app_client_with_auth):
    """/api/v1/* returns 200 with correct X-API-Key."""
    r = await app_client_with_auth.get(
        "/api/v1/signals",
        headers={"X-API-Key": "test-secret-key"},
    )
    assert r.status_code == 200
    await app_client_with_auth.aclose()


async def test_auth_health_no_key_required(app_client_with_auth):
    """/health is accessible even when auth is enabled (not under /api/v1/)."""
    r = await app_client_with_auth.get("/health")
    assert r.status_code == 200
    await app_client_with_auth.aclose()
