"""Lot size calculation based on VIX regime and grade tier.

The tier multiplier matrix scales position size down when VIX is elevated
or the signal grade is weak, and blocks C-grade trades entirely in
extreme volatility.

Additional helpers adjust risk for drawdown, win/loss streaks, and
spread costs.
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


def adjust_for_drawdown(base_risk_pct: float, current_drawdown_pct: float) -> float:
    """Reduce *base_risk_pct* based on current drawdown depth.

    - 0-10 % drawdown: full risk
    - 10-20 % drawdown: half risk
    - 20 %+ drawdown: quarter risk

    Args:
        base_risk_pct: Normal risk per trade as a decimal (e.g. 0.01).
        current_drawdown_pct: Current drawdown as a percentage (e.g. 15.0
            means the account is 15 % below peak equity).

    Returns:
        Adjusted risk percentage (always >= 0).
    """
    if current_drawdown_pct >= 20.0:
        return base_risk_pct * 0.25
    if current_drawdown_pct >= 10.0:
        return base_risk_pct * 0.5
    return base_risk_pct


def adjust_for_streak(
    base_multiplier: float,
    consecutive_wins: int,
    consecutive_losses: int,
) -> float:
    """Anti-martingale streak adjustment.

    - After 1 loss: reduce by 25 %
    - After 2+ losses: halve
    - After 2+ wins: increase by 10 % (capped at 1.2x)
    - No streak: unchanged

    Args:
        base_multiplier: Starting multiplier (typically 1.0).
        consecutive_wins: Current win streak length.
        consecutive_losses: Current loss streak length.

    Returns:
        Adjusted multiplier (>= 0).
    """
    if consecutive_losses >= 2:
        return base_multiplier * 0.5
    if consecutive_losses == 1:
        return base_multiplier * 0.75
    if consecutive_wins >= 2:
        return min(base_multiplier * 1.1, 1.2)
    return base_multiplier


def deduct_spread(
    risk_amount: float,
    spread_pips: float,
    pip_value: float,
) -> float:
    """Deduct expected spread cost from the risk budget.

    Args:
        risk_amount: Dollar risk budget for the trade.
        spread_pips: Expected spread in pips.
        pip_value: Dollar value of one pip for the intended lot size.

    Returns:
        Adjusted risk amount after spread deduction (floored at 0).
    """
    spread_cost = spread_pips * pip_value
    return max(risk_amount - spread_cost, 0.0)


def calculate_lot_size(
    account_balance: float,
    risk_pct: float,
    entry: float,
    stop_loss: float,
    vix: float,
    grade: str,
    instrument: str,
    *,
    drawdown_pct: float = 0.0,
    consecutive_wins: int = 0,
    consecutive_losses: int = 0,
    spread_pips: float = 0.0,
    correlation_adjustment: float = 1.0,
    kelly_fraction: float | None = None,
) -> float:
    """Calculate lot size for a trade.

    The formula:
      1. risk_pct is adjusted for drawdown (``adjust_for_drawdown``).
         If ``kelly_fraction`` is provided, effective risk is the minimum
         of drawdown-adjusted risk and kelly_fraction.
      2. risk_amount = account_balance * adjusted_risk_pct * tier_multiplier
      3. An anti-martingale streak multiplier is applied
         (``adjust_for_streak``).
      4. Expected spread cost is deducted (``deduct_spread``).
      5. sl_distance_pips = abs(entry - stop_loss) / pip_size
      6. lots = adjusted_risk / (sl_distance_pips * pip_value_per_lot)
      7. Multiply by ``correlation_adjustment``.
      8. Round down to nearest lot_step, clamp to min_lot.

    Args:
        account_balance: Account equity in USD.
        risk_pct: Risk per trade as a decimal (e.g. 0.01 = 1 %).
        entry: Planned entry price.
        stop_loss: Stop-loss price.
        vix: Current VIX index value.
        grade: Signal grade (A+, A, B, C).
        instrument: Instrument key (e.g. "EURUSD", "Gold").
        drawdown_pct: Current drawdown percentage (default 0.0).
        consecutive_wins: Length of current win streak (default 0).
        consecutive_losses: Length of current loss streak (default 0).
        spread_pips: Expected spread in pips (default 0.0).
        correlation_adjustment: Multiplier from portfolio correlation
            analysis (default 1.0, no adjustment).
        kelly_fraction: Optional Kelly criterion risk fraction.  When
            provided, effective risk = min(risk_pct, kelly_fraction).

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

    # 1. Adjust risk for drawdown, cap by Kelly if provided
    adjusted_risk_pct = adjust_for_drawdown(risk_pct, drawdown_pct)
    if kelly_fraction is not None:
        adjusted_risk_pct = min(adjusted_risk_pct, kelly_fraction)

    # 2. Base risk amount with tier multiplier
    risk_amount = account_balance * adjusted_risk_pct * multiplier

    # 3. Anti-martingale streak adjustment
    streak_mult = adjust_for_streak(1.0, consecutive_wins, consecutive_losses)
    risk_amount *= streak_mult

    # 4. Deduct spread cost
    risk_amount = deduct_spread(risk_amount, spread_pips, params.pip_value_per_lot)

    if risk_amount <= 0.0:
        return 0.0

    raw_lots = risk_amount / (sl_pips * params.pip_value_per_lot)

    # 5. Correlation adjustment
    raw_lots *= max(correlation_adjustment, 0.0)

    lots = _round_to_step(raw_lots, params.lot_step)
    return max(lots, params.min_lot) if lots > 0 else 0.0
