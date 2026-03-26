"""Centralised price-fetching config and multi-source OHLC fetcher.

Holds all instrument/config constants previously inlined in root fetch_all.py
and delegates to the existing scrapers in src/trading/scrapers/.

Priority chain: Twelvedata -> Stooq -> Yahoo, with Finnhub realtime overlay.
"""

from __future__ import annotations

import logging
import os

from src.trading.scrapers import finnhub, stooq, twelvedata, yahoo_finance

log = logging.getLogger(__name__)

# ── API keys ──────────────────────────────────────────────────────
TWELVEDATA_API_KEY = os.environ.get("TWELVEDATA_API_KEY", "")
FINNHUB_API_KEY = os.environ.get("FINNHUB_API_KEY", "")

# ── Twelvedata config ─────────────────────────────────────────────
TD_FREE_SYMBOLS = {"EURUSD=X", "JPY=X", "GBPUSD=X", "AUDUSD=X", "GC=F", "HYG", "TIP", "EEM"}
TWELVEDATA_MAP = {
    "EURUSD=X": "EUR/USD",
    "JPY=X": "USD/JPY",
    "GBPUSD=X": "GBP/USD",
    "AUDUSD=X": "AUD/USD",
    "GC=F": "XAU/USD",
    "HYG": "HYG",
    "TIP": "TIP",
    "EEM": "EEM",
}
TD_INTERVAL = {"1d": "1day", "15m": "15min", "60m": "1h"}
TD_SIZE = {"1y": 365, "5d": 500, "60d": 500, "30d": 35}

# ── Stooq config ──────────────────────────────────────────────────
STOOQ_MAP = {
    "EURUSD=X": "eurusd",
    "JPY=X": "usdjpy",
    "GBPUSD=X": "gbpusd",
    "AUDUSD=X": "audusd",
    "GC=F": "xauusd",
    "SI=F": "xagusd",
    "BZ=F": "co.f",
    "CL=F": "cl.f",
    "^GSPC": "^spx",
    "^NDX": "^ndx",
    "^VIX": "^vix",
    "DX-Y.NYB": "dxy.f",
    "HG=F": "hg.f",
    "HYG": "hyg.us",
    "TIP": "tip.us",
    "EEM": "eem.us",
}
STOOQ_DAYS = {"1y": 400, "30d": 35, "5d": 7}

# ── Finnhub config ────────────────────────────────────────────────
FINNHUB_QUOTE_MAP = {
    "^GSPC": "^GSPC",
    "^NDX": "^NDX",
    "^VIX": "^VIX",
    "SI=F": "SI1!",
    "BZ=F": "UKOIL",
    "CL=F": "USOIL",
    "HG=F": "HG1!",
}

# ── Macro symbols (for fetch_macro_indicators in sentiment.py) ───
MACRO_SYMBOLS = {
    "HYG": "HYG",
    "TIP": "TIP",
    "TNX": "^TNX",
    "IRX": "^IRX",
    "Copper": "HG=F",
    "EEM": "EEM",
}

# ── Instrument definitions ────────────────────────────────────────
INSTRUMENTS = [
    {
        "key": "EURUSD",
        "navn": "EUR/USD",
        "symbol": "EURUSD=X",
        "label": "Valuta",
        "kat": "valuta",
        "klasse": "A",
        "session": "London 08:00-12:00 CET",
    },
    {
        "key": "USDJPY",
        "navn": "USD/JPY",
        "symbol": "JPY=X",
        "label": "Valuta",
        "kat": "valuta",
        "klasse": "A",
        "session": "London 08:00-12:00 CET",
    },
    {
        "key": "GBPUSD",
        "navn": "GBP/USD",
        "symbol": "GBPUSD=X",
        "label": "Valuta",
        "kat": "valuta",
        "klasse": "A",
        "session": "London 08:00-12:00 CET",
    },
    {
        "key": "AUDUSD",
        "navn": "AUD/USD",
        "symbol": "AUDUSD=X",
        "label": "Valuta",
        "kat": "valuta",
        "klasse": "A",
        "session": "London 08:00-12:00 CET",
    },
    {
        "key": "Gold",
        "navn": "Gull",
        "symbol": "GC=F",
        "label": "Ravare",
        "kat": "ravarer",
        "klasse": "B",
        "session": "London Fix 10:30 / NY Fix 15:00 CET",
    },
    {
        "key": "Silver",
        "navn": "Solv",
        "symbol": "SI=F",
        "label": "Ravare",
        "kat": "ravarer",
        "klasse": "B",
        "session": "London Fix 10:30 / NY Fix 15:00 CET",
    },
    {
        "key": "Brent",
        "navn": "Brent",
        "symbol": "BZ=F",
        "label": "Ravare",
        "kat": "ravarer",
        "klasse": "B",
        "session": "London Fix 10:30 / NY Fix 15:00 CET",
    },
    {
        "key": "WTI",
        "navn": "WTI",
        "symbol": "CL=F",
        "label": "Ravare",
        "kat": "ravarer",
        "klasse": "B",
        "session": "London Fix 10:30 / NY Fix 15:00 CET",
    },
    {
        "key": "SPX",
        "navn": "S&P 500",
        "symbol": "^GSPC",
        "label": "Aksjer",
        "kat": "aksjer",
        "klasse": "C",
        "session": "NY Open 14:30-17:00 CET",
    },
    {
        "key": "NAS100",
        "navn": "Nasdaq",
        "symbol": "^NDX",
        "label": "Aksjer",
        "kat": "aksjer",
        "klasse": "C",
        "session": "NY Open 14:30-17:00 CET",
    },
    {
        "key": "VIX",
        "navn": "VIX",
        "symbol": "^VIX",
        "label": "Vol",
        "kat": "aksjer",
        "klasse": "C",
        "session": "NY Open 14:30-17:00 CET",
    },
    {
        "key": "DXY",
        "navn": "DXY",
        "symbol": "DX-Y.NYB",
        "label": "Valuta",
        "kat": "valuta",
        "klasse": "A",
        "session": "London 08:00-12:00 CET",
    },
]

