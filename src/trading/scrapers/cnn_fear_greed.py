#!/usr/bin/env python3
"""
cnn_fear_greed.py - CNN Fear & Greed Index scraper.

Fetches the current Fear & Greed Index score from CNN's internal API.
Score range: 0 (Extreme Fear) to 100 (Extreme Greed).

No API key required.
Zero external dependencies - stdlib only.
"""

import logging
import urllib.request
import json

log = logging.getLogger(__name__)


def fetch():
    """
    Fetch current Fear & Greed Index.

    Returns:
        Dict with "score" (float) and "rating" (str), or None on error.
    """
    url = "https://production.dataviz.cnn.io/index/fearandgreed/graphdata"
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/120.0",
        "Accept": "application/json, text/plain, */*",
        "Referer": "https://edition.cnn.com/markets/fear-and-greed",
        "Origin": "https://edition.cnn.com",
    })
    try:
        with urllib.request.urlopen(req, timeout=8) as r:
            d = json.loads(r.read())
        fg = d["fear_and_greed"]
        return {
            "score": round(fg["score"], 1),
            "rating": fg["rating"],
        }
    except Exception as e:
        log.error(f"Fear&Greed ERROR: {e}")
        return None


def classify(score):
    """
    Classify a Fear & Greed score into a regime.

    Returns:
        Dict with label, color, and position_guidance.
    """
    if score >= 75:
        return {"label": "Extreme Greed", "color": "bear", "guidance": "Reduce risk"}
    elif score >= 55:
        return {"label": "Greed", "color": "warn", "guidance": "Normal"}
    elif score >= 45:
        return {"label": "Neutral", "color": "neutral", "guidance": "Normal"}
    elif score >= 25:
        return {"label": "Fear", "color": "warn", "guidance": "Opportunity building"}
    else:
        return {"label": "Extreme Fear", "color": "bull", "guidance": "Contrarian buy zone"}


if __name__ == "__main__":
    result = fetch()
    if result:
        regime = classify(result["score"])
        log.info(f"Fear & Greed: {result['score']} ({result['rating']})")
        log.info(f"  Regime: {regime['label']} -> {regime['guidance']}")
