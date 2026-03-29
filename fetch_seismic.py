#!/usr/bin/env python3
"""Thin wrapper for USGS seismic data. See src/trading/scrapers/seismic.py."""
import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.trading.scrapers.seismic import fetch  # noqa: E402

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    events = fetch()
    for ev in events:
        print(f"M{ev['mag']} {ev['region']}: {ev['place']}")
