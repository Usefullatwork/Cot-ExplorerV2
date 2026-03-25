"""FastAPI application factory for Cot-ExplorerV2."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.middleware.auth import APIKeyMiddleware
from src.api.routes import backtests, cot, health, instruments, macro, signals, webhook


def create_app() -> FastAPI:
    """Build and return the FastAPI application with all routes and middleware."""
    app = FastAPI(
        title="Cot-ExplorerV2 API",
        version="2.0.0",
        description="Trading signal platform: COT + SMC + 12-point confluence scoring",
    )

    # CORS — allow all origins for development
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

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

    return app


app = create_app()
