"""COT data factories for tests."""

from __future__ import annotations


def make_cot_data(
    spec_net: float = 5000,
    oi: float = 100000,
    change: float = 500,
) -> dict:
    """Create a COT data record for testing."""
    return {
        "spec_net": spec_net,
        "open_interest": oi,
        "change_spec_net": change,
        "spec_long": max(0, spec_net) + 20000,
        "spec_short": max(0, -spec_net) + 20000,
    }


# Standard instrument-to-COT mapping
COT_MAP = {
    "EURUSD": "euro fx",
    "Gold": "gold",
    "USDJPY": "japanese yen",
    "GBPUSD": "british pound",
    "Silver": "silver",
}


# Sample COT database keyed by lowercase market name
SAMPLE_COT_DB = {
    "euro fx": {
        "spec_net": 45000,
        "open_interest": 600000,
        "change_spec_net": 3000,
        "spec_long": 180000,
        "spec_short": 135000,
    },
    "gold": {
        "spec_net": -12000,
        "open_interest": 500000,
        "change_spec_net": -5000,
        "spec_long": 150000,
        "spec_short": 162000,
    },
    "japanese yen": {
        "spec_net": -80000,
        "open_interest": 200000,
        "change_spec_net": 2000,
        "spec_long": 30000,
        "spec_short": 110000,
    },
}
