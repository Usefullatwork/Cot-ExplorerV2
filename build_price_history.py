#!/usr/bin/env python3
"""Fetch weekly price history from Yahoo Finance.

Thin wrapper -- all logic lives in src.trading.core.build_price_history.
"""

import sys
from pathlib import Path

# Ensure project root is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from src.trading.core.build_price_history import main  # noqa: E402

if __name__ == "__main__":
    main()
