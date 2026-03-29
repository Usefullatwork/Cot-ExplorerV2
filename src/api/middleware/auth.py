"""API key authentication middleware.

If ``SCALP_API_KEY`` is set in the environment, all ``/api/v1/*`` routes
require a matching ``X-API-Key`` header.  If the env var is empty or unset,
the API runs in public mode (no auth).
"""

from __future__ import annotations

import hmac
import logging
import os

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

logger = logging.getLogger(__name__)
_warned_public_mode = False


class APIKeyMiddleware(BaseHTTPMiddleware):
    """Enforce API key on /api/v1/* routes when SCALP_API_KEY is configured."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        api_key = os.environ.get("SCALP_API_KEY", "")
        if not api_key:
            global _warned_public_mode
            if not _warned_public_mode:
                logger.warning("SCALP_API_KEY not set — API running in PUBLIC mode (no authentication)")
                _warned_public_mode = True
            # Public mode — no authentication required
            return await call_next(request)

        path = request.url.path
        if not path.startswith("/api/v1/"):
            # Only protect /api/v1/* routes
            return await call_next(request)

        provided = request.headers.get("X-API-Key", "")
        if not hmac.compare_digest(provided, api_key):
            return JSONResponse(
                status_code=401,
                content={"detail": "Invalid or missing API key"},
            )

        return await call_next(request)
