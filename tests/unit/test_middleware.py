"""Unit tests for API middleware: auth, rate_limit, and cache."""

from __future__ import annotations

import logging
import os
import time
from unittest.mock import patch

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

import src.api.middleware.auth as auth_module
from src.api.middleware.auth import APIKeyMiddleware
from src.api.middleware.cache import TTLCache
from src.api.middleware.rate_limit import RateLimitMiddleware

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_app(
    *,
    auth: bool = False,
    api_key: str = "test-key",
    rate_limit: bool = False,
    max_requests: int = 5,
    trust_proxy: bool | None = None,
) -> FastAPI:
    """Build a minimal FastAPI app with selected middleware and test routes."""
    app = FastAPI()

    if rate_limit:
        kwargs: dict = {"max_requests": max_requests}
        if trust_proxy is not None:
            kwargs["trust_proxy"] = trust_proxy
        app.add_middleware(RateLimitMiddleware, **kwargs)
    if auth:
        app.add_middleware(APIKeyMiddleware)

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    @app.get("/api/v1/data")
    async def data():
        return {"value": 42}

    # Patch the env var so the auth middleware sees it
    if auth:
        os.environ["SCALP_API_KEY"] = api_key
    else:
        os.environ.pop("SCALP_API_KEY", None)

    return app


def _client(app: FastAPI) -> AsyncClient:
    """Create an httpx async client wired to the given ASGI app."""
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


# =========================================================================
# Auth middleware
# =========================================================================


async def test_auth_valid_key():
    """Request with the correct API key returns 200."""
    app = _make_app(auth=True, api_key="secret-123")
    async with _client(app) as c:
        resp = await c.get("/api/v1/data", headers={"X-API-Key": "secret-123"})
        assert resp.status_code == 200
        assert resp.json() == {"value": 42}


async def test_auth_missing_key():
    """Request without any API key returns 401."""
    app = _make_app(auth=True, api_key="secret-123")
    async with _client(app) as c:
        resp = await c.get("/api/v1/data")
        assert resp.status_code == 401
        assert "Invalid or missing" in resp.json()["detail"]


async def test_auth_invalid_key():
    """Request with the wrong API key returns 401."""
    app = _make_app(auth=True, api_key="secret-123")
    async with _client(app) as c:
        resp = await c.get("/api/v1/data", headers={"X-API-Key": "wrong-key"})
        assert resp.status_code == 401


async def test_auth_health_exempt():
    """/health is outside /api/v1/* so it bypasses auth even when enabled."""
    app = _make_app(auth=True, api_key="secret-123")
    async with _client(app) as c:
        resp = await c.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"


async def test_auth_public_mode():
    """When SCALP_API_KEY is empty, all routes are accessible without a key."""
    app = _make_app(auth=False)
    async with _client(app) as c:
        resp = await c.get("/api/v1/data")
        assert resp.status_code == 200


# =========================================================================
# Rate limit middleware
# =========================================================================


async def test_rate_limit_under_threshold():
    """Requests under the limit all return 200."""
    app = _make_app(rate_limit=True, max_requests=5)
    async with _client(app) as c:
        for _ in range(5):
            resp = await c.get("/health")
            assert resp.status_code == 200


async def test_rate_limit_over_threshold():
    """Requests exceeding the per-IP limit return 429."""
    app = _make_app(rate_limit=True, max_requests=3)
    async with _client(app) as c:
        for _ in range(3):
            resp = await c.get("/health")
            assert resp.status_code == 200

        resp = await c.get("/health")
        assert resp.status_code == 429
        assert "Rate limit exceeded" in resp.json()["detail"]


async def test_rate_limit_reset():
    """After the 60-second window expires, requests are allowed again."""
    app = _make_app(rate_limit=True, max_requests=2)
    async with _client(app) as c:
        # Exhaust the limit
        for _ in range(2):
            await c.get("/health")

        resp = await c.get("/health")
        assert resp.status_code == 429

        # Simulate time passing beyond the 60s window by manipulating
        # the internal _hits timestamps on the middleware instance.
        for mw in app.user_middleware:
            pass  # middleware is already mounted, access via app internals

        # Walk the middleware stack to find RateLimitMiddleware
        found = None
        node = app.middleware_stack
        while node is not None:
            if isinstance(node, RateLimitMiddleware):
                found = node
                break
            node = getattr(node, "app", None)

        assert found is not None, "RateLimitMiddleware not found in stack"

        # Shift all recorded timestamps back by 61 seconds
        for ip in found._hits:
            found._hits[ip] = [t - 61 for t in found._hits[ip]]

        resp = await c.get("/health")
        assert resp.status_code == 200


async def test_rate_limit_different_ips():
    """Different client IPs have independent rate-limit buckets."""
    app = _make_app(rate_limit=True, max_requests=2, trust_proxy=True)
    async with _client(app) as c:
        # Exhaust the limit for IP "1.2.3.4"
        for _ in range(2):
            await c.get("/health", headers={"X-Forwarded-For": "1.2.3.4"})

        resp = await c.get("/health", headers={"X-Forwarded-For": "1.2.3.4"})
        assert resp.status_code == 429

        # A different IP should still be allowed
        resp = await c.get("/health", headers={"X-Forwarded-For": "5.6.7.8"})
        assert resp.status_code == 200


# =========================================================================
# TTLCache (not ASGI middleware, but a shared utility used by route handlers)
# =========================================================================


def test_cache_miss():
    """Getting a key that was never set returns None."""
    cache = TTLCache(default_ttl=60)
    assert cache.get("missing") is None


