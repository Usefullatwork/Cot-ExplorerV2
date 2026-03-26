#!/usr/bin/env python3
"""Thin wrapper for backward compatibility. See src/trading/core/fetch_prices.py."""
import logging
import sys
import os

# Ensure project root is on the path so `src.` imports work
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.trading.core.fetch_prices import main  # noqa: E402

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )
    main()
