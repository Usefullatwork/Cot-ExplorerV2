#!/usr/bin/env python3
"""Smart Money Concepts (SMC) analysis engine.

Thin wrapper -- all logic lives in src.trading.core.smc.
"""

import sys
from pathlib import Path

# Ensure project root is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from src.trading.core.smc import *  # noqa: E402, F401, F403
from src.trading.core.smc import run_smc  # noqa: E402 -- explicit for IDE

if __name__ == "__main__":
    import logging
    import json
    import urllib.request
    import urllib.parse

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    log = logging.getLogger(__name__)

    def fetch(symbol, interval="15m", range_="5d"):
        url = (f"https://query1.finance.yahoo.com/v8/finance/chart/"
               f"{urllib.parse.quote(symbol)}?interval={interval}&range={range_}")
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as r:
            d = json.loads(r.read())
        q = d["chart"]["result"][0]["indicators"]["quote"][0]
        return [(h, l, c) for h, l, c in zip(q["high"], q["low"], q["close"])
                if h and l and c]

    for sym, name in [("EURUSD=X", "EUR/USD"), ("GC=F", "Gold"), ("CL=F", "WTI")]:
        log.info("=== %s ===", name)
        rows = fetch(sym)
        if not rows:
            log.info("  No data"); continue
        result = run_smc(rows, swing_length=5)
        if not result:
            log.info("  Insufficient data"); continue
        curr = rows[-1][2]
        log.info("  Price: %.5f  Structure: %s", curr, result["structure"])
