"""Crypto market scraper — CoinGecko (free, no API key) + Fear & Greed index.

Fetches market data for 8 major cryptocurrencies and the alternative.me
Fear & Greed index.  All functions return None/empty on error (never crash).
"""

from __future__ import annotations

import json
import logging
import urllib.request
from datetime import datetime, timezone

log = logging.getLogger(__name__)

_HEADERS = {"User-Agent": "Mozilla/5.0 (CotExplorerV2)"}
_TIMEOUT = 10

_COINS = "bitcoin,ethereum,solana,ripple,binancecoin,cardano,dogecoin,avalanche-2"
_COINGECKO_URL = (
    "https://api.coingecko.com/api/v3/coins/markets"
    f"?vs_currency=usd&ids={_COINS}"
    "&order=market_cap_desc&per_page=20&page=1"
    "&sparkline=false&price_change_percentage=24h"
)
_FNG_URL = "https://api.alternative.me/fng/?limit=1"


def fetch_crypto_market() -> dict | None:
    """Fetch market data for 8 major cryptocurrencies from CoinGecko.

    Returns dict with ``coins``, ``total_market_cap``, ``btc_dominance``, ``fetched_at``
    or None on error.
    """
    req = urllib.request.Request(_COINGECKO_URL, headers=_HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as r:
            data = json.loads(r.read())
    except Exception as e:
        log.error("CoinGecko fetch error: %s", e)
        return None

    if not isinstance(data, list) or not data:
        return None

    total_cap = sum(c.get("market_cap", 0) or 0 for c in data)
    btc = next((c for c in data if c.get("id") == "bitcoin"), None)
    btc_dom = round(((btc.get("market_cap", 0) or 0) / total_cap) * 100, 1) if btc and total_cap else 0.0

    coins = []
    for c in data:
        coins.append({
            "id": c.get("id", ""),
            "symbol": (c.get("symbol") or "").upper(),
            "name": c.get("name", ""),
            "price": c.get("current_price"),
            "market_cap": c.get("market_cap"),
            "volume_24h": c.get("total_volume"),
            "change_24h": c.get("price_change_percentage_24h"),
            "rank": c.get("market_cap_rank"),
            "image": c.get("image", ""),
        })

    return {
        "coins": coins,
        "total_market_cap": total_cap,
        "btc_dominance": btc_dom,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }


def fetch_fear_greed() -> dict | None:
    """Fetch the Crypto Fear & Greed index from alternative.me.

    Returns dict with ``value`` (0-100), ``label`` (e.g. 'Extreme Fear'),
    ``timestamp``, ``fetched_at`` or None on error.
    """
    req = urllib.request.Request(_FNG_URL, headers=_HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as r:
            body = json.loads(r.read())
    except Exception as e:
        log.error("Fear & Greed fetch error: %s", e)
        return None

    entries = body.get("data", [])
    if not entries:
        return None

    entry = entries[0]
    return {
        "value": int(entry.get("value", 50)),
        "label": entry.get("value_classification", "Neutral"),
        "timestamp": entry.get("timestamp", ""),
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }
