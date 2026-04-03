#!/usr/bin/env python3
"""Thin wrapper — fetches oil & gas intelligence."""

import json
import logging

from src.trading.scrapers.oilgas_intel import fetch_oilgas_report

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

if __name__ == "__main__":
    report = fetch_oilgas_report()
    print(json.dumps(report, indent=2, ensure_ascii=False))
