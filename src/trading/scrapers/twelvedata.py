#!/usr/bin/env python3
"""
twelvedata.py - Twelvedata OHLC data scraper.

Fetches historical price data from Twelvedata API.
Free tier: 800 requests/day, 8 requests/minute.

Requires TWELVEDATA_API_KEY environment variable.
Zero external dependencies - stdlib only.
"""

import logging
import urllib.request
import urllib.parse
import json
import os
import time

log = logging.getLogger(__name__)

API_KEY = os.environ.get("TWELVEDATA_API_KEY", "")

# Only symbols confirmed available on free plan
FREE_SYMBOLS = {"EURUSD=X", "JPY=X", "GBPUSD=X", "AUDUSD=X", "GC=F", "HYG", "TIP", "EEM"}

# Yahoo -> Twelvedata symbol mapping
SYMBOL_MAP = {
    "EURUSD=X": "EUR/USD",
    "JPY=X":    "USD/JPY",
    "GBPUSD=X": "GBP/USD",
    "AUDUSD=X": "AUD/USD",
    "GC=F":     "XAU/USD",
    "HYG":      "HYG",
    "TIP":      "TIP",
    "EEM":      "EEM",
}

INTERVAL_MAP = {"1d": "1day", "15m": "15min", "60m": "1h"}
SIZE_MAP = {"1y": 365, "5d": 500, "60d": 500, "30d": 35}


def fetch_ohlc(symbol, interval="1d", outputsize=365):
    """
    Fetch OHLC from Twelvedata.

    Args:
        symbol: Yahoo-style symbol (must be in FREE_SYMBOLS).
        interval: "1d", "15m", or "60m"
        outputsize: Number of data points to fetch.

    Returns:
        List of (high, low, close) tuples, oldest first. Empty on error.
    """
    if not API_KEY or symbol not in FREE_SYMBOLS:
        return []
    td_sym = SYMBOL_MAP.get(symbol, symbol)
    td_int = INTERVAL_MAP.get(interval, interval)
    url = (f"https://api.twelvedata.com/time_series"
           f"?symbol={urllib.parse.quote(td_sym)}"
           f"&interval={td_int}&outputsize={outputsize}"
           f"&apikey={API_KEY}")
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=12) as r:
            d = json.loads(r.read())
        if d.get("status") == "error":
            log.warning(f"Twelvedata {td_sym}: {d.get('message', 'unknown error')}")
            return []
        rows = []
        for v in reversed(d.get("values", [])):
            try:
                rows.append((float(v["high"]), float(v["low"]), float(v["close"])))
            except (ValueError, KeyError):
                continue
        time.sleep(8)  # Rate limit: max 8 req/min on free plan
        return rows
    except Exception as e:
        log.error(f"Twelvedata ERROR {td_sym} ({interval}): {e}")
        return []


if __name__ == "__main__":
    if not API_KEY:
        log.warning("Set TWELVEDATA_API_KEY to test")
    else:
        rows = fetch_ohlc("EURUSD=X", "1d", 30)
        log.info(f"EUR/USD: {len(rows)} bars")
