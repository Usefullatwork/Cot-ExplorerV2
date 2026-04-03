"""Kelly criterion position sizing.

Computes the optimal bet fraction (f*) from historical win rate and
average win/loss ratio.  Provides full, half, and quarter Kelly
variants plus a lot-size helper that converts the Kelly fraction into
a concrete trade size.

All functions are pure -- no I/O, no DB, no side effects.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class KellyResult:
    """Kelly criterion sizing result."""

    full_kelly: float
    half_kelly: float
    quarter_kelly: float
    win_rate: float
    avg_win: float
    avg_loss: float
    edge: float  # expected value per unit bet


# ---------------------------------------------------------------------------
# Core Kelly math
# ---------------------------------------------------------------------------


def kelly_fraction(win_rate: float, avg_win: float, avg_loss: float) -> float:
    """Compute full Kelly fraction: f* = (b*p - q) / b.

    Where b = avg_win / avg_loss, p = win_rate, q = 1 - p.
    Returns 0.0 if there is no edge (negative or zero expected value).
    Clamps to [0.0, 1.0].

    Args:
        win_rate: Probability of a winning trade (0.0-1.0).
        avg_win: Average profit on a winning trade (positive).
        avg_loss: Average loss on a losing trade (positive).

    Returns:
        Optimal fraction of bankroll to risk.
    """
    if avg_loss <= 0.0 or avg_win <= 0.0 or win_rate <= 0.0:
        return 0.0

    b = avg_win / avg_loss
    p = win_rate
    q = 1.0 - p

    f_star = (b * p - q) / b

    return max(0.0, min(f_star, 1.0))


def half_kelly(
    win_rate: float,
    avg_win: float,
    avg_loss: float,
    max_fraction: float = 0.25,
) -> float:
    """Half-Kelly clamped to *max_fraction*.

    Conservative sizing that reduces variance while retaining most of the
    compound growth benefit.

    Args:
        win_rate: Probability of a winning trade (0.0-1.0).
        avg_win: Average profit on a winning trade (positive).
        avg_loss: Average loss on a losing trade (positive).
        max_fraction: Upper clamp for the resulting fraction.

    Returns:
        Half of the full Kelly fraction, clamped to [0.0, max_fraction].
    """
    f = kelly_fraction(win_rate, avg_win, avg_loss) / 2.0
    return max(0.0, min(f, max_fraction))


# ---------------------------------------------------------------------------
# Lot-size conversion
# ---------------------------------------------------------------------------


def kelly_position_size(
    account_equity: float,
    win_rate: float,
    avg_win: float,
    avg_loss: float,
    entry_price: float,
    stop_loss: float,
    pip_size: float = 0.0001,
    pip_value_per_lot: float = 10.0,
    max_fraction: float = 0.25,
) -> float:
    """Compute lot size using half-Kelly.

    risk_per_lot = abs(entry - stop_loss) / pip_size * pip_value_per_lot
    kelly_risk   = account_equity * half_kelly_fraction
    lots         = kelly_risk / risk_per_lot

    Args:
        account_equity: Account equity in USD.
        win_rate: Historical win rate (0.0-1.0).
        avg_win: Average winning trade profit (positive).
        avg_loss: Average losing trade loss (positive).
        entry_price: Planned entry price.
        stop_loss: Stop-loss price.
        pip_size: Value of one pip in price terms.
        pip_value_per_lot: Dollar value of one pip per standard lot.
        max_fraction: Upper clamp for the half-Kelly fraction.

    Returns:
        Lot size (>= 0.0).  Returns 0.0 when inputs are invalid or
        there is no edge.
    """
    if account_equity <= 0.0 or pip_size <= 0.0 or pip_value_per_lot <= 0.0:
        return 0.0

    sl_distance = abs(entry_price - stop_loss)
    if sl_distance == 0.0:
        return 0.0

    risk_per_lot = (sl_distance / pip_size) * pip_value_per_lot
    if risk_per_lot <= 0.0:
        return 0.0

    kelly_risk = account_equity * half_kelly(win_rate, avg_win, avg_loss, max_fraction)
    if kelly_risk <= 0.0:
        return 0.0

    return kelly_risk / risk_per_lot


# ---------------------------------------------------------------------------
# Convenience: compute Kelly from raw trade P&L list
# ---------------------------------------------------------------------------


def compute_kelly(trades_pnl: list[float]) -> KellyResult:
    """Compute Kelly from a list of trade P&L values.

    Separates wins (> 0) and losses (< 0), computes rates and averages,
    then returns a ``KellyResult`` with full, half, and quarter Kelly.

    Args:
        trades_pnl: List of trade profit/loss values.  Positive = win,
            negative = loss.  Zeros are ignored.

    Returns:
        KellyResult dataclass.
    """
    wins = [t for t in trades_pnl if t > 0.0]
    losses = [t for t in trades_pnl if t < 0.0]

    total = len(wins) + len(losses)
    if total == 0:
        return KellyResult(
            full_kelly=0.0,
            half_kelly=0.0,
            quarter_kelly=0.0,
            win_rate=0.0,
            avg_win=0.0,
            avg_loss=0.0,
            edge=0.0,
        )

    wr = len(wins) / total
    aw = sum(wins) / len(wins) if wins else 0.0
    al = abs(sum(losses) / len(losses)) if losses else 0.0

    fk = kelly_fraction(wr, aw, al)
    edge = wr * aw - (1.0 - wr) * al

    return KellyResult(
        full_kelly=fk,
        half_kelly=fk / 2.0,
        quarter_kelly=fk / 4.0,
        win_rate=wr,
        avg_win=aw,
        avg_loss=al,
        edge=edge,
    )
