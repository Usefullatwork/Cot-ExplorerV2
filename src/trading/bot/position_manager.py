"""Position management rules — SCALP EDGE exit logic.

Pure functions: inspect position state, return action dicts. No broker calls.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional


@dataclass(frozen=True)
class PositionAction:
    """A single action to execute on a position."""

    action: str  # partial_close, close, emergency_close
    reason: str
    close_pct: float = 1.0
    new_sl: Optional[float] = None


def check_t1_hit(
    position: dict[str, Any],
    current_price: float,
) -> Optional[PositionAction]:
    """Check if price has reached T1.

    If T1 is hit and no prior partial close, return an action to close
    50% and move the stop-loss to breakeven (entry price).

    Args:
        position: Dict with ``direction``, ``entry_price``, ``target_1``,
            ``t1_hit`` (bool).
        current_price: Current market price.

    Returns:
        PositionAction for partial close, or None.
    """
    if position.get("t1_hit", False):
        return None

    direction = position.get("direction", "bull")
    t1 = position.get("target_1", 0.0)
    entry = position.get("entry_price", 0.0)

    hit = (
        current_price >= t1 if direction == "bull" else current_price <= t1
    )
    if hit:
        return PositionAction(
            action="partial_close",
            reason="t1_hit",
            close_pct=0.5,
            new_sl=entry,
        )
    return None


def check_ema9_exit(
    position: dict[str, Any],
    ema9_15m: float,
    current_price: float,
) -> Optional[PositionAction]:
    """Check for EMA9 cross exit after T1 has been hit.

    Only triggers when T1 was already hit (position is in partial state).
    Bull: exit if price < EMA9.  Bear: exit if price > EMA9.

    Args:
        position: Dict with ``direction``, ``t1_hit`` (bool).
        ema9_15m: Current 15-minute EMA(9) value.
        current_price: Current market price.

    Returns:
        PositionAction for full close, or None.
    """
    if not position.get("t1_hit", False):
        return None

    direction = position.get("direction", "bull")
    if direction == "bull" and current_price < ema9_15m:
        return PositionAction(action="close", reason="ema9_cross")
    if direction == "bear" and current_price > ema9_15m:
        return PositionAction(action="close", reason="ema9_cross")
    return None


def check_candle_rules(
    position: dict[str, Any],
) -> Optional[PositionAction]:
    """Time-based exit rules using 5m candle count since entry.

    Rules:
      - 8 candles (40 min) without T1 hit: close 50%.
      - 16 candles (80 min) after a partial close: close remaining.

    Args:
        position: Dict with ``candles_since_entry`` (int), ``t1_hit`` (bool).

    Returns:
        PositionAction or None.
    """
    candles = position.get("candles_since_entry", 0)
    t1_hit = position.get("t1_hit", False)

    # 16-candle rule: after partial close, close the rest
    if t1_hit and candles >= 16:
        return PositionAction(
            action="close",
            reason="candle_16",
        )

    # 8-candle rule: no T1 yet, partial close
    if not t1_hit and candles >= 8:
        return PositionAction(
            action="partial_close",
            reason="candle_8",
            close_pct=0.5,
        )

    return None


def check_geo_spike(
    position: dict[str, Any],
    current_price: float,
    atr_d1: float,
) -> Optional[PositionAction]:
    """Emergency exit if price moved > 2x ATR(D1) against position.

    Args:
        position: Dict with ``direction``, ``entry_price``.
        current_price: Current market price.
        atr_d1: Daily ATR value.

    Returns:
        PositionAction for emergency close, or None.
    """
    if atr_d1 <= 0:
        return None

    entry = position.get("entry_price", 0.0)
    direction = position.get("direction", "bull")
    threshold = 2.0 * atr_d1

    if direction == "bull" and (entry - current_price) > threshold:
        return PositionAction(action="emergency_close", reason="geo_spike")
    if direction == "bear" and (current_price - entry) > threshold:
        return PositionAction(action="emergency_close", reason="geo_spike")

    return None


def manage_position(
    position: dict[str, Any],
    market_data: dict[str, Any],
) -> list[PositionAction]:
    """Run all position checks in priority order.

    Priority: geo_spike > t1_hit > ema9_exit > candle_rules.
    Returns a single-element list with the first triggered action,
    or an empty list if no action is needed.

    Args:
        position: Position state dict.
        market_data: Dict with ``price``, ``ema9_15m``, ``atr_d1``.
    """
    current_price = market_data.get("price", 0.0)
    ema9_15m = market_data.get("ema9_15m", 0.0)
    atr_d1 = market_data.get("atr_d1", 0.0)

    # 1. Geo spike — highest priority
    action = check_geo_spike(position, current_price, atr_d1)
    if action is not None:
        return [action]

    # 2. T1 hit
    action = check_t1_hit(position, current_price)
    if action is not None:
        return [action]

    # 3. EMA9 cross (only after T1)
    action = check_ema9_exit(position, ema9_15m, current_price)
    if action is not None:
        return [action]

    # 4. Candle rules
    action = check_candle_rules(position)
    if action is not None:
        return [action]

    return []
