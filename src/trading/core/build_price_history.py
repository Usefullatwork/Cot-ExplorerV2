#!/usr/bin/env python3
"""Fetch weekly price history from Yahoo Finance.

Saves data to ``data/prices/{key}.json`` plus a ``cot_map.json`` mapping
CFTC COT symbols to price keys.
"""

import json
import logging
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

log = logging.getLogger(__name__)

INSTRUMENTS = [
    {"key": "eurusd", "yahoo": "EURUSD=X", "navn": "EUR/USD"},
    {"key": "usdjpy", "yahoo": "JPY=X", "navn": "USD/JPY"},
    {"key": "gbpusd", "yahoo": "GBPUSD=X", "navn": "GBP/USD"},
    {"key": "audusd", "yahoo": "AUDUSD=X", "navn": "AUD/USD"},
    {"key": "gold", "yahoo": "GC=F", "navn": "Gull"},
    {"key": "silver", "yahoo": "SI=F", "navn": "Solv"},
    {"key": "brent", "yahoo": "BZ=F", "navn": "Brent"},
    {"key": "wti", "yahoo": "CL=F", "navn": "WTI"},
    {"key": "spx", "yahoo": "^GSPC", "navn": "S&P 500"},
    {"key": "nas100", "yahoo": "^NDX", "navn": "Nasdaq"},
    {"key": "dxy", "yahoo": "DX-Y.NYB", "navn": "DXY"},
    {"key": "corn", "yahoo": "ZC=F", "navn": "Mais"},
    {"key": "wheat", "yahoo": "ZW=F", "navn": "Hvete"},
    {"key": "soybean", "yahoo": "ZS=F", "navn": "Soyabonner"},
    {"key": "sugar", "yahoo": "SB=F", "navn": "Sukker"},
    {"key": "coffee", "yahoo": "KC=F", "navn": "Kaffe"},
    {"key": "cocoa", "yahoo": "CC=F", "navn": "Kakao"},
]

COT_TO_PRICE = {
    "099741": "eurusd",
    "096742": "usdjpy",
    "092741": "gbpusd",
    "232741": "audusd",
    "088691": "gold",
    "084691": "silver",
    "067651": "wti",
    "023651": "brent",
    "133741": "spx",
    "209742": "nas100",
    "098662": "dxy",
    "002602": "corn",
    "001602": "wheat",
    "005602": "soybean",
    "083731": "sugar",
    "073732": "coffee",
    "080732": "cocoa",
}


def fetch_weekly(yahoo_sym: str, years: int = 15) -> list[dict]:
    """Fetch weekly OHLC from Yahoo Finance for *yahoo_sym*."""
    end = int(time.time())
    start = end - years * 365 * 24 * 3600
    url = (
        f"https://query1.finance.yahoo.com/v8/finance/chart/"
        f"{urllib.parse.quote(yahoo_sym)}?interval=1wk&period1={start}&period2={end}"
    )
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            d = json.loads(r.read())
        res = d["chart"]["result"][0]
        ts = res["timestamp"]
        cl = res["indicators"]["quote"][0]["close"]
        out = []
        for i in range(len(ts)):
            if cl[i] is None:
                continue
            dt = datetime.fromtimestamp(ts[i], tz=timezone.utc).strftime("%Y-%m-%d")
            out.append({"date": dt, "price": round(cl[i], 5 if cl[i] < 100 else 2)})
        return out
    except Exception as e:
        log.error("  FEIL: %s", e)
        return []


def build_price_history(base_dir: str | Path | None = None) -> int:
    """Fetch and store weekly prices for all instruments.

    Parameters
    ----------
    base_dir : path, optional
        Target ``data/prices/`` directory.  Defaults to ``<project>/data/prices``.

    Returns
    -------
    int  Number of instruments successfully fetched.
    """
    if base_dir is None:
        base_dir = Path(__file__).resolve().parents[3] / "data" / "prices"
    base_dir = Path(base_dir)
    base_dir.mkdir(parents=True, exist_ok=True)

    count = 0
    for inst in INSTRUMENTS:
        log.info("Fetching %s (%s)...", inst["navn"], inst["yahoo"])
        rows = fetch_weekly(inst["yahoo"])
        if not rows:
            continue
        out = {"key": inst["key"], "navn": inst["navn"], "yahoo": inst["yahoo"], "data": rows}
        path = base_dir / (inst["key"] + ".json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False)
        log.info("  %d weeks -> %s", len(rows), path)
        count += 1

    # Save COT -> price mapping
    with open(base_dir / "cot_map.json", "w", encoding="utf-8") as f:
        json.dump(COT_TO_PRICE, f, ensure_ascii=False, indent=2)

    log.info("Done! Saved %d instruments to %s", count, base_dir)
    return count


def main() -> None:
    """CLI entry point."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    build_price_history()


if __name__ == "__main__":
    main()
