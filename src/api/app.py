"""FastAPI application factory for Cot-ExplorerV2."""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware

from src.api.middleware.auth import APIKeyMiddleware
from src.api.middleware.rate_limit import RateLimitMiddleware
from src.api.routes import (
    backtests,
    correlations,
    cot,
    crypto,
    geointel,
    health,
    instruments,
    intelligence,
    macro,
    prices,
    risk,
    signal_health,
    signal_log,
    signals,
    trading,
    webhook,
)

CORS_ORIGINS = os.environ.get("CORS_ORIGINS", "http://localhost:3000").split(",")


class CSPMiddleware(BaseHTTPMiddleware):
    """Add Content-Security-Policy headers to all responses."""

    async def dispatch(self, request, call_next):
        response = await call_next(request)
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self'; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "font-src https://fonts.gstatic.com; "
            "img-src 'self' data: https://*.basemaps.cartocdn.com; "
            "connect-src 'self'"
        )
        return response


def create_app() -> FastAPI:
    """Build and return the FastAPI application with all routes and middleware."""
    app = FastAPI(
        title="Cot-ExplorerV2 API",
        version="2.0.0",
        description="Trading signal platform: COT + SMC + 12-point confluence scoring",
    )

    # CORS — restricted to configured origins
    app.add_middleware(
        CORSMiddleware,
        allow_origins=CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type", "X-API-Key"],
    )

    # Per-IP rate limiting
    app.add_middleware(RateLimitMiddleware)

    # API key authentication middleware
    app.add_middleware(APIKeyMiddleware)

    # Content Security Policy headers
    app.add_middleware(CSPMiddleware)

    # Register routers
    app.include_router(health.router)
    app.include_router(signals.router)
    app.include_router(instruments.router)
    app.include_router(cot.router)
    app.include_router(macro.router)
    app.include_router(webhook.router)
    app.include_router(backtests.router)
    app.include_router(trading.router)
    app.include_router(trading.tv_router)
    app.include_router(geointel.router)
    app.include_router(correlations.router)
    app.include_router(signal_log.router)
    app.include_router(prices.router)
    app.include_router(crypto.router)
    app.include_router(signal_health.router)
    app.include_router(risk.router)
    app.include_router(intelligence.router)

    # Serve built frontend (must be LAST — after all API routes)
    frontend_dist = Path(__file__).resolve().parents[2] / "frontend" / "dist"
    if frontend_dist.is_dir():
        app.mount("/", StaticFiles(directory=str(frontend_dist), html=True), name="frontend")

    return app


app = create_app()
