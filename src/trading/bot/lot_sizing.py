"""Lot size calculation based on VIX regime and grade tier.

The tier multiplier matrix scales position size down when VIX is elevated
or the signal grade is weak, and blocks C-grade trades entirely in
extreme volatility.
"""

from __future__ import annotations

import math

from src.core.enums import Grade, VixRegime
from src.trading.bot.config import LOT_PARAMS, LotParams


# ---------------------------------------------------------------------------
# VIX x Grade multiplier matrix
# ---------------------------------------------------------------------------
_TIER_MATRIX: dict[VixRegime, dict[str, float]] = {
    VixRegime.NORMAL: {
        Grade.A_PLUS: 1.0,
        Grade.A: 1.0,
        Grade.B: 0.6,
        Grade.C: 0.3,
    },
    VixRegime.ELEVATED: {
        Grade.A_PLUS: 0.6,
        Grade.A: 0.6,
        Grade.B: 0.3,
        Grade.C: 0.3,
    },
    VixRegime.EXTREME: {
        Grade.A_PLUS: 0.3,
        Grade.A: 0.3,
        Grade.B: 0.3,
        Grade.C: 0.0,  # no trade
    },
}


def classify_vix(vix: float) -> VixRegime:
    """Classify VIX value into a volatility regime.

    Args:
        vix: Current VIX index value.

    Returns:
        VixRegime enum member.
    """
    if vix > 30.0:
        return VixRegime.EXTREME
    if vix > 20.0:
        return VixRegime.ELEVATED
    return VixRegime.NORMAL


def get_tier_multiplier(vix: float, grade: str) -> float:
    """Look up the tier multiplier for a VIX level and grade.

    Args:
        vix: Current VIX index value.
        grade: Signal grade string (e.g. "A+", "A", "B", "C").

    Returns:
        Multiplier between 0.0 and 1.0.  Returns 0.0 if grade is
        unknown or the combination is blocked.
    """
    regime = classify_vix(vix)
    regime_row = _TIER_MATRIX.get(regime, {})
    return regime_row.get(grade, 0.0)


def _round_to_step(value: float, step: float) -> float:
    """Round *value* down to the nearest multiple of *step*."""
    if step <= 0:
        return value
    return math.floor(value / step) * step


def calculate_lot_size(
    account_balance: float,
    risk_pct: float,
    entry: float,
    stop_loss: float,
    vix: float,
    grade: str,
    instrument: str,
) -> float:
    """Calculate lot size for a trade.

    The formula:
      1. risk_amount = account_balance * risk_pct * tier_multiplier
      2. sl_distance_pips = abs(entry - stop_loss) / pip_size
      3. lots = risk_amount / (sl_distance_pips * pip_value_per_lot)
      4. Round down to nearest lot_step, clamp to min_lot.

    Args:
        account_balance: Account equity in USD.
        risk_pct: Risk per trade as a decimal (e.g. 0.01 = 1%).
        entry: Planned entry price.
        stop_loss: Stop-loss price.
        vix: Current VIX index value.
        grade: Signal grade (A+, A, B, C).
        instrument: Instrument key (e.g. "EURUSD", "Gold").

    Returns:
        Lot size rounded to the instrument's lot_step.
        Returns 0.0 if the trade is blocked (C grade in extreme VIX),
        the instrument is unknown, or the stop-loss distance is zero.
    """
    multiplier = get_tier_multiplier(vix, grade)
    if multiplier <= 0.0:
        return 0.0

    params: LotParams | None = LOT_PARAMS.get(instrument)
    if params is None:
        return 0.0

    sl_distance = abs(entry - stop_loss)
    if sl_distance == 0.0:
        return 0.0

    sl_pips = sl_distance / params.pip_size
    if sl_pips == 0.0:
        return 0.0

    risk_amount = account_balance * risk_pct * multiplier
    raw_lots = risk_amount / (sl_pips * params.pip_value_per_lot)

    lots = _round_to_step(raw_lots, params.lot_step)
    return max(lots, params.min_lot) if lots > 0 else 0.0