# ── News confirms map (instrument -> (risk_on_dir, risk_off_dir)) ─
NEWS_CONFIRMS_MAP = {
    "SPX": ("bull", "bear"),
    "NAS100": ("bull", "bear"),
    "Gold": ("bear", "bull"),
    "Silver": ("bear", "bull"),
    "EURUSD": ("bull", "bear"),
    "GBPUSD": ("bull", "bear"),
    "AUDUSD": ("bull", "bear"),
    "USDJPY": ("bull", "bear"),
    "DXY": ("bear", "bull"),
    "Brent": (None, None),
    "WTI": (None, None),
    "VIX": ("bear", "bull"),
}

# ── COT market mapping ────────────────────────────────────────────
COT_MAP = {
    "EURUSD": "euro fx",
    "USDJPY": "japanese yen",
    "GBPUSD": "british pound",
    "Gold": "gold",
    "Silver": "silver",
    "Brent": "crude oil, light sweet",
    "WTI": "crude oil, light sweet",
    "SPX": "s&p 500 consolidated",
    "NAS100": "nasdaq mini",
    "DXY": "usd index",
}


# ══════════════════════════════════════════════════════════════════
# Multi-source price fetcher (delegates to scrapers)
# ══════════════════════════════════════════════════════════════════


def _finnhub_overlay(symbol: str) -> tuple[float, float, float] | None:
    """Get Finnhub realtime quote if available for this symbol."""
    if not FINNHUB_API_KEY or symbol not in FINNHUB_QUOTE_MAP:
        return None
    return finnhub.fetch_quote(symbol)


def fetch_prices(
    symbol: str,
    interval: str,
    range_or_size: str,
) -> list[tuple[float, float, float]]:
    """Fetch OHLC bars with priority: Twelvedata -> Stooq -> Yahoo.

    Overlays last bar with Finnhub realtime quote when on daily interval.

    Args:
        symbol: Yahoo-style symbol (e.g. "EURUSD=X", "GC=F", "^GSPC")
        interval: "1d", "15m", or "60m"
        range_or_size: "1y", "5d", "60d", "30d"

    Returns:
        List of (high, low, close) tuples, oldest first. Empty on error.
    """
    # 1. Try Twelvedata (forex/gold — free-tier symbols only)
    if TWELVEDATA_API_KEY and symbol in TD_FREE_SYMBOLS:
        outputsize = TD_SIZE.get(range_or_size, 365)
        rows = twelvedata.fetch_ohlc(symbol, interval, outputsize)
        if rows:
            if interval == "1d":
                qt = _finnhub_overlay(symbol)
                if qt:
                    rows[-1] = qt
            return rows

    # 2. Try Stooq (daily only — no intraday)
    if interval == "1d":
        rows = stooq.fetch_ohlc(symbol, range_or_size)
        if rows:
            qt = _finnhub_overlay(symbol)
            if qt:
                rows[-1] = qt
            return rows

    # 3. Fallback to Yahoo Finance
    return yahoo_finance.fetch_ohlc(symbol, interval, range_or_size)
