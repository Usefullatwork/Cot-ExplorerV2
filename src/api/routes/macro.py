"""Macro data routes — Dollar Smile, VIX regime, indicators, VIX term structure, ADR."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from fastapi import APIRouter
from pydantic import BaseModel
from starlette.responses import Response

from src.analysis.adr_calculator import calculate_adr, to_dict as adr_to_dict
from src.api.middleware.cache import macro_cache
from src.db import repository as repo
from src.trading.scrapers.vix_futures import (
    fetch_vix_term_structure,
    to_dict as vix_to_dict,
)

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["macro"])

_DATA_DIR = Path(__file__).resolve().parents[3] / "data"


@router.get(
    "/macro",
    summary="Full macro panel",
    description=(
        "Returns the complete macro environment: Dollar Smile, VIX regime, conflicts, prices, calendar."
        " Prefers DB snapshot; falls back to data/macro/latest.json."
    ),
)
def macro_panel():
    """Full macro panel: Dollar Smile, VIX regime, conflicts, prices.

    Prefers the DB snapshot; falls back to data/macro/latest.json.
    """
    cached = macro_cache.get("macro_panel_json")
    if cached is not None:
        return Response(content=cached, media_type="application/json; charset=utf-8")

    snap = repo.get_latest_macro()
    if snap and snap.full_json:
        macro_cache.set("macro_panel_json", snap.full_json)
        return Response(content=snap.full_json, media_type="application/json; charset=utf-8")

    macro_path = _DATA_DIR / "macro" / "latest.json"
    if macro_path.exists():
        with open(macro_path, "rb") as f:
            raw = f.read()
        macro_cache.set("macro_panel_json", raw)
        return Response(content=raw, media_type="application/json; charset=utf-8")

    return {"error": "No macro data available. Run the pipeline first."}


@router.get(
    "/macro/indicators",
    summary="Macro indicators subset",
    description="Returns price data for key macro indicators: HYG, TIP, TNX, IRX, Copper, EEM.",
)
def macro_indicators() -> dict:
    """Subset of macro indicators: HYG, TIP, TNX, IRX, Copper, EEM.

    Falls back to reading from data/macro/latest.json prices dict.
    """
    cached = macro_cache.get("macro_indicators")
    if cached is not None:
        return cached

    snap = repo.get_latest_macro()
    if snap and snap.full_json:
        full = json.loads(snap.full_json)
        prices = full.get("prices", {})
    else:
        macro_path = _DATA_DIR / "macro" / "latest.json"
        if macro_path.exists():
            with open(macro_path, encoding="utf-8") as f:
                prices = json.load(f).get("prices", {})
        else:
            return {}

    indicator_keys = ["HYG", "TIP", "TNX", "IRX", "Copper", "EEM"]
    result = {k: prices[k] for k in indicator_keys if k in prices}
    macro_cache.set("macro_indicators", result)
    return result


# ---------------------------------------------------------------------------
# VIX Term Structure
# ---------------------------------------------------------------------------


class VixTermResponse(BaseModel):
    """Response model for VIX term structure."""

    spot: float
    vix_9d: float
    vix_3m: float
    regime: str
    spread: float


@router.get(
    "/macro/vix-term",
    summary="VIX term structure",
    description="Returns VIX spot, 9-day, 3-month values and contango/backwardation regime.",
    response_model=VixTermResponse,
)
def vix_term_structure() -> dict:
    """VIX term structure: spot, 9D, 3M, regime."""
    cached = macro_cache.get("vix_term")
    if cached is not None:
        return cached

    ts = fetch_vix_term_structure()
    result = vix_to_dict(ts)
    macro_cache.set("vix_term", result, ttl=60)
    return result


# ---------------------------------------------------------------------------
# ADR (Average Daily Range)
# ---------------------------------------------------------------------------


class ADRItem(BaseModel):
    """Single instrument ADR data."""

    instrument: str
    adr: float
    adr_pct: float
    current_price: float
    days_used: int


class ADRResponse(BaseModel):
    """Response model for ADR endpoint."""

    items: list[ADRItem]


@router.get(
    "/macro/adr",
    summary="Average Daily Range for all instruments",
    description="Returns 20-day ADR for all instruments with daily price data.",
    response_model=ADRResponse,
)
def average_daily_range() -> dict:
    """Calculate 20-day ADR for all instruments from prices_daily."""
    cached = macro_cache.get("adr_data")
    if cached is not None:
        return cached

    # Load instruments from config/instruments.yaml (same as instruments route)
    from src.api.routes.instruments import _load_instruments

    instruments = _load_instruments()
    items = []

    for inst in instruments:
        key = inst.get("key", "")
        prices = repo.get_price_history(instrument=key)
        if len(prices) < 5:
            continue

        highs = [p.high for p in prices]
        lows = [p.low for p in prices]
        current = prices[-1].close if prices else 0.0

        try:
            adr = calculate_adr(
                instrument=key,
                highs=highs,
                lows=lows,
                current_price=current,
                period=20,
            )
            items.append(adr_to_dict(adr))
        except ValueError:
            continue

    result = {"items": items}
    macro_cache.set("adr_data", result, ttl=300)
    return result
