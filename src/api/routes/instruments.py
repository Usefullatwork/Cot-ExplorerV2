"""Instrument listing and detail routes."""

from __future__ import annotations

from pathlib import Path

import yaml
from fastapi import APIRouter, HTTPException

from src.db import repository as repo

router = APIRouter(prefix="/api/v1", tags=["instruments"])

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


@router.get("/instruments")
def list_instruments() -> list[dict]:
    """List all 12 tracked instruments."""
    return _load_instruments()


@router.get("/instruments/{key}")
def instrument_detail(key: str) -> dict:
    """Single instrument detail with latest price from the database."""
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

    return match
