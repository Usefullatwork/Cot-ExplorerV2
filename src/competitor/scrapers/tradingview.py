"""Parse TradingView RSS for recent trading ideas."""

from __future__ import annotations

import logging
import re
import urllib.request
import xml.etree.ElementTree as ET
from typing import Any

logger = logging.getLogger(__name__)

_RSS_URL = "https://www.tradingview.com/feed/"
_HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/120.0",
    "Accept": "application/rss+xml, application/xml, text/xml",
}

# Map common TradingView symbols to our instrument keys
_SYMBOL_MAP = {
    "FX:EURUSD": "EURUSD",
    "FX:USDJPY": "USDJPY",
    "FX:GBPUSD": "GBPUSD",
    "FX:AUDUSD": "AUDUSD",
    "OANDA:XAUUSD": "Gold",
    "COMEX:GC1!": "Gold",
    "OANDA:XAGUSD": "Silver",
    "COMEX:SI1!": "Silver",
    "NYMEX:CL1!": "WTI",
    "ICEEUR:BRN1!": "Brent",
    "SP:SPX": "SPX",
    "NASDAQ:NDX": "NAS100",
    "TVC:DXY": "DXY",
    "TVC:VIX": "VIX",
}


def _normalize_symbol(raw: str) -> str | None:
    """Try to map a TradingView symbol to a local instrument key."""
    raw_upper = raw.upper().strip()
    if raw_upper in _SYMBOL_MAP:
        return _SYMBOL_MAP[raw_upper]
    # Try just the ticker part
    ticker = raw_upper.split(":")[-1] if ":" in raw_upper else raw_upper
    for tv_sym, local_key in _SYMBOL_MAP.items():
        if ticker in tv_sym:
            return local_key
    return ticker if len(ticker) <= 8 else None


def _guess_direction(title: str) -> str:
    """Guess idea direction from the title text."""
    lower = title.lower()
    bull_words = ["long", "buy", "bullish", "breakout", "support", "bounce", "upside"]
    bear_words = ["short", "sell", "bearish", "breakdown", "resistance", "downside"]
    bull = sum(1 for w in bull_words if w in lower)
    bear = sum(1 for w in bear_words if w in lower)
    if bull > bear:
        return "bull"
    if bear > bull:
        return "bear"
    return "neutral"


def fetch_tv_ideas_rss() -> list[dict[str, Any]]:
    """Parse TradingView RSS feed for recent trading ideas.

    Returns a list of ``{"symbol": str, "direction": str, "title": str, "url": str}``.
    """
    try:
        req = urllib.request.Request(_RSS_URL, headers=_HEADERS)
        with urllib.request.urlopen(req, timeout=15) as resp:
            xml_bytes = resp.read()
    except Exception as exc:
        logger.warning("TradingView RSS fetch failed: %s", exc)
        return []

    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError as exc:
        logger.warning("TradingView RSS parse error: %s", exc)
        return []

    ideas: list[dict[str, Any]] = []
    for item in root.iter("item"):
        title_el = item.find("title")
        link_el = item.find("link")
        if title_el is None or link_el is None:
            continue
        title = title_el.text or ""
        url = link_el.text or ""

        # Try to extract symbol from category or title
        category_el = item.find("category")
        raw_sym = category_el.text if category_el is not None and category_el.text else ""
        symbol = _normalize_symbol(raw_sym)
        if not symbol:
            # Try from title — e.g. "EURUSD - Long Setup"
            match = re.match(r"([A-Z]{3,8})", title)
            symbol = match.group(1) if match else "UNKNOWN"

        ideas.append({
            "symbol": symbol,
            "direction": _guess_direction(title),
            "title": title[:200],
            "url": url,
        })

    logger.info("TradingView RSS: %d ideas", len(ideas))
    return ideas