def test_cache_hit():
    """A stored value is returned before its TTL expires."""
    cache = TTLCache(default_ttl=60)
    cache.set("key1", {"data": "hello"})
    assert cache.get("key1") == {"data": "hello"}


def test_cache_different_paths():
    """Different keys are stored independently."""
    cache = TTLCache(default_ttl=60)
    cache.set("/api/a", "result-a")
    cache.set("/api/b", "result-b")
    assert cache.get("/api/a") == "result-a"
    assert cache.get("/api/b") == "result-b"


def test_cache_expiry():
    """Expired entries return None and are evicted."""
    cache = TTLCache(default_ttl=1)
    cache.set("ephemeral", "value", ttl=0)
    # TTL=0 means it expires at time.monotonic() + 0, which is already past
    # by the time we call get (monotonic advances).
    # Use a tiny TTL and mock time to be precise.
    with patch("src.api.middleware.cache.time") as mock_time:
        now = time.monotonic()
        mock_time.monotonic.return_value = now
        cache._store["ephemeral"] = (now + 1, "value")

        # Before expiry
        assert cache.get("ephemeral") == "value"

        # After expiry
        mock_time.monotonic.return_value = now + 2
        assert cache.get("ephemeral") is None
        assert len(cache._store) == 0


def test_cache_invalidate():
    """Explicitly invalidating a key removes it."""
    cache = TTLCache(default_ttl=60)
    cache.set("x", 1)
    cache.invalidate("x")
    assert cache.get("x") is None


def test_cache_clear():
    """Clearing the cache removes all entries."""
    cache = TTLCache(default_ttl=60)
    cache.set("a", 1)
    cache.set("b", 2)
    assert len(cache) == 2
    cache.clear()
    assert len(cache) == 0


# =========================================================================
# Security hardening — Auth public-mode warning
# =========================================================================


async def test_auth_public_mode_logs_warning(caplog):
    """When SCALP_API_KEY is not set, a warning is logged (once)."""
    # Reset the module-level flag so the warning fires in this test
    auth_module._warned_public_mode = False
    # Build app WITH auth middleware but WITHOUT an API key in the env
    app = FastAPI()
    app.add_middleware(APIKeyMiddleware)

    @app.get("/api/v1/data")
    async def _data():
        return {"value": 42}

    os.environ.pop("SCALP_API_KEY", None)

    with caplog.at_level(logging.WARNING, logger="src.api.middleware.auth"):
        async with _client(app) as c:
            resp = await c.get("/api/v1/data")
            assert resp.status_code == 200
    assert any("PUBLIC mode" in msg for msg in caplog.messages)
    # Restore flag
    auth_module._warned_public_mode = False


# =========================================================================
# Security hardening — Rate limiter proxy trust
# =========================================================================


async def test_rate_limit_ignores_xff_by_default():
    """Without trust_proxy, X-Forwarded-For header is ignored."""
    app = _make_app(rate_limit=True, max_requests=2, trust_proxy=False)
    async with _client(app) as c:
        # Send 2 requests with XFF header — should use real client IP instead
        for _ in range(2):
            resp = await c.get("/health", headers={"X-Forwarded-For": "1.2.3.4"})
            assert resp.status_code == 200

        # Third request should be rate-limited based on actual client IP
        # (all 3 requests share the same real IP)
        resp = await c.get("/health", headers={"X-Forwarded-For": "5.6.7.8"})
        assert resp.status_code == 429


async def test_rate_limit_trusts_xff_when_enabled():
    """With trust_proxy=True, X-Forwarded-For is used for IP extraction."""
    app = _make_app(rate_limit=True, max_requests=2, trust_proxy=True)
    async with _client(app) as c:
        # Exhaust limit for IP "1.2.3.4"
        for _ in range(2):
            resp = await c.get("/health", headers={"X-Forwarded-For": "1.2.3.4"})
            assert resp.status_code == 200

        # Same XFF IP — should be rate limited
        resp = await c.get("/health", headers={"X-Forwarded-For": "1.2.3.4"})
        assert resp.status_code == 429

        # Different XFF IP — should be allowed
        resp = await c.get("/health", headers={"X-Forwarded-For": "5.6.7.8"})
        assert resp.status_code == 200


async def test_rate_limit_memory_cap():
    """After >10k IPs, the _hits dict is pruned to prevent memory exhaustion."""
    app = _make_app(rate_limit=True, max_requests=100)

    # Find the RateLimitMiddleware instance in the middleware stack
    node = app.middleware_stack
    rl_mw = None
    while node is not None:
        if isinstance(node, RateLimitMiddleware):
            rl_mw = node
            break
        node = getattr(node, "app", None)

    # Need to build the app first so middleware_stack exists
    # For an ASGI app, the middleware stack is built on first request.
    # Force it by making one request first.
    async with _client(app) as c:
        await c.get("/health")

    # Re-find after stack is built
    node = app.middleware_stack
    rl_mw = None
    while node is not None:
        if isinstance(node, RateLimitMiddleware):
            rl_mw = node
            break
        node = getattr(node, "app", None)

    assert rl_mw is not None, "RateLimitMiddleware not found in stack"

    # Inject 10_001 fake IPs directly into _hits
    import time as _time
    now = _time.monotonic()
    for i in range(10_001):
        rl_mw._hits[f"fake-{i}"] = [now]

    assert len(rl_mw._hits) > 10_000

    # Next request triggers the memory cap check
    async with _client(app) as c:
        resp = await c.get("/health")
        assert resp.status_code == 200

    # After the cap, at most ~5001 entries remain (10001 - 5000 + new request IP + prune leftovers)
    assert len(rl_mw._hits) <= 5_100
