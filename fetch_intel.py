#!/usr/bin/env python3
"""Thin wrapper for geo-intel news feed. See src/trading/scrapers/intel_feed.py."""
import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.trading.scrapers.intel_feed import fetch  # noqa: E402

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    articles = fetch(max_per_category=5)
    for art in articles:
        print(f"[{art['category']}] {art['title'][:80]} — {art['source']}")
