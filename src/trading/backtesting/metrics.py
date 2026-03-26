"""
Performance metrics for backtesting results.
All stdlib Python -- no numpy/pandas/scipy.
"""

import math
from typing import List, Tuple


def sharpe_ratio(returns: List[float], risk_free_rate: float = 0.0) -> float:
    """Annualized Sharpe ratio.

    Args:
        returns: List of periodic returns (e.g. weekly as decimals: 0.01 = 1%).
        risk_free_rate: Annualized risk-free rate (decimal). Default 0.

    Returns:
        Annualized Sharpe ratio. Assumes ~52 weekly periods per year.
    """
    if not returns or len(returns) < 2:
        return 0.0

    # Convert annual risk-free to per-period
    periods_per_year = 52  # weekly data
    rf_period = (1 + risk_free_rate) ** (1 / periods_per_year) - 1

    excess = [r - rf_period for r in returns]
    mean_excess = sum(excess) / len(excess)
    variance = sum((r - mean_excess) ** 2 for r in excess) / (len(excess) - 1)
    std = math.sqrt(variance) if variance > 0 else 0

    if std == 0:
        return 0.0

    return (mean_excess / std) * math.sqrt(periods_per_year)


def sortino_ratio(returns: List[float], risk_free_rate: float = 0.0) -> float:
    """Annualized Sortino ratio (penalizes only downside volatility).

    Args:
        returns: List of periodic returns as decimals.
        risk_free_rate: Annualized risk-free rate (decimal).

    Returns:
        Annualized Sortino ratio.
    """
    if not returns or len(returns) < 2:
        return 0.0

    periods_per_year = 52
    rf_period = (1 + risk_free_rate) ** (1 / periods_per_year) - 1

    excess = [r - rf_period for r in returns]
    mean_excess = sum(excess) / len(excess)

    # Downside deviation: only negative excess returns
    downside_sq = [e**2 for e in excess if e < 0]
    if not downside_sq:
        return float("inf") if mean_excess > 0 else 0.0

    downside_var = sum(downside_sq) / len(downside_sq)
    downside_dev = math.sqrt(downside_var)

    if downside_dev == 0:
        return 0.0

    return (mean_excess / downside_dev) * math.sqrt(periods_per_year)


def max_drawdown(equity_curve: List[float]) -> Tuple[float, int, int]:
    """Maximum drawdown as a percentage.

    Args:
        equity_curve: List of equity values over time.

    Returns:
        (max_dd_pct, peak_idx, trough_idx) where max_dd_pct is positive
        (e.g. 15.0 means 15% drawdown).
    """
    if not equity_curve or len(equity_curve) < 2:
        return (0.0, 0, 0)

    peak = equity_curve[0]
    peak_idx = 0
    max_dd = 0.0
    max_dd_peak_idx = 0
    max_dd_trough_idx = 0

    for i, val in enumerate(equity_curve):
        if val > peak:
            peak = val
            peak_idx = i

        dd = (peak - val) / peak * 100 if peak > 0 else 0
        if dd > max_dd:
            max_dd = dd
            max_dd_peak_idx = peak_idx
            max_dd_trough_idx = i

    return (max_dd, max_dd_peak_idx, max_dd_trough_idx)


def win_rate(trades: list) -> float:
    """Win rate as a percentage (0-100).

    Args:
        trades: List of Trade objects (must have .pnl attribute).
    """
    if not trades:
        return 0.0
    winners = sum(1 for t in trades if t.pnl > 0)
    return (winners / len(trades)) * 100


def profit_factor(trades: list) -> float:
    """Gross profit / gross loss. > 1.0 is profitable.

    Args:
        trades: List of Trade objects with .pnl attribute.
    """
    gross_profit = sum(t.pnl for t in trades if t.pnl > 0)
    gross_loss = abs(sum(t.pnl for t in trades if t.pnl < 0))

    if gross_loss == 0:
        return float("inf") if gross_profit > 0 else 0.0

    return gross_profit / gross_loss


