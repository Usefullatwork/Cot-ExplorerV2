"""VIX Term Structure scraper — spot, 9-day, and 3-month VIX indices.

Fetches CBOE VIX indices via Yahoo Finance (free, no key):
  ^VIX   — spot VIX
  ^VIX9D — 9-day VIX
  ^VIX3M — 3-month VIX

Computes contango/backwardation regime from the term structure.

All functions return empty/default on error (never crash).
"""

from __future__ import annotations

import json
import logging
import urllib.parse
import urllib.request
from enum import Enum
from typing import NamedTuple

log = logging.getLogger(__name__)


class VixRegime(str, Enum):
    """VIX term structure regime."""

    CONTANGO = "contango"       # VIX3M > VIX spot — normal, low fear
    BACKWARDATION = "backwardation"  # VIX spot > VIX3M — fear spike
    FLAT = "flat"               # Within 0.5 points


class VixTermStructure(NamedTuple):
    """VIX term structure data."""

    spot: float
    vix_9d: float
    vix_3m: float
    regime: VixRegime
    spread: float  # VIX3M - VIX spot


_SYMBOLS = {
    "spot": "^VIX",
    "vix_9d": "^VIX9D",
    "vix_3m": "^VIX3M",
}


def _fetch_quote(symbol: str) -> float | None:
    """Fetch the latest price for a Yahoo Finance symbol.

    Returns None on any error.
    """
    url = (
        f"https://query1.finance.yahoo.com/v8/finance/chart/"
        f"{urllib.parse.quote(symbol)}?interval=1d&range=5d"
    )
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0",
            "Accept": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            d = json.loads(r.read())
        closes = d["chart"]["result"][0]["indicators"]["quote"][0].get("close", [])
        # Return most recent non-None close
        for c in reversed(closes):
            if c is not None:
                return round(float(c), 2)
        return None
    except Exception as e:
        log.error("VIX fetch error %s: %s", symbol, e)
        return None


def classify_regime(spot: float, vix_3m: float, threshold: float = 0.5) -> VixRegime:
    """Classify VIX term structure regime.

    Args:
        spot: Current VIX spot price.
        vix_3m: 3-month VIX price.
        threshold: Points within which the structure is considered flat.

    Returns:
        VixRegime classification.
    """
    spread = vix_3m - spot
    if spread > threshold:
        return VixRegime.CONTANGO
    if spread < -threshold:
        return VixRegime.BACKWARDATION
    return VixRegime.FLAT


def fetch_vix_term_structure() -> VixTermStructure | None:
    """Fetch VIX spot, 9D, and 3M and return term structure.

    Returns None if spot or 3M fetch fails.
    """
    spot = _fetch_quote(_SYMBOLS["spot"])
    vix_9d = _fetch_quote(_SYMBOLS["vix_9d"])
    vix_3m = _fetch_quote(_SYMBOLS["vix_3m"])

    if spot is None or vix_3m is None:
        log.error("VIX term structure: missing spot or 3M data")
        return None

    regime = classify_regime(spot, vix_3m)
    spread = round(vix_3m - spot, 2)

    return VixTermStructure(
        spot=spot,
        vix_9d=vix_9d or 0.0,
        vix_3m=vix_3m,
        regime=regime,
        spread=spread,
    )


def to_dict(ts: VixTermStructure | None) -> dict:
    """Convert VixTermStructure to JSON-serializable dict.

    Returns a safe default if ts is None.
    """
    if ts is None:
        return {
            "spot": 0.0,
            "vix_9d": 0.0,
            "vix_3m": 0.0,
            "regime": "flat",
            "spread": 0.0,
        }
    return {
        "spot": ts.spot,
        "vix_9d": ts.vix_9d,
        "vix_3m": ts.vix_3m,
        "regime": ts.regime.value,
        "spread": ts.spread,
    }
