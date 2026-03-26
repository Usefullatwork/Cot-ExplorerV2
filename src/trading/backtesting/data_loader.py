"""
Data loader for backtesting framework.

Loads and merges price + COT data from the cot-explorer data directory.
"""

import json
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from .models import Bar


class DataLoader:
    """Load and merge price + COT data from the cot-explorer data directory."""

    # COT symbol -> price key mapping (from cot_map.json)
    DEFAULT_COT_MAP = {
        "099741": "eurusd",
        "096742": "usdjpy",
        "092741": "gbpusd",
        "232741": "audusd",
        "088691": "gold",
        "084691": "silver",
        "067651": "wti",
        "023651": "brent",
        "133741": "spx",
        "209742": "nas100",
        "098662": "dxy",
        "002602": "corn",
        "001602": "wheat",
        "005602": "soybean",
        "083731": "sugar",
        "073732": "coffee",
        "080732": "cocoa",
    }

    # Reverse: price key -> list of COT symbols
    PRICE_TO_COT = {}
    for cot_sym, price_key in DEFAULT_COT_MAP.items():
        PRICE_TO_COT.setdefault(price_key, []).append(cot_sym)

    # Report type preference order
    REPORT_PREF = ["tff", "legacy", "disaggregated", "supplemental"]

    def __init__(self, data_dir: str):
        self.data_dir = data_dir
        self.prices_dir = os.path.join(data_dir, "prices")
        self.timeseries_dir = os.path.join(data_dir, "timeseries")
        self.cot_map = self._load_cot_map()

    def _load_cot_map(self) -> Dict[str, str]:
        path = os.path.join(self.prices_dir, "cot_map.json")
        if os.path.exists(path):
            with open(path, "r") as f:
                return json.load(f)
        return dict(self.DEFAULT_COT_MAP)

    def available_instruments(self) -> List[str]:
        """List instruments that have price data."""
        instruments = []
        if os.path.isdir(self.prices_dir):
            for fname in os.listdir(self.prices_dir):
                if fname.endswith(".json") and fname != "cot_map.json":
                    instruments.append(fname.replace(".json", ""))
        return sorted(instruments)

    def load_prices(self, instrument: str) -> List[Dict]:
        """Load price data: returns list of {date, price}."""
        path = os.path.join(self.prices_dir, f"{instrument}.json")
        if not os.path.exists(path):
            return []
        with open(path, "r") as f:
            data = json.load(f)
        return data.get("data", [])

    def load_cot(self, instrument: str) -> List[Dict]:
        """Load COT timeseries for an instrument. Tries preferred report types."""
        cot_symbols = self.PRICE_TO_COT.get(instrument, [])
        if not cot_symbols:
            # Try reverse lookup from loaded map
            rev = {}
            for k, v in self.cot_map.items():
                rev.setdefault(v, []).append(k)
            cot_symbols = rev.get(instrument, [])

        for cot_sym in cot_symbols:
            for report in self.REPORT_PREF:
                path = os.path.join(self.timeseries_dir, f"{cot_sym}_{report}.json")
                if os.path.exists(path):
                    with open(path, "r") as f:
                        data = json.load(f)
                    return data.get("data", [])
        return []

    def load_merged(
        self,
        instrument: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> List[Bar]:
        """Load and merge price + COT data for an instrument.

        Price data is weekly (each date = one bar).
        COT data is also weekly, aligned by nearest date.
        Returns chronologically sorted list of Bar objects.
        """
        prices = self.load_prices(instrument)
        cot_data = self.load_cot(instrument)

        # Build COT lookup by date
        cot_by_date: Dict[str, Dict] = {}
        for row in cot_data:
            cot_by_date[row["date"]] = row

        bars = []
        last_cot = None

        for row in prices:
            date_str = row["date"]
            price = row["price"]

            # Date filtering
            if start_date and date_str < start_date:
                continue
            if end_date and date_str > end_date:
                continue

            # Find matching COT data (exact date or nearest previous)
            cot = cot_by_date.get(date_str)
            if cot is None:
                # Find nearest previous COT date (within 10 days)
                d = datetime.strptime(date_str, "%Y-%m-%d")
                for offset in range(1, 11):
                    candidate = (d - timedelta(days=offset)).strftime("%Y-%m-%d")
                    if candidate in cot_by_date:
                        cot = cot_by_date[candidate]
                        break

            if cot is None:
                cot = last_cot  # carry forward
            else:
                last_cot = cot

            bar = Bar(
                date=date_str,
                instrument=instrument,
                price=price,
                spec_net=cot["spec_net"] if cot else None,
                spec_long=cot["spec_long"] if cot else None,
                spec_short=cot["spec_short"] if cot else None,
                open_interest=cot["oi"] if cot else None,
            )
            bars.append(bar)

        return bars
