"""Per-IP rate limiting middleware.

Configurable via the ``RATE_LIMIT_PER_MINUTE`` environment variable (default: 60).
Returns HTTP 429 when the limit is exceeded.
"""

from __future__ import annotations

import os
import time
from collections import defaultdict

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

# Sliding-window token bucket per IP
_WINDOW = 60  # seconds


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Enforce per-IP request rate limits."""

    def __init__(self, app, max_requests: int | None = None, trust_proxy: bool | None = None) -> None:  # type: ignore[override]
        super().__init__(app)
        self.max_requests = max_requests or int(os.environ.get("RATE_LIMIT_PER_MINUTE", "60"))
        if trust_proxy is not None:
            self.trust_proxy = trust_proxy
        else:
            self.trust_proxy = os.environ.get("RATE_LIMIT_TRUST_PROXY", "").lower() in ("1", "true")
        # ip -> list of request timestamps (within current window)
        self._hits: dict[str, list[float]] = defaultdict(list)

    def _client_ip(self, request: Request) -> str:
        """Extract the client IP.  Only trusts X-Forwarded-For when trust_proxy is True."""
        if self.trust_proxy:
            forwarded = request.headers.get("X-Forwarded-For")
            if forwarded:
                return forwarded.split(",")[0].strip()
        return request.client.host if request.client else "unknown"

    def _prune(self, ip: str, now: float) -> None:
        """Remove timestamps older than the current window."""
        cutoff = now - _WINDOW
        self._hits[ip] = [t for t in self._hits[ip] if t > cutoff]

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        now = time.monotonic()
        ip = self._client_ip(request)
        self._prune(ip, now)

        # Memory cap: evict oldest entries when the dict grows too large
        if len(self._hits) > 10_000:
            # Sort IPs by their oldest timestamp, remove the 5000 stalest
            sorted_ips = sorted(self._hits.keys(), key=lambda k: min(self._hits[k]) if self._hits[k] else 0)
            for stale_ip in sorted_ips[:5_000]:
                del self._hits[stale_ip]

        if len(self._hits[ip]) >= self.max_requests:
            return JSONResponse(
                status_code=429,
                content={"detail": "Rate limit exceeded. Try again later."},
            )

        self._hits[ip].append(now)
        return await call_next(request)