def expectancy(trades: list) -> float:
    """Expected value per trade.

    E = (win_rate * avg_win) - (loss_rate * avg_loss)

    Args:
        trades: List of Trade objects with .pnl attribute.

    Returns:
        Expected P&L per trade in absolute terms.
    """
    if not trades:
        return 0.0

    winners = [t for t in trades if t.pnl > 0]
    losers = [t for t in trades if t.pnl <= 0]

    avg_win = sum(t.pnl for t in winners) / len(winners) if winners else 0
    avg_loss = abs(sum(t.pnl for t in losers) / len(losers)) if losers else 0

    wr = len(winners) / len(trades)
    lr = len(losers) / len(trades)

    return (wr * avg_win) - (lr * avg_loss)


def avg_holding_period(trades: list) -> float:
    """Average number of bars a trade is held.

    Args:
        trades: List of Trade objects with .bars_held attribute.
    """
    if not trades:
        return 0.0
    return sum(t.bars_held for t in trades) / len(trades)


def calmar_ratio(returns: List[float], max_dd: float) -> float:
    """Calmar ratio: annualized return / max drawdown.

    Args:
        returns: List of periodic returns (decimals).
        max_dd: Maximum drawdown as a percentage (e.g. 15.0 for 15%).

    Returns:
        Calmar ratio.
    """
    if not returns or max_dd <= 0:
        return 0.0

    periods_per_year = 52
    total_return = 1.0
    for r in returns:
        total_return *= 1 + r

    years = len(returns) / periods_per_year
    if years <= 0:
        return 0.0

    annualized_return = (total_return ** (1 / years) - 1) * 100
    return annualized_return / max_dd


def recovery_factor(net_profit: float, max_dd_absolute: float) -> float:
    """Recovery factor: net profit / max drawdown (absolute).

    Args:
        net_profit: Total net profit in currency.
        max_dd_absolute: Max drawdown in currency (positive number).

    Returns:
        Recovery factor. Higher is better.
    """
    if max_dd_absolute <= 0:
        return float("inf") if net_profit > 0 else 0.0
    return net_profit / max_dd_absolute


def consecutive_wins(trades: list) -> int:
    """Maximum consecutive winning trades."""
    if not trades:
        return 0
    max_streak = 0
    current = 0
    for t in trades:
        if t.pnl > 0:
            current += 1
            max_streak = max(max_streak, current)
        else:
            current = 0
    return max_streak


def consecutive_losses(trades: list) -> int:
    """Maximum consecutive losing trades."""
    if not trades:
        return 0
    max_streak = 0
    current = 0
    for t in trades:
        if t.pnl <= 0:
            current += 1
            max_streak = max(max_streak, current)
        else:
            current = 0
    return max_streak


def risk_reward_ratio(trades: list) -> float:
    """Average risk:reward ratio achieved across all trades."""
    if not trades:
        return 0.0
    winners = [t for t in trades if t.pnl > 0]
    losers = [t for t in trades if t.pnl < 0]
    if not winners or not losers:
        return 0.0
    avg_win = sum(t.pnl for t in winners) / len(winners)
    avg_loss = abs(sum(t.pnl for t in losers) / len(losers))
    if avg_loss == 0:
        return float("inf")
    return avg_win / avg_loss


def monthly_returns(equity_curve: List[Tuple[str, float]]) -> List[Tuple[str, float]]:
    """Calculate monthly returns from dated equity curve.

    Args:
        equity_curve: List of (date_str, equity_value) tuples.

    Returns:
        List of (month_str "YYYY-MM", return_pct) tuples.
    """
    if not equity_curve or len(equity_curve) < 2:
        return []

    monthly: List[Tuple[str, float]] = []
    prev_month = equity_curve[0][0][:7]
    prev_equity = equity_curve[0][1]

    for date_str, eq in equity_curve[1:]:
        month = date_str[:7]
        if month != prev_month:
            ret = (eq / prev_equity - 1) * 100 if prev_equity else 0
            monthly.append((prev_month, round(ret, 2)))
            prev_equity = eq
            prev_month = month

    # Final partial month
    if equity_curve:
        last_eq = equity_curve[-1][1]
        ret = (last_eq / prev_equity - 1) * 100 if prev_equity else 0
        monthly.append((prev_month, round(ret, 2)))

    return monthly
