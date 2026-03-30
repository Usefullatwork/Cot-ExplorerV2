#!/usr/bin/env python3
"""Thin wrapper for energy infrastructure data."""
import json
import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from src.trading.scrapers.energy_infra import MINES, PIPELINES, LNG_TERMINALS, SHIPPING_LANES

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print(f"Mines: {len(MINES)}, Pipelines: {len(PIPELINES)}, "
          f"LNG: {len(LNG_TERMINALS)}, Shipping: {len(SHIPPING_LANES)}")
