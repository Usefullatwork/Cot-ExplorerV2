#!/usr/bin/env python3
"""Thin wrapper for crypto market data."""
import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from src.trading.scrapers.crypto import fetch_crypto_market, fetch_fear_greed

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    data = fetch_crypto_market()
    if data:
        for c in data.get("coins", []):
            print(f"{c['symbol']}: ${c['price']:.2f} ({c.get('change_24h', 0):.1f}%)")
    fg = fetch_fear_greed()
    if fg:
        print(f"Fear & Greed: {fg.get('value', '?')} — {fg.get('label', '?')}")
