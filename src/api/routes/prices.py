"""Live prices route — latest price + 1d/5d changes for all instruments."""

from __future__ import annotations

import logging

from fastapi import APIRouter
from pydantic import BaseModel

from src.api.middleware.cache import macro_cache
from src.db import repository as repo

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
    "Valuta": ["EURUSD", "USDJPY", "GBPUSD", "AUDUSD", "USDCHF", "DXY"],
    "Ravarer": ["Gold", "Silver", "Brent", "WTI", "NATGAS"],
}

# Instrument key -> display name
_DISPLAY_NAMES = {
    "SPX": "S&P 500", "NAS100": "Nasdaq 100", "VIX": "VIX",
    "EURUSD": "EUR/USD", "USDJPY": "USD/JPY", "GBPUSD": "GBP/USD",
    "AUDUSD": "AUD/USD", "USDCHF": "USD/CHF", "DXY": "Dollar Index",
    "Gold": "Gull", "Silver": "Solv", "Brent": "Brent",
    "WTI": "WTI", "NATGAS": "Naturgass",
}


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

    result = {"items": items}
    macro_cache.set("prices_live", result, ttl=60)
    return result
