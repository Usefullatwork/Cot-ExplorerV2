#!/usr/bin/env python3
"""Thin wrapper — fetches shipping intelligence (Baltic indices + routes)."""

import json
import logging

from src.trading.scrapers.shipping_intel import fetch_shipping_report

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

if __name__ == "__main__":
    report = fetch_shipping_report()
    print(json.dumps(report, indent=2, ensure_ascii=False))
