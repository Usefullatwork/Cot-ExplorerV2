#!/usr/bin/env python3
"""
yahoo_finance.py - Yahoo Finance OHLC data scraper.

Fetches historical and intraday price data from Yahoo Finance v8 API.
Supports multiple intervals (1d, 15m, 60m) and ranges (1y, 5d, 30d).

Free tier, no API key required. Personal use only.
Zero external dependencies - stdlib only.
"""

import logging
import urllib.request
import urllib.parse
import json

log = logging.getLogger(__name__)


def fetch_ohlc(symbol: str, interval: str = "1d", range_: str = "1y") -> list[tuple[float, float, float]]:
    """
    Fetch OHLC data from Yahoo Finance.

    Args:
        symbol: Yahoo Finance symbol (e.g., "EURUSD=X", "GC=F", "^GSPC")
        interval: Candle interval ("1d", "15m", "60m")
        range_: Data range ("1y", "5d", "30d", "60d")

    Returns:
        List of (high, low, close) tuples, oldest first. Empty list on error.
    """
    url = (f"https://query1.finance.yahoo.com/v8/finance/chart/"
           f"{urllib.parse.quote(symbol)}?interval={interval}&range={range_}")
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0",
        "Accept": "application/json",
    })
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            d = json.loads(r.read())
        res = d["chart"]["result"][0]
        q = res["indicators"]["quote"][0]
        rows = [
            (h, l, c)
            for h, l, c in zip(
                q.get("high", []),
                q.get("low", []),
                q.get("close", []),
            )
            if h and l and c
        ]
        return rows
    except Exception as e:
        log.error(f"Yahoo ERROR {symbol} ({interval}): {e}")
        return []


def fetch_price_changes(symbol: str) -> dict | None:
    """
    Fetch current price with 1d/5d/20d changes.

    Returns:
        Dict with price, chg1d, chg5d, chg20d or None on error.
    """
    url = (f"https://query1.finance.yahoo.com/v8/finance/chart/"
           f"{urllib.parse.quote(symbol)}?interval=1d&range=1mo")
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0",
        "Accept": "application/json",
    })
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            d = json.loads(r.read())
        res = d["chart"]["result"][0]
        closes = res["indicators"]["quote"][0]["close"]
        closes = [c for c in closes if c is not None]
        if len(closes) < 6:
            return None
        now = closes[-1]
        day1 = closes[-2]
        day5 = closes[-6] if len(closes) >= 6 else closes[0]
        day20 = closes[-21] if len(closes) >= 21 else closes[0]
        return {
            "price": round(now, 4),
            "chg1d": round((now / day1 - 1) * 100, 2),
            "chg5d": round((now / day5 - 1) * 100, 2),
            "chg20d": round((now / day20 - 1) * 100, 2),
        }
    except Exception as e:
        log.error(f"Yahoo ERROR {symbol}: {e}")
        return None


if __name__ == "__main__":
    for sym, name in [("EURUSD=X", "EUR/USD"), ("GC=F", "Gold"), ("^GSPC", "S&P 500")]:
        log.info(f"{name}:")
        data = fetch_price_changes(sym)
        if data:
            log.info(f"  Price: {data['price']}  1d: {data['chg1d']:+.2f}%  5d: {data['chg5d']:+.2f}%")
