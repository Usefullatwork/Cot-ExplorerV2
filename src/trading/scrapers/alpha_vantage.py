#!/usr/bin/env python3
"""
alpha_vantage.py - Alpha Vantage market data scraper.

Fetches daily OHLC data from Alpha Vantage API.
Free tier: 25 requests/day, 5 requests/minute.

Requires ALPHA_VANTAGE_API_KEY environment variable.
Zero external dependencies - stdlib only.
"""

import urllib.request
import urllib.parse
import json
import os
import time

API_KEY = os.environ.get("ALPHA_VANTAGE_API_KEY", "")


def fetch_daily(symbol, outputsize="compact"):
    """
    Fetch daily OHLC from Alpha Vantage.

    Args:
        symbol: Ticker symbol (e.g., "MSFT", "SPY")
        outputsize: "compact" (100 days) or "full" (20+ years)

    Returns:
        List of (high, low, close) tuples, oldest first. Empty on error.
    """
    if not API_KEY:
        return []
    url = (f"https://www.alphavantage.co/query"
           f"?function=TIME_SERIES_DAILY"
           f"&symbol={urllib.parse.quote(symbol)}"
           f"&outputsize={outputsize}"
           f"&apikey={API_KEY}")
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=12) as r:
            d = json.loads(r.read())
        ts = d.get("Time Series (Daily)", {})
        rows = []
        for date in sorted(ts.keys()):
            bar = ts[date]
            try:
                h = float(bar["2. high"])
                l = float(bar["3. low"])
                c = float(bar["4. close"])
                rows.append((h, l, c))
            except (ValueError, KeyError):
                continue
        time.sleep(12)  # Rate limit: 5 req/min
        return rows
    except Exception as e:
        print(f"  Alpha Vantage ERROR {symbol}: {e}")
        return []


def fetch_forex(from_currency, to_currency):
    """
    Fetch forex exchange rate.

    Returns:
        Float exchange rate or None on error.
    """
    if not API_KEY:
        return None
    url = (f"https://www.alphavantage.co/query"
           f"?function=CURRENCY_EXCHANGE_RATE"
           f"&from_currency={from_currency}"
           f"&to_currency={to_currency}"
           f"&apikey={API_KEY}")
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            d = json.loads(r.read())
        rate = d.get("Realtime Currency Exchange Rate", {}).get("5. Exchange Rate")
        return float(rate) if rate else None
    except Exception as e:
        print(f"  Alpha Vantage FX ERROR {from_currency}/{to_currency}: {e}")
        return None


if __name__ == "__main__":
    if not API_KEY:
        print("Set ALPHA_VANTAGE_API_KEY to test")
    else:
        rows = fetch_daily("SPY", "compact")
        print(f"SPY: {len(rows)} daily bars")
