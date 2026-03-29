"""Crypto market data routes — market overview and Fear & Greed index."""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, Field

from src.api.middleware.cache import macro_cache
from src.trading.scrapers.crypto import fetch_crypto_market, fetch_fear_greed

router = APIRouter(prefix="/api/v1", tags=["crypto"])


# ── Response models ──────────────────────────────────────────────────────────


class CoinItem(BaseModel):
    """Single cryptocurrency market data."""

    id: str = Field(..., description="CoinGecko coin ID")
    symbol: str = Field(..., description="Ticker symbol (uppercase)")
    name: str = Field(..., description="Coin name")
    price: float | None = Field(None, description="Current price in USD")
    market_cap: float | None = Field(None, description="Market cap in USD")
    volume_24h: float | None = Field(None, description="24h trading volume in USD")
    change_24h: float | None = Field(None, description="24h price change percentage")
    rank: int | None = Field(None, description="Market cap rank")
    image: str = Field("", description="Coin icon URL")


class CryptoMarketResponse(BaseModel):
    """Crypto market overview."""

    coins: list[CoinItem] = Field(default_factory=list)
    total_market_cap: float = Field(0, description="Total market cap of tracked coins")
    btc_dominance: float = Field(0, description="Bitcoin dominance percentage")
    fetched_at: str = Field("", description="ISO timestamp of data fetch")


class FearGreedResponse(BaseModel):
    """Crypto Fear & Greed index."""

    value: int = Field(50, description="Index value 0-100")
    label: str = Field("Neutral", description="Human-readable classification")
    timestamp: str = Field("", description="Unix timestamp of measurement")
    fetched_at: str = Field("", description="ISO timestamp of data fetch")


# ── Endpoints ────────────────────────────────────────────────────────────────


@router.get(
    "/crypto/market",
    response_model=CryptoMarketResponse,
    summary="Crypto market overview",
    description="Returns price, market cap, volume, and 24h change for 8 major cryptocurrencies.",
)
def crypto_market() -> dict:
    """Market data for BTC, ETH, SOL, XRP, BNB, ADA, DOGE, AVAX."""
    cached = macro_cache.get("crypto_market")
    if cached is not None:
        return cached

    data = fetch_crypto_market()
    if data is None:
        return {"coins": [], "total_market_cap": 0, "btc_dominance": 0, "fetched_at": ""}

    macro_cache.set("crypto_market", data, ttl=120)
    return data


@router.get(
    "/crypto/fear-greed",
    response_model=FearGreedResponse,
    summary="Crypto Fear & Greed index",
    description="Returns the alternative.me Fear & Greed index (0=Extreme Fear, 100=Extreme Greed).",
)
def crypto_fear_greed() -> dict:
    """Current Fear & Greed index value and classification."""
    cached = macro_cache.get("crypto_fng")
    if cached is not None:
        return cached

    data = fetch_fear_greed()
    if data is None:
        return {"value": 50, "label": "Ukjent", "timestamp": "", "fetched_at": ""}

    macro_cache.set("crypto_fng", data, ttl=300)
    return data
