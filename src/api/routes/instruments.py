"""Instrument listing and detail routes."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import yaml
from fastapi import APIRouter, HTTPException

from pydantic import BaseModel, Field

from src.api.middleware.cache import instruments_cache
from src.db import repository as repo
from src.security.input_validator import validate_symbol

router = APIRouter(prefix="/api/v1", tags=["instruments"])


# ── Response models ──────────────────────────────────────────────────────────

class CurrentPrice(BaseModel):
    """Latest price snapshot for an instrument."""

    date: str = Field(..., description="Date of the price bar (YYYY-MM-DD)", examples=["2026-03-25"])
    high: float = Field(..., description="Daily high", examples=[1.0920])
    low: float = Field(..., description="Daily low", examples=[1.0810])
    close: float = Field(..., description="Daily close", examples=[1.0880])
    source: Optional[str] = Field(None, description="Data provider name", examples=["yahoo"])


class InstrumentResponse(BaseModel):
    """Trading instrument definition with optional current price."""

    key: str = Field(..., description="Unique instrument key", examples=["EURUSD"])
    name: str = Field(..., description="Full instrument name", examples=["EUR/USD"])
    symbol: str = Field(..., description="Market symbol", examples=["EURUSD=X"])
    label: str = Field(..., description="Short display label", examples=["EUR/USD"])
    category: str = Field(..., description="Asset category", examples=["valuta"])
    current_price: Optional[CurrentPrice] = Field(None, description="Latest price from the database")

    model_config = {"extra": "allow"}


# ── Internal helpers ─────────────────────────────────────────────────────────

_INSTRUMENTS_CACHE: list[dict] | None = None


def _load_instruments() -> list[dict]:
    """Load instrument definitions from config/instruments.yaml."""
    global _INSTRUMENTS_CACHE
    if _INSTRUMENTS_CACHE is not None:
        return _INSTRUMENTS_CACHE

    config_path = Path(__file__).resolve().parents[3] / "config" / "instruments.yaml"
    with open(config_path) as f:
        data = yaml.safe_load(f)
    _INSTRUMENTS_CACHE = data.get("instruments", [])
    return _INSTRUMENTS_CACHE


@router.get(
    "/instruments",
    response_model=list[InstrumentResponse],
    summary="List all instruments",
    description="Returns all tracked instruments with their configuration from instruments.yaml.",
)
def list_instruments() -> list[dict]:
    """List all 12 tracked instruments."""
    cached = instruments_cache.get("all_instruments")
    if cached is not None:
        return cached
    result = _load_instruments()
    instruments_cache.set("all_instruments", result)
    return result


@router.get(
    "/instruments/{key}",
    response_model=InstrumentResponse,
    summary="Instrument detail",
    description="Returns a single instrument definition with the latest price from the database.",
)
def instrument_detail(key: str) -> dict:
    """Single instrument detail with latest price from the database."""
    try:
        key = validate_symbol(key)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    cache_key = f"instrument_detail:{key}"
    cached = instruments_cache.get(cache_key)
    if cached is not None:
        return cached

    instruments = _load_instruments()
    match = next((i for i in instruments if i["key"] == key), None)
    if not match:
        raise HTTPException(status_code=404, detail=f"Instrument {key} not found")

    # Attach latest price from DB if available
    prices = repo.get_price_history(instrument=key, start=None, end=None)
    if prices:
        latest = prices[-1]
        match = {
            **match,
            "current_price": {
                "date": latest.date,
                "high": latest.high,
                "low": latest.low,
                "close": latest.close,
                "source": latest.source,
            },
        }
    else:
        match = {**match, "current_price": None}

    instruments_cache.set(cache_key, match)
    return match
