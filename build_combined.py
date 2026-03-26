#!/usr/bin/env python3
"""Build combined latest.json from COT reports.

Thin wrapper -- all logic lives in src.trading.core.build_combined.
"""

import sys
from pathlib import Path

# Ensure project root is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from src.trading.core.build_combined import main  # noqa: E402

if __name__ == "__main__":
    main()
