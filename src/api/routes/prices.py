"""Live prices route — latest price + 1d/5d changes for all instruments."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from src.api.middleware.cache import macro_cache
from src.db import repository as repo

_DATA_DIR = Path(__file__).resolve().parents[3] / "data"

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["prices"])


class PriceItem(BaseModel):
    """Single instrument price snapshot."""

    instrument: str
    name: str
    group: str
    price: float
    chg_1d: float | None = None
    chg_5d: float | None = None


class PricesResponse(BaseModel):
    """Response for live prices endpoint."""

    items: list[PriceItem]


# Instrument groups for the Prices panel
_PRICE_GROUPS = {
    "Indekser": ["SPX", "NAS100", "VIX"],
    "Valuta": ["EURUSD", "USDJPY", "GBPUSD", "AUDUSD", "USDCHF", "DXY", "USDNOK"],
    "Ravarer": ["Gold", "Silver", "Brent", "WTI", "NATGAS"],
    "Rente/Kreditt": ["HYG", "TIP"],
}

# Instrument key -> display name
_DISPLAY_NAMES = {
    "SPX": "S&P 500", "NAS100": "Nasdaq 100", "VIX": "VIX",
    "EURUSD": "EUR/USD", "USDJPY": "USD/JPY", "GBPUSD": "GBP/USD",
    "AUDUSD": "AUD/USD", "USDCHF": "USD/CHF", "DXY": "Dollar Index",
    "USDNOK": "USD/NOK",
    "Gold": "Gull", "Silver": "Solv", "Brent": "Brent",
    "WTI": "WTI", "NATGAS": "Naturgass",
    "HYG": "High Yield", "TIP": "TIPS ETF",
}


def _prices_from_macro_json() -> list[dict]:
    """Read live prices from data/macro/latest.json as fallback when DB is empty."""
    macro_path = _DATA_DIR / "macro" / "latest.json"
    if not macro_path.exists():
        return []
    try:
        with open(macro_path, encoding="utf-8") as f:
            macro = json.load(f)
    except (json.JSONDecodeError, OSError):
        return []

    prices_data = macro.get("prices", {})
    items = []
    for group_name, keys in _PRICE_GROUPS.items():
        for key in keys:
            p = prices_data.get(key)
            if not p:
                continue
            price = p.get("price", 0)
            items.append({
                "instrument": key,
                "name": _DISPLAY_NAMES.get(key, key),
                "group": group_name,
                "price": price,
                "chg_1d": p.get("chg1d"),
                "chg_5d": p.get("chg5d"),
            })
    return items


def _pct_change(prices: list, offset: int) -> float | None:
    """Calculate percentage change from `offset` days ago to latest."""
    if len(prices) < offset + 1:
        return None
    latest = prices[-1].close
    prev = prices[-(offset + 1)].close
    if prev == 0:
        return None
    return round((latest - prev) / prev * 100, 2)


@router.get(
    "/prices/live",
    summary="Live prices for all tracked instruments",
    description="Returns latest price + 1d/5d changes grouped by Indices, Forex, Commodities.",
    response_model=PricesResponse,
)
def live_prices() -> dict:
    """Latest prices with 1d and 5d changes."""
    cached = macro_cache.get("prices_live")
    if cached is not None:
        return cached

    items = []
    for group_name, keys in _PRICE_GROUPS.items():
        for key in keys:
            prices = repo.get_price_history(instrument=key)
            if not prices:
                continue

            latest = prices[-1]
            chg_1d = _pct_change(prices, 1)
            chg_5d = _pct_change(prices, 5)

            items.append({
                "instrument": key,
                "name": _DISPLAY_NAMES.get(key, key),
                "group": group_name,
                "price": round(latest.close, latest.close > 100 and 2 or 5),
                "chg_1d": chg_1d,
                "chg_5d": chg_5d,
            })

    # Fallback: if DB has no prices, read from macro JSON
    if not items:
        items = _prices_from_macro_json()

    result = {"items": items}
    macro_cache.set("prices_live", result, ttl=60)
    return result


class PriceHistoryItem(BaseModel):
    """Single price bar for time series."""

    time: str
    value: float


class PriceHistoryResponse(BaseModel):
    """Response for price history endpoint."""

    instrument: str
    items: list[PriceHistoryItem]


# All known instrument keys (union of groups)
_ALL_INSTRUMENTS = {key for keys in _PRICE_GROUPS.values() for key in keys}


@router.get(
    "/prices/{instrument}/history",
    summary="Price history for an instrument",
    description="Returns daily close prices as time/value pairs for chart rendering.",
    response_model=PriceHistoryResponse,
)
def price_history(instrument: str) -> dict:
    """Daily close prices for a single instrument."""
    if instrument not in _ALL_INSTRUMENTS:
        raise HTTPException(status_code=404, detail=f"Unknown instrument: {instrument}")

    prices = repo.get_price_history(instrument=instrument)
    if not prices:
        return {"instrument": instrument, "items": []}

    items = [{"time": p.date, "value": round(p.close, 5)} for p in prices]
    return {"instrument": instrument, "items": items}
