#!/usr/bin/env python3
"""
stooq.py - Stooq daily OHLC data scraper.

Fetches daily price data from Stooq.com CSV endpoint.
No API key required. Near-realtime during market hours.

Zero external dependencies - stdlib only.
"""

import logging
import urllib.request
from datetime import datetime, timezone, timedelta

log = logging.getLogger(__name__)

# Symbol mapping: Yahoo -> Stooq
SYMBOL_MAP = {
    "EURUSD=X":  "eurusd",
    "JPY=X":     "usdjpy",
    "GBPUSD=X":  "gbpusd",
    "AUDUSD=X":  "audusd",
    "GC=F":      "xauusd",
    "SI=F":      "xagusd",
    "BZ=F":      "co.f",
    "CL=F":      "cl.f",
    "^GSPC":     "^spx",
    "^NDX":      "^ndx",
    "^VIX":      "^vix",
    "DX-Y.NYB":  "dxy.f",
    "HG=F":      "hg.f",
    "HYG":       "hyg.us",
    "TIP":       "tip.us",
    "EEM":       "eem.us",
}

RANGE_DAYS = {"1y": 400, "30d": 35, "5d": 7}


def fetch_ohlc(symbol, range_="1y"):
    """
    Fetch daily OHLC from Stooq.

    Args:
        symbol: Yahoo-style symbol or Stooq symbol directly.
        range_: "1y", "30d", or "5d"

    Returns:
        List of (high, low, close) tuples, oldest first. Empty on error.
    """
    stooq_sym = SYMBOL_MAP.get(symbol, symbol)
    days = RANGE_DAYS.get(range_, 400)
    d2 = datetime.now(timezone.utc).strftime("%Y%m%d")
    d1 = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y%m%d")
    url = f"https://stooq.com/q/d/l/?s={stooq_sym}&i=d&d1={d1}&d2={d2}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            text = r.read().decode(errors="replace")
        lines = text.strip().split("\n")
        rows = []
        for line in lines[1:]:
            parts = line.strip().split(",")
            if len(parts) < 5:
                continue
            try:
                h, l, c = float(parts[2]), float(parts[3]), float(parts[4])
                if h and l and c:
                    rows.append((h, l, c))
            except (ValueError, IndexError):
                continue
        return rows
    except Exception as e:
        log.error(f"Stooq ERROR {stooq_sym}: {e}")
        return []


if __name__ == "__main__":
    for sym, name in [("EURUSD=X", "EUR/USD"), ("GC=F", "Gold")]:
        rows = fetch_ohlc(sym, "30d")
        if rows:
            log.info(f"{name}: {len(rows)} bars, last close: {rows[-1][2]}")
