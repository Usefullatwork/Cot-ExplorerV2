#!/usr/bin/env python3
"""Thin wrapper for COMEX inventory data. See src/trading/scrapers/comex.py."""
import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.trading.scrapers.comex import fetch  # noqa: E402

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    data = fetch()
    for metal in ("gold", "silver", "copper"):
        m = data.get(metal)
        if m:
            print(f"{metal}: reg={m['registered']:,} elig={m['eligible']:,} cov={m['coverage_pct']}%")
    print(f"Stress index: {data['stress_index']}")
