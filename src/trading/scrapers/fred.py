#!/usr/bin/env python3
"""
fred.py - FRED (Federal Reserve Economic Data) scraper.

Fetches economic data from the St. Louis Fed's FRED database.
Supports both CSV (no key) and JSON API (key required) endpoints.

Public domain data. No API key required for CSV endpoint.
Zero external dependencies - stdlib only.
"""

import logging
import urllib.request
import json
import os

log = logging.getLogger(__name__)

API_KEY = os.environ.get("FRED_API_KEY", "")


def fetch_csv(series_id: str) -> float | None:
    """
    Fetch the latest value from FRED CSV endpoint (no API key).

    Args:
        series_id: FRED series ID (e.g., "DGS10", "DTB3")

    Returns:
        Latest float value or None on error.
    """
    url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            lines = r.read().decode().strip().split("\n")
        for line in reversed(lines[1:]):
            parts = line.strip().split(",")
            if len(parts) == 2 and parts[1] not in (".", ""):
                return float(parts[1])
        return None
    except Exception as e:
        log.error(f"FRED CSV {series_id} ERROR: {e}")
        return None


def fetch_api(series_id: str, limit: int = 16) -> list[tuple[str, float]]:
    """
    Fetch observations from FRED JSON API (requires API key).

    Args:
        series_id: FRED series ID
        limit: Max observations to fetch

    Returns:
        List of (date_str, float_value) tuples, oldest first.
    """
    if not API_KEY:
        return []
    url = (f"https://api.stlouisfed.org/fred/series/observations"
           f"?series_id={series_id}&api_key={API_KEY}"
           f"&file_type=json&sort_order=desc&limit={limit}")
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=12) as r:
            d = json.loads(r.read())
        obs = []
        for o in d.get("observations", []):
            if o.get("value") not in (".", "", None):
                try:
                    obs.append((o["date"], float(o["value"])))
                except (ValueError, KeyError):
                    pass
        return list(reversed(obs))
    except Exception as e:
        log.error(f"FRED API {series_id} ERROR: {e}")
        return []


if __name__ == "__main__":
    for series, name in [("DGS10", "10Y Yield"), ("DTB3", "3M T-Bill")]:
        val = fetch_csv(series)
        if val:
            log.info(f"{name}: {val:.3f}%")
