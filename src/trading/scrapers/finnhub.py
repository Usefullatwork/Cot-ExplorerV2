#!/usr/bin/env python3
"""
finnhub.py - Finnhub realtime quote scraper.

Fetches realtime quotes for indices and commodities.
Free tier: 60 requests/minute.

Requires FINNHUB_API_KEY environment variable.
Zero external dependencies - stdlib only.
"""

import urllib.request
import urllib.parse
import json
import os

API_KEY = os.environ.get("FINNHUB_API_KEY", "")

# Yahoo -> Finnhub symbol mapping
QUOTE_MAP = {
    "^GSPC": "^GSPC",
    "^NDX":  "^NDX",
    "^VIX":  "^VIX",
    "SI=F":  "SI1!",
    "BZ=F":  "UKOIL",
    "CL=F":  "USOIL",
    "HG=F":  "HG1!",
}


def fetch_quote(symbol):
    """
    Fetch realtime (h, l, c) quote from Finnhub.

    Args:
        symbol: Yahoo-style symbol (must be in QUOTE_MAP).

    Returns:
        Tuple (high, low, close) or None on error.
    """
    if not API_KEY:
        return None
    fh_sym = QUOTE_MAP.get(symbol)
    if not fh_sym:
        return None
    url = (f"https://finnhub.io/api/v1/quote"
           f"?symbol={urllib.parse.quote(fh_sym)}&token={API_KEY}")
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=8) as r:
            d = json.loads(r.read())
        c, h, l = d.get("c", 0), d.get("h", 0), d.get("l", 0)
        if c and h and l:
            return (h, l, c)
        return None
    except Exception as e:
        print(f"  Finnhub ERROR {fh_sym}: {e}")
        return None


if __name__ == "__main__":
    if not API_KEY:
        print("Set FINNHUB_API_KEY to test")
    else:
        for sym, name in [("^GSPC", "S&P 500"), ("^VIX", "VIX")]:
            q = fetch_quote(sym)
            if q:
                print(f"{name}: H={q[0]} L={q[1]} C={q[2]}")
