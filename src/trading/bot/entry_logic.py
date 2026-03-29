"""Entry confirmation logic — SCALP EDGE rules.

All functions are pure: they accept data and return booleans or
tuples, with no side effects or broker calls.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from src.analysis.regime_detector import (
    SAFE_HAVENS,
    MarketRegime,
)
from src.trading.bot.config import (
    CORRELATED_PAIRS,
    DEFAULT_SPREADS,
    SESSION_RULES,
    SESSIONS,
)


@dataclass(frozen=True)
class EntryResult:
    """Outcome of the entry evaluation."""

    passed: bool
    reason: str


# ---------------------------------------------------------------------------
# Individual check functions
# ---------------------------------------------------------------------------


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


def check_session_filter(
    instrument: str,
    instrument_class: str,
    current_hour_cet: int,
) -> bool:
    """Check if current time is within allowed trading session for this instrument class.

    Uses ``SESSION_RULES`` to determine which sessions are allowed for
    the given class (A/B/C), then checks ``SESSIONS`` to see if the
    current CET hour falls within any allowed window.

    Args:
        instrument: Instrument key (e.g. ``"EURUSD"``).  Currently unused
            but included for future per-instrument overrides.
        instrument_class: Class from instruments.yaml (``"A"``, ``"B"``, ``"C"``).
        current_hour_cet: Current hour in CET (0-23).

    Returns:
        True if the current hour falls within at least one allowed session.
    """
    allowed_sessions = SESSION_RULES.get(instrument_class, [])
    if not allowed_sessions:
        return False

    for session_name in allowed_sessions:
        window = SESSIONS.get(session_name)
        if window is None:
            continue
        start, end = window
        if start < end:
            # Normal range (e.g. 7-12)
            if start <= current_hour_cet < end:
                return True
        else:
            # Wraps midnight (e.g. 23-7)
            if current_hour_cet >= start or current_hour_cet < end:
                return True

    return False


def check_news_blackout(
    instrument: str,
    events: list[dict[str, Any]],
    blackout_minutes: int = 60,
) -> tuple[bool, str]:
    """Check if there's a high-impact economic event within blackout_minutes.

    Only events with ``impact == "high"`` trigger a blackout.  The event
    must also affect the given instrument (checked via ``berorte`` list).

    Args:
        instrument: Instrument key (e.g. ``"EURUSD"``).
        events: List of event dicts, each with keys:
            ``title`` (str), ``impact`` (str), ``minutes_away`` (float),
            ``country`` (str), ``berorte`` (list[str] — affected instruments).
        blackout_minutes: Minutes before/after event to block entry.

    Returns:
        Tuple of (clear, reason).  ``(True, "")`` if no blocking event,
        ``(False, "news_blackout_<title>_in_<N>m")`` if blocked.
    """
    for event in events:
        impact = event.get("impact", "").lower()
        if impact != "high":
            continue

        affected = event.get("berorte", [])
        if affected and instrument not in affected:
            continue

        minutes_away = event.get("minutes_away")
        if minutes_away is None:
            continue

        if abs(minutes_away) <= blackout_minutes:
            title = event.get("title", "unknown").replace(" ", "_")
            mins = int(minutes_away)
            return False, f"news_blackout_{title}_in_{mins}m"

    return True, ""


def check_spread(
    instrument: str,
    current_spread: float,
    max_spread_multiplier: float = 2.0,
) -> bool:
    """Check if current spread is acceptable.

    Compares *current_spread* against the instrument's normal spread from
    ``DEFAULT_SPREADS``, multiplied by *max_spread_multiplier*.

    Args:
        instrument: Instrument key (e.g. ``"EURUSD"``).
        current_spread: Current live spread in pips.
        max_spread_multiplier: Maximum allowed multiple of normal spread.

    Returns:
        True if spread is within acceptable range, False if widened.
    """
    normal_spread = DEFAULT_SPREADS.get(instrument)
    if normal_spread is None:
        # Unknown instrument — allow entry (don't block on missing data)
        return True
    return current_spread <= normal_spread * max_spread_multiplier


def check_correlation_limit(
    instrument: str,
    open_positions: list[str],
) -> tuple[bool, str]:
    """Check if a correlated instrument is already held.

    Uses ``CORRELATED_PAIRS`` to find instruments that should not be
    held simultaneously.

    Args:
        instrument: Instrument key for the candidate trade.
        open_positions: List of instrument keys currently held.

    Returns:
        Tuple of (clear, reason).  ``(True, "")`` if no conflict,
        ``(False, "correlated_<symbol>_open")`` if a correlated
        position is already open.
    """
    correlated = CORRELATED_PAIRS.get(instrument, [])
    for pos in open_positions:
        if pos in correlated:
            return False, f"correlated_{pos}_open"
    return True, ""


def check_rsi_filter(
    rsi_14: float,
    direction: str,
    overbought: float = 75.0,
    oversold: float = 25.0,
) -> bool:
    """Counter-trend filter: reject entries at RSI extremes.

    Blocks long entries when RSI is overbought and short entries when
    RSI is oversold, preventing entries into exhausted moves.

    Args:
        rsi_14: Current 14-period RSI value (0-100).
        direction: ``"bull"`` or ``"bear"``.
        overbought: RSI threshold above which longs are rejected.
        oversold: RSI threshold below which shorts are rejected.

    Returns:
        True if RSI confirms the direction, False if at an extreme.
    """
    if direction == "bull" and rsi_14 >= overbought:
        return False
    if direction == "bear" and rsi_14 <= oversold:
        return False
    return True


def check_regime_filter(
    instrument: str,
    regime: MarketRegime,
    adjustments: dict,
) -> tuple[bool, str]:
    """Check if instrument is allowed under the current market regime.

    In CRISIS or WAR_FOOTING regimes with ``safe_haven_only`` set, only
    safe-haven instruments (Gold, Silver, USDJPY, USDCHF) may be traded.

    Args:
        instrument: Instrument key (e.g. ``"EURUSD"``).
        regime: Current ``MarketRegime``.
        adjustments: Dict from ``get_regime_adjustments``.

    Returns:
        Tuple of (allowed, reason).  ``(True, "")`` if instrument is
        allowed, ``(False, "regime_filter_<regime>_safe_havens_only")``
        if blocked.
    """
    if adjustments.get("safe_haven_only", False):
        if instrument not in SAFE_HAVENS:
            return False, f"regime_filter_{regime.value}_safe_havens_only"
    return True, ""


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------


def evaluate_entry(
    signal: dict[str, Any],
    market_data: dict[str, Any],
    bot_config: dict[str, Any],
    *,
    current_hour_cet: int | None = None,
    events: list[dict[str, Any]] | None = None,
    current_spread: float | None = None,
    open_position_instruments: list[str] | None = None,
    rsi_14: float | None = None,
    regime: MarketRegime | None = None,
    regime_adjustments: dict | None = None,
) -> EntryResult:
    """Orchestrate all entry checks for a candidate signal.

    Checks run in priority order (fastest rejection first):
      1.  Kill switch active?
      2.  Max open positions reached?
      3.  Grade / score gate
      4.  Session filter (instrument class vs CET hour)
      5.  News blackout (high-impact event within window)
      6.  Spread check (current vs normal spread)
      7.  Correlation limit (correlated pair already open)
      8.  Zone proximity (price near entry level)
      9.  Candle confirmation (5m candle in direction)
      10. EMA9 filter (price on correct side of 15m EMA9)
      11. RSI filter (reject entries at RSI extremes)
      12. Regime filter (safe-havens only during crisis/war)

    Args:
        signal: Dict with keys ``entry_price``, ``direction``, ``grade``,
            ``score``, ``instrument``, ``instrument_class``.
        market_data: Dict with keys ``price``, ``atr_15m``, ``ema9_15m``,
            ``candles_5m``, ``open_positions``.
        bot_config: Dict with keys ``kill_switch_active``, ``max_positions``,
            ``min_grade``, ``min_score``.
        current_hour_cet: Current hour in CET (0-23).  Skipped if None.
        events: Economic calendar events for news blackout check.
            Skipped if None.
        current_spread: Current live spread in pips.  Skipped if None.
        open_position_instruments: List of instrument keys currently held,
            for correlation check.  Skipped if None.
        rsi_14: Current 14-period RSI value.  Skipped if None.
        regime: Current market regime.  Skipped if None.
        regime_adjustments: Dict from ``get_regime_adjustments``.
            Skipped if None.

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

    # 4. Session filter
    instrument = signal.get("instrument", "")
    instrument_class = signal.get("instrument_class", "")
    if current_hour_cet is not None and instrument_class:
        if not check_session_filter(instrument, instrument_class, current_hour_cet):
            return EntryResult(passed=False, reason="outside_trading_session")

    # 5. News blackout
    if events is not None:
        clear, news_reason = check_news_blackout(instrument, events)
        if not clear:
            return EntryResult(passed=False, reason=news_reason)

    # 6. Spread check
    if current_spread is not None:
        if not check_spread(instrument, current_spread):
            return EntryResult(passed=False, reason="spread_too_wide")

    # 7. Correlation limit
    if open_position_instruments is not None:
        clear, corr_reason = check_correlation_limit(
            instrument, open_position_instruments
        )
        if not clear:
            return EntryResult(passed=False, reason=corr_reason)

    # 8. Zone proximity
    entry_level = signal.get("entry_price", 0.0)
    price = market_data.get("price", 0.0)
    atr_15m = market_data.get("atr_15m", 0.0)
    entry_weight = signal.get("entry_weight", 3)
    if not check_zone_proximity(price, entry_level, atr_15m, entry_weight):
        return EntryResult(passed=False, reason="price_not_at_zone")

    # 9. Candle confirmation
    direction = signal.get("direction", "bull")
    candles_5m = market_data.get("candles_5m", [])
    if not check_candle_confirmation(candles_5m, direction):
        return EntryResult(passed=False, reason="no_candle_confirmation")

    # 10. EMA9 filter
    ema9_15m = market_data.get("ema9_15m", 0.0)
    if not check_ema9_filter(price, ema9_15m, direction):
        return EntryResult(passed=False, reason="ema9_filter_failed")

    # 11. RSI filter
    if rsi_14 is not None:
        if not check_rsi_filter(rsi_14, direction):
            return EntryResult(passed=False, reason="rsi_extreme")

    # 12. Regime filter
    if regime is not None and regime_adjustments is not None:
        clear, regime_reason = check_regime_filter(
            instrument, regime, regime_adjustments
        )
        if not clear:
            return EntryResult(passed=False, reason=regime_reason)

    return EntryResult(passed=True, reason="all_checks_passed")
