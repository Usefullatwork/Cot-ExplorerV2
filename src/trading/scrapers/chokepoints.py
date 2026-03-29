#!/usr/bin/env python3
"""
chokepoints.py - Static chokepoint definitions and risk assessment.

Defines major maritime chokepoints that affect commodity supply chains,
with throughput data, cargo types, and affected trading instruments.
Risk levels can be dynamically bumped based on news intel.

No API calls. Pure static data + risk logic.
"""

import logging
from typing import Optional

log = logging.getLogger(__name__)

CHOKEPOINTS: list[dict] = [
    {
        "name": "Strait of Hormuz",
        "lat": 26.56,
        "lon": 56.25,
        "throughput": "21 million barrels/day (~21% of global oil)",
        "cargo_types": ["crude oil", "LNG", "refined products"],
        "affected_instruments": ["OIL", "NATGAS", "GOLD", "USDJPY"],
        "risk_level": "medium",
        "keywords": ["hormuz", "iran", "persian gulf", "oman strait"],
    },
    {
        "name": "Suez Canal",
        "lat": 30.46,
        "lon": 32.34,
        "throughput": "12% of global trade, ~1M barrels/day oil",
        "cargo_types": ["crude oil", "containers", "LNG", "grain"],
        "affected_instruments": ["OIL", "GOLD", "EURUSD", "WHEAT"],
        "risk_level": "medium",
        "keywords": ["suez", "egypt canal", "red sea north"],
    },
    {
        "name": "Strait of Malacca",
        "lat": 2.5,
        "lon": 101.0,
        "throughput": "16 million barrels/day, 25% of global trade",
        "cargo_types": ["crude oil", "LNG", "containers", "palm oil"],
        "affected_instruments": ["OIL", "AUDUSD", "COPPER", "PALLADIUM"],
        "risk_level": "low",
        "keywords": ["malacca", "singapore strait", "south china sea"],
    },
    {
        "name": "Panama Canal",
        "lat": 9.08,
        "lon": -79.68,
        "throughput": "5% of global trade, ~0.9M barrels/day oil",
        "cargo_types": ["containers", "grain", "LNG", "copper"],
        "affected_instruments": ["COPPER", "WHEAT", "NATGAS", "SPX"],
        "risk_level": "low",
        "keywords": ["panama canal", "panama drought", "gatun lake"],
    },
    {
        "name": "Bab el-Mandeb",
        "lat": 12.58,
        "lon": 43.33,
        "throughput": "4.8 million barrels/day, Red Sea gateway",
        "cargo_types": ["crude oil", "containers", "LNG"],
        "affected_instruments": ["OIL", "GOLD", "EURUSD", "NATGAS"],
        "risk_level": "high",
        "keywords": ["bab el-mandeb", "yemen", "houthi", "red sea", "aden"],
    },
    {
        "name": "Turkish Straits",
        "lat": 41.12,
        "lon": 29.05,
        "throughput": "3 million barrels/day oil, Black Sea access",
        "cargo_types": ["crude oil", "grain", "coal", "iron ore"],
        "affected_instruments": ["OIL", "WHEAT", "GOLD", "EURUSD"],
        "risk_level": "low",
        "keywords": ["bosphorus", "dardanelles", "turkish strait", "black sea"],
    },
]


def get_chokepoints() -> list[dict]:
    """
    Return the list of chokepoint definitions.

    Returns:
        List of chokepoint dicts with: name, lat, lon, throughput,
        cargo_types, affected_instruments, risk_level.
    """
    # Return copies without internal keywords field
    return [
        {k: v for k, v in cp.items() if k != "keywords"}
        for cp in CHOKEPOINTS
    ]


def assess_risk(intel_articles: list[dict]) -> list[dict]:
    """
    Assess chokepoint risk levels based on news intelligence.

    Bumps risk_level up one tier (low->medium, medium->high) if any
    article title mentions a chokepoint's keywords.

    Args:
        intel_articles: List of article dicts (must have 'title' key).

    Returns:
        List of chokepoint dicts with updated risk_level values.
    """
    bump_map = {"low": "medium", "medium": "high", "high": "high"}
    titles_lower = " ".join(a.get("title", "").lower() for a in intel_articles)

    results: list[dict] = []
    for cp in CHOKEPOINTS:
        entry = {k: v for k, v in cp.items() if k != "keywords"}
        keywords = cp.get("keywords", [])

        mentioned = any(kw in titles_lower for kw in keywords)
        if mentioned:
            old_level = entry["risk_level"]
            entry["risk_level"] = bump_map.get(old_level, old_level)
            if entry["risk_level"] != old_level:
                log.info(f"Chokepoint {entry['name']}: risk bumped {old_level} -> {entry['risk_level']}")

        results.append(entry)

    return results


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    for cp in get_chokepoints():
        log.info(f"  {cp['name']}: {cp['risk_level']} — {cp['throughput']}")
