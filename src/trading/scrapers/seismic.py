#!/usr/bin/env python3
"""
seismic.py - USGS earthquake data scraper for mining regions.

Fetches M4.5+ earthquakes from the past week and filters for
10 major mining regions that can affect commodity supply chains.

Public domain data. No API key required.
Zero external dependencies - stdlib only.
"""

import json
import logging
import urllib.request
from typing import Optional

log = logging.getLogger(__name__)

FEED_URL = "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/4.5_week.geojson"

# Mining regions: (name, min_lat, max_lat, min_lon, max_lon)
MINING_REGIONS: list[tuple[str, float, float, float, float]] = [
    ("Chile/Peru", -56.0, -5.0, -82.0, -66.0),
    ("DRC/Zambia", -18.0, 6.0, 21.0, 32.0),
    ("Indonesia/Papua", -11.0, 6.0, 95.0, 141.0),
    ("Australia", -44.0, -10.0, 112.0, 154.0),
    ("South Africa", -35.0, -22.0, 16.0, 33.0),
    ("Canada", 48.0, 72.0, -141.0, -52.0),
    ("Russia/Siberia", 50.0, 75.0, 60.0, 180.0),
    ("Brazil", -34.0, 6.0, -74.0, -35.0),
    ("Philippines", 5.0, 21.0, 116.0, 127.0),
    ("Mexico", 14.0, 33.0, -118.0, -86.0),
]


def _classify_region(lat: float, lon: float) -> Optional[str]:
    """Return the mining region name if coords fall within one, else None."""
    for name, min_lat, max_lat, min_lon, max_lon in MINING_REGIONS:
        if min_lat <= lat <= max_lat and min_lon <= lon <= max_lon:
            return name
    return None


def fetch() -> list[dict]:
    """
    Fetch M4.5+ earthquakes from the past week, filtered to mining regions.

    Returns:
        List of SeismicEvent dicts with: id, mag, lat, lon, depth_km,
        place, time, region, url.  Empty list on error.
    """
    req = urllib.request.Request(
        FEED_URL,
        headers={"User-Agent": "Mozilla/5.0 Cot-ExplorerV2/2.0"},
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            data = json.loads(r.read())
    except Exception as e:
        log.error(f"Seismic fetch ERROR: {e}")
        return []

    events: list[dict] = []
    for feature in data.get("features", []):
        props = feature.get("properties", {})
        coords = feature.get("geometry", {}).get("coordinates", [0, 0, 0])
        lon, lat, depth = coords[0], coords[1], coords[2]

        region = _classify_region(lat, lon)
        if region is None:
            continue

        events.append({
            "id": feature.get("id", ""),
            "mag": props.get("mag", 0.0),
            "lat": lat,
            "lon": lon,
            "depth_km": depth,
            "place": props.get("place", ""),
            "time": props.get("time", 0),
            "region": region,
            "url": props.get("url", ""),
        })

    log.info(f"Seismic: {len(events)} mining-region events from {len(data.get('features', []))} total")
    return events


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    results = fetch()
    for ev in results:
        log.info(f"  M{ev['mag']} {ev['region']}: {ev['place']}")
