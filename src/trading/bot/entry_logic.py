"""Entry confirmation logic — SCALP EDGE rules.

All functions are pure: they accept data and return booleans or
tuples, with no side effects or broker calls.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class EntryResult:
    """Outcome of the entry evaluation."""

    passed: bool
    reason: str


def check_zone_proximity(
    price: float,
    entry_level: float,
    atr_15m: float,
    weight: int = 3,
) -> bool:
    """Check whether *price* is close enough to *entry_level*.

    Tolerance scales with the level weight:
      - weight <= 1:  0.30 x ATR(15m)
      - weight == 2:  0.35 x ATR(15m)
      - weight >= 3:  0.45 x ATR(15m)

    Args:
        price: Current market price.
        entry_level: Target entry price from the setup.
        atr_15m: 15-minute ATR value.
        weight: HTF weight of the entry level (1-5).

    Returns:
        True if price is within the tolerance band of entry_level.
    """
    if atr_15m <= 0:
        return False

    if weight <= 1:
        factor = 0.30
    elif weight == 2:
        factor = 0.35
    else:
        factor = 0.45

    tolerance = atr_15m * factor
    return abs(price - entry_level) <= tolerance


def check_candle_confirmation(
    candles_5m: list[dict[str, float]],
    direction: str,
    max_candles: int = 6,
) -> bool:
    """Check whether a 5m candle has closed in the correct direction.

    Each candle dict must have ``open`` and ``close`` keys.

    Args:
        candles_5m: Recent 5-minute candles (newest first), each with
            ``open`` and ``close`` float values.
        direction: ``"bull"`` or ``"bear"``.
        max_candles: Maximum number of recent candles to check.

    Returns:
        True if at least one candle within the window confirms direction.
    """
    for candle in candles_5m[:max_candles]:
        c_open = candle.get("open", 0.0)
        c_close = candle.get("close", 0.0)
        if direction == "bull" and c_close > c_open:
            return True
        if direction == "bear" and c_close < c_open:
            return True
    return False


def check_ema9_filter(
    price: float,
    ema9_15m: float,
    direction: str,
) -> bool:
    """Check whether price is on the correct side of 15m EMA9.

    Args:
        price: Current market price.
        ema9_15m: Current 15-minute EMA(9) value.
        direction: ``"bull"`` or ``"bear"``.

    Returns:
        True if price is above EMA9 for bull, below for bear.
    """
    if direction == "bull":
        return price > ema9_15m
    return price < ema9_15m


def evaluate_entry(
    signal: dict[str, Any],
    market_data: dict[str, Any],
    bot_config: dict[str, Any],
) -> EntryResult:
    """Orchestrate all entry checks for a candidate signal.

    Checks run in priority order (fastest rejection first):
      1. Kill switch active?
      2. Max open positions reached?
      3. Zone proximity (price near entry level)
      4. Candle confirmation (5m candle in direction)
      5. EMA9 filter (price on correct side of 15m EMA9)

    Args:
        signal: Dict with keys ``entry_price``, ``direction``, ``grade``,
            ``score``, ``instrument``.
        market_data: Dict with keys ``price``, ``atr_15m``, ``ema9_15m``,
            ``candles_5m``, ``open_positions``.
        bot_config: Dict with keys ``kill_switch_active``, ``max_positions``,
            ``min_grade``, ``min_score``.

    Returns:
        EntryResult with ``passed`` and ``reason``.
    """
    # 1. Kill switch
    if bot_config.get("kill_switch_active", False):
        return EntryResult(passed=False, reason="kill_switch_active")

    # 2. Max positions
    open_positions = market_data.get("open_positions", 0)
    max_positions = bot_config.get("max_positions", 3)
    if open_positions >= max_positions:
        return EntryResult(passed=False, reason="max_positions_reached")

    # 3. Grade / score gate
    grade_order = {"A+": 4, "A": 3, "B": 2, "C": 1}
    signal_grade_rank = grade_order.get(signal.get("grade", "C"), 0)
    min_grade_rank = grade_order.get(bot_config.get("min_grade", "B"), 2)
    if signal_grade_rank < min_grade_rank:
        return EntryResult(passed=False, reason="grade_below_minimum")

    signal_score = signal.get("score", 0)
    min_score = bot_config.get("min_score", 6)
    if signal_score < min_score:
        return EntryResult(passed=False, reason="score_below_minimum")

    # 4. Zone proximity
    entry_level = signal.get("entry_price", 0.0)
    price = market_data.get("price", 0.0)
    atr_15m = market_data.get("atr_15m", 0.0)
    entry_weight = signal.get("entry_weight", 3)
    if not check_zone_proximity(price, entry_level, atr_15m, entry_weight):
        return EntryResult(passed=False, reason="price_not_at_zone")

    # 5. Candle confirmation
    direction = signal.get("direction", "bull")
    candles_5m = market_data.get("candles_5m", [])
    if not check_candle_confirmation(candles_5m, direction):
        return EntryResult(passed=False, reason="no_candle_confirmation")

    # 6. EMA9 filter
    ema9_15m = market_data.get("ema9_15m", 0.0)
    if not check_ema9_filter(price, ema9_15m, direction):
        return EntryResult(passed=False, reason="ema9_filter_failed")

    return EntryResult(passed=True, reason="all_checks_passed")
