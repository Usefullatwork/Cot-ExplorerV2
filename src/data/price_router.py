"""Price routing — fallback logic: TradingView -> Twelvedata -> Stooq -> Yahoo.

Optionally updates the latest bar with a Finnhub real-time quote.
"""

from __future__ import annotations

import json
import logging
import os
import time
import urllib.parse
import urllib.request
from typing import Any

from src.core.models import OhlcBar
from src.data.providers.stooq import StooqProvider
from src.data.providers.tradingview import TradingViewProvider
from src.data.providers.yahoo import YahooProvider

logger = logging.getLogger(__name__)

# ── Twelvedata config (exact v1 logic) ──────────────────────────────────────
TWELVEDATA_API_KEY = os.environ.get("TWELVEDATA_API_KEY", "")

TD_FREE_SYMBOLS = {
    "EURUSD=X", "JPY=X", "GBPUSD=X", "AUDUSD=X", "GC=F",
    "HYG", "TIP", "EEM",
}

TWELVEDATA_MAP: dict[str, str] = {
    "EURUSD=X": "EUR/USD",
    "JPY=X": "USD/JPY",
    "GBPUSD=X": "GBP/USD",
    "AUDUSD=X": "AUD/USD",
    "GC=F": "XAU/USD",
    "HYG": "HYG",
    "TIP": "TIP",
    "EEM": "EEM",
}

TD_INTERVAL: dict[str, str] = {"1d": "1day", "15m": "15min", "60m": "1h"}
TD_SIZE: dict[str, int] = {"1y": 365, "5d": 500, "60d": 500, "30d": 35}

# ── Finnhub config (exact v1 logic) ─────────────────────────────────────────
FINNHUB_API_KEY = os.environ.get("FINNHUB_API_KEY", "")

FINNHUB_QUOTE_MAP: dict[str, str] = {
    "^GSPC": "^GSPC",
    "^NDX": "^NDX",
    "^VIX": "^VIX",
    "SI=F": "SI1!",
    "BZ=F": "UKOIL",
    "CL=F": "USOIL",
    "HG=F": "HG1!",
}

# Provider instances
_tradingview = TradingViewProvider()
_yahoo = YahooProvider()
_stooq = StooqProvider()


def _fetch_twelvedata(symbol: str, interval: str, outputsize: int) -> list[OhlcBar]:
    """Fetch from Twelvedata — exact v1 logic from fetch_all.py lines 123-150."""
    if not TWELVEDATA_API_KEY or symbol not in TD_FREE_SYMBOLS:
        return []
    td_sym = TWELVEDATA_MAP.get(symbol, symbol)
    td_int = TD_INTERVAL.get(interval, interval)
    url = (
        f"https://api.twelvedata.com/time_series"
        f"?symbol={urllib.parse.quote(td_sym)}"
        f"&interval={td_int}&outputsize={outputsize}"
        f"&apikey={TWELVEDATA_API_KEY}"
    )
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=12) as r:
            d = json.loads(r.read())
        if d.get("status") == "error":
            logger.warning("Twelvedata %s: %s", td_sym, d.get("message", "unknown error"))
            return []
        rows: list[OhlcBar] = []
        for v in reversed(d.get("values", [])):
            try:
                rows.append(OhlcBar(
                    high=float(v["high"]),
                    low=float(v["low"]),
                    close=float(v["close"]),
                ))
            except (ValueError, KeyError):
                continue
        time.sleep(8)  # Free plan: max 8 req/min
        return rows
    except Exception as exc:
        logger.error("Twelvedata %s (%s): %s", td_sym, interval, exc)
        return []


def _fetch_finnhub_quote(symbol: str) -> OhlcBar | None:
    """Fetch real-time quote from Finnhub — exact v1 logic from lines 184-202."""
    if not FINNHUB_API_KEY:
        return None
    fh_sym = FINNHUB_QUOTE_MAP.get(symbol)
    if not fh_sym:
        return None
    url = (
        f"https://finnhub.io/api/v1/quote"
        f"?symbol={urllib.parse.quote(fh_sym)}&token={FINNHUB_API_KEY}"
    )
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=8) as r:
            d = json.loads(r.read())
        c, h, l = d.get("c", 0), d.get("h", 0), d.get("l", 0)
        if c and h and l:
            return OhlcBar(high=h, low=l, close=c)
        return None
    except Exception as exc:
        logger.error("Finnhub %s: %s", fh_sym, exc)
        return None


def fetch_prices(
    symbol: str,
    interval: str = "1d",
    range_or_size: str = "1y",
) -> list[OhlcBar]:
    """Route price fetching through providers with fallback order.

    Priority: TradingView -> Twelvedata (forex/gold) -> Stooq (daily) -> Yahoo.
    If the interval is daily, the last bar is optionally updated with a
    Finnhub real-time quote.

    Parameters
    ----------
    symbol : str
        Yahoo-style symbol.
    interval : str
        ``"1d"``, ``"15m"``, ``"60m"``.
    range_or_size : str
        Date range key: ``"1y"``, ``"5d"``, ``"30d"``.

    Returns
    -------
    list[OhlcBar]
        Bars ordered oldest to newest.
    """
    # 1. TradingView: real-time WebSocket (no API key, optional package)
    if _tradingview.is_available():
        if interval == "1d":
            rows = _tradingview.fetch_daily(symbol, range_or_size)
        else:
            rows = _tradingview.fetch_intraday(symbol, interval)
        if rows:
            logger.debug("TradingView served %d bars for %s", len(rows), symbol)
            return rows

    # 2. Twelvedata: forex + gold on free plan
    if TWELVEDATA_API_KEY and symbol in TD_FREE_SYMBOLS:
        rows = _fetch_twelvedata(symbol, interval, TD_SIZE.get(range_or_size, 365))
        if rows:
            if interval == "1d":
                qt = _fetch_finnhub_quote(symbol)
                if qt:
                    rows[-1] = qt
            return rows

    # 3. Stooq: daily data for all symbols (no key)
    if interval == "1d":
        rows = _stooq.fetch_stooq(symbol, range_or_size)
        if rows:
            qt = _fetch_finnhub_quote(symbol)
            if qt:
                rows[-1] = qt
            return rows

    # 4. Yahoo: fallback (intraday + anything Stooq doesn't cover)
    return _yahoo.fetch_yahoo(symbol, interval, range_or_size)
