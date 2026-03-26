"""Bot configuration — env vars, symbol map, lot parameters.

All settings have safe defaults so the bot can run in paper mode
without any environment variables set.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field

from src.core.enums import BrokerMode


@dataclass(frozen=True)
class BotSettings:
    """Immutable snapshot of bot configuration from environment."""

    api_key: str = ""
    account_id: str = ""
    broker_mode: BrokerMode = BrokerMode.PAPER
    max_positions: int = 3
    max_daily_trades: int = 10
    risk_pct: float = 0.01
    min_grade: str = "B"
    min_score: int = 6


def load_settings() -> BotSettings:
    """Load bot settings from environment variables with safe defaults."""
    mode_raw = os.getenv("BROKER_MODE", "PAPER").upper()
    try:
        broker_mode = BrokerMode(mode_raw)
    except ValueError:
        broker_mode = BrokerMode.PAPER

    return BotSettings(
        api_key=os.getenv("PEPPERSTONE_API_KEY", ""),
        account_id=os.getenv("PEPPERSTONE_ACCOUNT_ID", ""),
        broker_mode=broker_mode,
        max_positions=int(os.getenv("BOT_MAX_POSITIONS", "3")),
        max_daily_trades=int(os.getenv("BOT_MAX_DAILY_TRADES", "10")),
        risk_pct=float(os.getenv("BOT_RISK_PCT", "0.01")),
        min_grade=os.getenv("BOT_MIN_GRADE", "B"),
        min_score=int(os.getenv("BOT_MIN_SCORE", "6")),
    )


# ---------------------------------------------------------------------------
# Symbol map: our instrument key -> broker symbol name
# ---------------------------------------------------------------------------
SYMBOL_MAP: dict[str, str] = {
    "EURUSD": "EURUSD",
    "USDJPY": "USDJPY",
    "GBPUSD": "GBPUSD",
    "AUDUSD": "AUDUSD",
    "Gold": "XAUUSD",
    "Silver": "XAGUSD",
    "Brent": "UKOUSD",
    "WTI": "USOUSD",
    "SPX": "US500",
    "NAS100": "USTEC",
    "DXY": "USDX",
}


# ---------------------------------------------------------------------------
# Lot parameters per instrument
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class LotParams:
    """Minimum lot size and step for a broker instrument."""

    min_lot: float
    lot_step: float
    pip_size: float
    pip_value_per_lot: float  # USD value of 1 pip for 1 standard lot
    category: str  # "forex", "commodity", "index"


LOT_PARAMS: dict[str, LotParams] = {
    "EURUSD": LotParams(0.01, 0.01, 0.0001, 10.0, "forex"),
    "USDJPY": LotParams(0.01, 0.01, 0.01, 6.7, "forex"),
    "GBPUSD": LotParams(0.01, 0.01, 0.0001, 10.0, "forex"),
    "AUDUSD": LotParams(0.01, 0.01, 0.0001, 10.0, "forex"),
    "Gold": LotParams(0.01, 0.01, 0.01, 1.0, "commodity"),
    "Silver": LotParams(0.01, 0.01, 0.001, 50.0, "commodity"),
    "Brent": LotParams(0.01, 0.01, 0.01, 10.0, "commodity"),
    "WTI": LotParams(0.01, 0.01, 0.01, 10.0, "commodity"),
    "SPX": LotParams(0.01, 0.01, 0.1, 1.0, "index"),
    "NAS100": LotParams(0.01, 0.01, 0.1, 1.0, "index"),
}


# ---------------------------------------------------------------------------
# Trading sessions (CET hours)
# ---------------------------------------------------------------------------
SESSIONS: dict[str, tuple[int, int]] = {
    "london": (7, 12),        # 07:00-12:00 CET
    "ny_overlap": (13, 17),   # 13:00-17:00 CET
    "ny": (14, 21),           # 14:00-21:00 CET
    "asian": (23, 7),         # 23:00-07:00 CET (wraps midnight)
}

# Which sessions are allowed for each instrument class
SESSION_RULES: dict[str, list[str]] = {
    "A": ["london", "ny_overlap"],     # Forex: London + NY Overlap only
    "B": ["london", "ny"],             # Commodities: London + NY
    "C": ["ny"],                       # Indices: NY session only
}


# ---------------------------------------------------------------------------
# Correlated pairs (don't hold both simultaneously)
# ---------------------------------------------------------------------------
CORRELATED_PAIRS: dict[str, list[str]] = {
    "EURUSD": ["GBPUSD"],
    "GBPUSD": ["EURUSD"],
    "Gold": ["Silver"],
    "Silver": ["Gold"],
    "Brent": ["WTI"],
    "WTI": ["Brent"],
    "SPX": ["NAS100"],
    "NAS100": ["SPX"],
}


# ---------------------------------------------------------------------------
# Default spread in pips per instrument
# ---------------------------------------------------------------------------
DEFAULT_SPREADS: dict[str, float] = {
    "EURUSD": 1.2, "USDJPY": 1.4, "GBPUSD": 1.8, "AUDUSD": 1.6,
    "Gold": 3.0, "Silver": 3.5, "Brent": 4.0, "WTI": 4.0,
    "SPX": 5.0, "NAS100": 8.0, "DXY": 3.0, "VIX": 5.0,
}
