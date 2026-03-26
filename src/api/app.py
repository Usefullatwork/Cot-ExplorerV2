"""FastAPI application factory for Cot-ExplorerV2."""

from __future__ import annotations

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.middleware.auth import APIKeyMiddleware
from src.api.middleware.rate_limit import RateLimitMiddleware
from src.api.routes import backtests, cot, health, instruments, macro, signals, trading, webhook

CORS_ORIGINS = os.environ.get("CORS_ORIGINS", "http://localhost:3000").split(",")


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
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Per-IP rate limiting
    app.add_middleware(RateLimitMiddleware)

    # API key authentication middleware
    app.add_middleware(APIKeyMiddleware)

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

    return app


app = create_app()
