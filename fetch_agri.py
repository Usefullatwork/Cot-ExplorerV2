#!/usr/bin/env python3
"""Thin wrapper — fetches agriculture weather + COT intelligence."""

import json
import logging

from src.trading.scrapers.agri_weather import fetch_agri_report

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

if __name__ == "__main__":
    report = fetch_agri_report()
    print(json.dumps(report, indent=2, ensure_ascii=False))
