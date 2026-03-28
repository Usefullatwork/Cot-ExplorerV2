"""Position management rules — SCALP EDGE exit logic.

Pure functions: inspect position state, return action dicts. No broker calls.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from src.trading.bot.config import LOT_PARAMS

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ATR_TRAIL_MULTIPLIER: float = 1.5
BREAKEVEN_BUFFER_PIPS: float = 2.0
PIP_SIZE_DEFAULT: float = 0.0001  # Override per instrument if needed


def get_pip_size(instrument: str) -> float:
    """Look up pip_size from LOT_PARAMS, falling back to PIP_SIZE_DEFAULT."""
    params = LOT_PARAMS.get(instrument)
    if params is not None:
        return params.pip_size
    return PIP_SIZE_DEFAULT

# Triple TP allocation
TP_T1_PCT: float = 0.50  # 50% at 1R
TP_T2_PCT: float = 0.30  # 30% at 2R
TP_T3_PCT: float = 0.20  # 20% at 3R

# Session boundaries (CET hours)
SCALP_SESSION_END_CET: int = 21


@dataclass(frozen=True)
class PositionAction:
    """A single action to execute on a position."""

    action: str  # modify_sl, partial_close, close, emergency_close
    reason: str
    close_pct: float = 1.0
    new_sl: Optional[float] = None


# ---------------------------------------------------------------------------
# Existing checks (unchanged)
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# New checks — professional-grade exit logic
# ---------------------------------------------------------------------------


def check_atr_trailing(
    position: dict[str, Any],
    current_price: float,
    atr_value: float,
) -> Optional[PositionAction]:
    """ATR-based trailing stop that activates after T1 is hit.

    Trail distance is ``ATR_TRAIL_MULTIPLIER * atr_value`` (default 1.5x ATR).
    For longs the stop only ratchets upward; for shorts it only ratchets
    downward — the stop never retreats.

    Args:
        position: Dict with ``direction``, ``stop_loss``, ``t1_hit`` (bool).
        current_price: Current market price.
        atr_value: Current ATR value (same timeframe as trade).

    Returns:
        PositionAction with ``modify_sl`` if the trailing stop should move,
        or None if no adjustment is needed.
    """
    if not position.get("t1_hit", False):
        return None
    if atr_value <= 0:
        return None

    direction = position.get("direction", "bull")
    current_sl = position.get("stop_loss", 0.0)
    trail_distance = ATR_TRAIL_MULTIPLIER * atr_value

    if direction == "bull":
        new_sl = current_price - trail_distance
        # Only move the stop UP (never retreat)
        if new_sl > current_sl:
            return PositionAction(
                action="modify_sl",
                reason="atr_trailing",
                new_sl=new_sl,
            )
    else:
        new_sl = current_price + trail_distance
        # Only move the stop DOWN (never retreat)
        if current_sl == 0.0 or new_sl < current_sl:
            return PositionAction(
                action="modify_sl",
                reason="atr_trailing",
                new_sl=new_sl,
            )

    return None


def check_breakeven(
    position: dict[str, Any],
    current_price: float,
) -> Optional[PositionAction]:
    """Move stop-loss to breakeven + buffer when price reaches 50% of T1.

    Triggers once: when price has moved 50% of the distance from entry to T1,
    the SL is moved to entry + 2 pips (long) or entry - 2 pips (short).
    Will not re-trigger if the SL is already at or beyond entry.

    Args:
        position: Dict with ``direction``, ``entry_price``, ``target_1``,
            ``stop_loss``, ``pip_size`` (optional, defaults to 0.0001).
        current_price: Current market price.

    Returns:
        PositionAction with ``modify_sl`` for breakeven move, or None.
    """
    direction = position.get("direction", "bull")
    entry = position.get("entry_price", 0.0)
    t1 = position.get("target_1", 0.0)
    current_sl = position.get("stop_loss", 0.0)
    instrument = position.get("instrument", "")
    pip_size = position.get("pip_size", get_pip_size(instrument))

    # Already at or past breakeven — do not re-trigger
    if direction == "bull" and current_sl >= entry:
        return None
    if direction == "bear" and current_sl != 0.0 and current_sl <= entry:
        return None

    # Calculate 50% threshold toward T1
    distance_to_t1 = abs(t1 - entry)
    if distance_to_t1 == 0:
        return None

    halfway = distance_to_t1 * 0.5

    if direction == "bull":
        if (current_price - entry) >= halfway:
            buffer = BREAKEVEN_BUFFER_PIPS * pip_size
            return PositionAction(
                action="modify_sl",
                reason="breakeven",
                new_sl=entry + buffer,
            )
    else:
        if (entry - current_price) >= halfway:
            buffer = BREAKEVEN_BUFFER_PIPS * pip_size
            return PositionAction(
                action="modify_sl",
                reason="breakeven",
                new_sl=entry - buffer,
            )

    return None


def check_triple_tp(
    position: dict[str, Any],
    current_price: float,
) -> Optional[PositionAction]:
    """Triple take-profit at 1R / 2R / 3R.

    T1 (1R) is handled by ``check_t1_hit`` (50% close).  This function
    handles T2 (2R, close 30%) and T3 (3R, close remaining 20%).

    R is calculated from ``initial_risk`` if present in the position dict,
    otherwise falls back to ``abs(entry - stop_loss)``.  Using
    ``initial_risk`` is recommended because the stop-loss may have been
    moved to breakeven by the time T2/T3 are evaluated.

    Position dict should carry ``t2_hit`` and ``t3_hit`` booleans to
    prevent re-triggering.

    Args:
        position: Dict with ``direction``, ``entry_price``, ``stop_loss``,
            ``t1_hit``, ``t2_hit``, ``t3_hit``, and optionally
            ``initial_risk`` (original R value).
        current_price: Current market price.

    Returns:
        PositionAction for partial/full close at T2 or T3, or None.
    """
    # T1 must have been hit first
    if not position.get("t1_hit", False):
        return None

    direction = position.get("direction", "bull")
    entry = position.get("entry_price", 0.0)
    # Prefer explicit initial_risk (SL may have been moved to breakeven)
    r_value = position.get("initial_risk", 0.0)
    if r_value == 0:
        sl = position.get("stop_loss", 0.0)
        r_value = abs(entry - sl)
    if r_value == 0:
        return None

    t2_hit = position.get("t2_hit", False)
    t3_hit = position.get("t3_hit", False)

    if direction == "bull":
        t2_level = entry + 2 * r_value
        t3_level = entry + 3 * r_value
    else:
        t2_level = entry - 2 * r_value
        t3_level = entry - 3 * r_value

    # Check T3 first (higher priority when price has run far)
    if not t3_hit and t2_hit:
        hit_t3 = (
            current_price >= t3_level
            if direction == "bull"
            else current_price <= t3_level
        )
        if hit_t3:
            return PositionAction(
                action="close",
                reason="t3",
                close_pct=TP_T3_PCT,
            )

    # Check T2
    if not t2_hit:
        hit_t2 = (
            current_price >= t2_level
            if direction == "bull"
            else current_price <= t2_level
        )
        if hit_t2:
            return PositionAction(
                action="partial_close",
                reason="t2",
                close_pct=TP_T2_PCT,
            )

    return None


def check_session_exit(
    position: dict[str, Any],
    current_hour_cet: int,
    timeframe_bias: str,
) -> Optional[PositionAction]:
    """Close scalp positions at end of the NY session (CET).

    SWING and MAKRO positions are held overnight and are not affected.

    Args:
        position: Position dict (unused beyond presence check).
        current_hour_cet: Current hour in CET (0-23).
        timeframe_bias: One of ``"SCALP"``, ``"SWING"``, ``"MAKRO"``.

    Returns:
        PositionAction to close if scalp session has ended, or None.
    """
    if timeframe_bias != "SCALP":
        return None

    if current_hour_cet >= SCALP_SESSION_END_CET:
        return PositionAction(
            action="close",
            reason="session_end",
        )

    return None


def check_anti_whipsaw(
    instrument: str,
    last_loss_bar: int,
    current_bar: int,
    cooldown_bars: int = 4,
) -> bool:
    """Check whether enough bars have passed since the last loss.

    Returns ``True`` if re-entry is allowed (cooldown elapsed).
    Returns ``False`` if within the cooldown window — callers should
    block new entries on this instrument.

    Args:
        instrument: Instrument identifier (for documentation; logic is
            purely bar-based).
        last_loss_bar: Bar index of the most recent losing trade.
        current_bar: Current bar index.
        cooldown_bars: Minimum bars to wait before re-entry (default 4).

    Returns:
        True if cooldown has passed, False if still within cooldown.
    """
    return (current_bar - last_loss_bar) >= cooldown_bars


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------


def manage_position(
    position: dict[str, Any],
    market_data: dict[str, Any],
) -> list[PositionAction]:
    """Run all position checks in priority order.

    Priority: geo_spike > session_exit > atr_trailing > breakeven
              > triple_tp > t1_hit > ema9_exit > candle_rules.

    Returns a single-element list with the first triggered action,
    or an empty list if no action is needed.

    Args:
        position: Position state dict.
        market_data: Dict with ``price``, ``ema9_15m``, ``atr_d1``,
            ``atr`` (current-TF ATR), ``current_hour_cet``,
            ``timeframe_bias``.
    """
    current_price = market_data.get("price", 0.0)
    ema9_15m = market_data.get("ema9_15m", 0.0)
    atr_d1 = market_data.get("atr_d1", 0.0)
    atr = market_data.get("atr", 0.0)
    current_hour_cet = market_data.get("current_hour_cet", 0)
    timeframe_bias = market_data.get("timeframe_bias", "SCALP")

    # 1. Geo spike — highest priority (emergency)
    action = check_geo_spike(position, current_price, atr_d1)
    if action is not None:
        return [action]

    # 2. Session exit — close scalps at end of NY session
    action = check_session_exit(position, current_hour_cet, timeframe_bias)
    if action is not None:
        return [action]

    # 3. ATR trailing stop (post-T1)
    action = check_atr_trailing(position, current_price, atr)
    if action is not None:
        return [action]

    # 4. Breakeven + buffer (pre-T1 protection)
    action = check_breakeven(position, current_price)
    if action is not None:
        return [action]

    # 5. Triple take profit — T2 / T3 (post-T1)
    action = check_triple_tp(position, current_price)
    if action is not None:
        return [action]

    # 6. T1 hit
    action = check_t1_hit(position, current_price)
    if action is not None:
        return [action]

    # 7. EMA9 cross (only after T1)
    action = check_ema9_exit(position, ema9_15m, current_price)
    if action is not None:
        return [action]

    # 8. Candle rules
    action = check_candle_rules(position)
    if action is not None:
        return [action]

    return []
