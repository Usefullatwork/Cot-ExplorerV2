"""Scrape public community sentiment from Myfxbook."""

from __future__ import annotations

import json
import logging
import re
import urllib.request
from typing import Any

logger = logging.getLogger(__name__)

_URL = "https://www.myfxbook.com/community/outlook"
_HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/120.0",
    "Accept": "text/html,application/xhtml+xml",
}


def fetch_myfxbook_outlook() -> dict[str, dict[str, float]]:
    """Scrape Myfxbook community outlook page for public sentiment.

    Returns a dict of ``instrument -> {"long_pct": float, "short_pct": float}``.
    Falls back to an empty dict on any failure.
    """
    try:
        req = urllib.request.Request(_URL, headers=_HEADERS)
        with urllib.request.urlopen(req, timeout=15) as resp:
            html = resp.read().decode(errors="replace")
    except Exception as exc:
        logger.warning("Myfxbook fetch failed: %s", exc)
        return {}

    # Myfxbook embeds outlook data in a JS variable on the page.
    # Pattern: var defined in script tag containing JSON-like structures.
    results: dict[str, dict[str, float]] = {}

    # Look for rows like:  "EURUSD"  ...  longPercentage: 72.3  shortPercentage: 27.7
    # The page renders a table — we parse the raw text for percentage patterns.
    pattern = re.compile(
        r'(?P<pair>[A-Z]{6})\s*</a>.*?'
        r'(?P<long>\d+\.?\d*)%.*?'
        r'(?P<short>\d+\.?\d*)%',
        re.DOTALL,
    )
    for m in pattern.finditer(html):
        pair = m.group("pair")
        try:
            long_pct = float(m.group("long"))
            short_pct = float(m.group("short"))
            results[pair] = {"long_pct": long_pct, "short_pct": short_pct}
        except (ValueError, TypeError):
            continue

    logger.info("Myfxbook outlook: %d pairs", len(results))
    return results
