"""Monte Carlo simulation for trading strategy validation.

Randomly reshuffles trade order to stress-test parameter robustness.
All stdlib Python -- no numpy/pandas/scipy. Designed for speed: pure math,
no I/O. Uses list comprehensions and random.shuffle().

Usage:
    from src.trading.backtesting.monte_carlo import run_monte_carlo

    trades_pnl = [120.0, -50.0, 80.0, -30.0, 200.0, -100.0, ...]
    result = run_monte_carlo(trades_pnl, starting_equity=10000.0, iterations=5000)
    print(print_summary(result))
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import List, Tuple


@dataclass(frozen=True)
class MonteCarloResult:
    """Results from a Monte Carlo trade-reshuffling simulation."""

    iterations: int
    original_final_equity: float
    median_final_equity: float
    percentile_5: float          # worst 5% outcome
    percentile_25: float
    percentile_75: float
    percentile_95: float         # best 5% outcome
    probability_of_ruin: float   # % of sims where equity < ruin threshold
    max_drawdown_median: float   # median max drawdown across sims (%)
    max_drawdown_95th: float     # worst-case drawdown -- 95th percentile (%)
    confidence_profitable: float # % of sims that end profitable


def _build_equity_curve(
    trades: List[float], starting_equity: float,
) -> Tuple[float, float]:
    """Build equity curve from sequential trades.

    Returns:
        (final_equity, max_drawdown_pct)
    """
    equity = starting_equity
    peak = starting_equity
    max_dd_pct = 0.0

    for pnl in trades:
        equity += pnl
        if equity > peak:
            peak = equity
        if peak > 0:
            dd = (peak - equity) / peak * 100.0
            if dd > max_dd_pct:
                max_dd_pct = dd

    return equity, max_dd_pct


def _percentile(sorted_values: List[float], pct: float) -> float:
    """Compute percentile from a pre-sorted list. pct in [0, 100]."""
    if not sorted_values:
        return 0.0
    n = len(sorted_values)
    k = (pct / 100.0) * (n - 1)
    lo = int(math.floor(k))
    hi = min(lo + 1, n - 1)
    frac = k - lo
    return sorted_values[lo] + frac * (sorted_values[hi] - sorted_values[lo])


def run_monte_carlo(
    trades: List[float],
    starting_equity: float = 10000.0,
    iterations: int = 5000,
    ruin_threshold: float = 0.5,
    seed: int | None = None,
) -> MonteCarloResult:
    """Run Monte Carlo simulation by reshuffling trade P&L order.

    Args:
        trades: List of trade P&L values (positive = win, negative = loss).
        starting_equity: Initial account balance.
        iterations: Number of reshuffles (min 100, recommend 5000).
        ruin_threshold: Equity ratio below which = ruin (0.5 = 50% of start).
        seed: Optional RNG seed for reproducibility.

    Returns:
        MonteCarloResult with percentile statistics and ruin probability.

    Raises:
        ValueError: If trades is empty or iterations < 1.
    """
    if not trades:
        raise ValueError("trades list must not be empty")
    if iterations < 1:
        raise ValueError("iterations must be >= 1")

    iterations = max(iterations, 100)
    ruin_level = starting_equity * ruin_threshold

    rng = random.Random(seed)

    # Compute original (unshuffled) result
    original_final, _ = _build_equity_curve(trades, starting_equity)

    # Run simulations
    final_equities: List[float] = []
    max_drawdowns: List[float] = []
    ruin_count = 0
    profitable_count = 0

    shuffled = list(trades)  # working copy
    for _ in range(iterations):
        rng.shuffle(shuffled)
        final_eq, max_dd = _build_equity_curve(shuffled, starting_equity)
        final_equities.append(final_eq)
        max_drawdowns.append(max_dd)

        if final_eq < ruin_level:
            ruin_count += 1
        if final_eq > starting_equity:
            profitable_count += 1

    # Sort for percentile computation
    final_equities.sort()
    max_drawdowns.sort()

    return MonteCarloResult(
        iterations=iterations,
        original_final_equity=round(original_final, 2),
        median_final_equity=round(_percentile(final_equities, 50.0), 2),
        percentile_5=round(_percentile(final_equities, 5.0), 2),
        percentile_25=round(_percentile(final_equities, 25.0), 2),
        percentile_75=round(_percentile(final_equities, 75.0), 2),
        percentile_95=round(_percentile(final_equities, 95.0), 2),
        probability_of_ruin=round(ruin_count / iterations * 100.0, 2),
        max_drawdown_median=round(_percentile(max_drawdowns, 50.0), 2),
        max_drawdown_95th=round(_percentile(max_drawdowns, 95.0), 2),
        confidence_profitable=round(profitable_count / iterations * 100.0, 2),
    )


def generate_report(result: MonteCarloResult) -> dict:
    """Generate JSON-serializable report with all statistics.

    Args:
        result: MonteCarloResult from run_monte_carlo().

    Returns:
        Dictionary with all simulation statistics.
    """
    return {
        "simulation": {
            "iterations": result.iterations,
            "original_final_equity": result.original_final_equity,
        },
        "equity_distribution": {
            "median": result.median_final_equity,
            "percentile_5": result.percentile_5,
            "percentile_25": result.percentile_25,
            "percentile_75": result.percentile_75,
            "percentile_95": result.percentile_95,
        },
        "risk_assessment": {
            "probability_of_ruin_pct": result.probability_of_ruin,
            "max_drawdown_median_pct": result.max_drawdown_median,
            "max_drawdown_95th_pct": result.max_drawdown_95th,
            "confidence_profitable_pct": result.confidence_profitable,
        },
    }


def print_summary(result: MonteCarloResult) -> str:
    """Human-readable summary of Monte Carlo results.

    Args:
        result: MonteCarloResult from run_monte_carlo().

    Returns:
        Multi-line formatted string.
    """
    lines = [
        "=" * 55,
        "  MONTE CARLO SIMULATION RESULTS",
        "=" * 55,
        f"  Iterations:              {result.iterations:,}",
        f"  Original final equity:   ${result.original_final_equity:,.2f}",
        "",
        "  EQUITY DISTRIBUTION",
        "-" * 55,
        f"  5th percentile (worst):  ${result.percentile_5:,.2f}",
        f"  25th percentile:         ${result.percentile_25:,.2f}",
        f"  Median (50th):           ${result.median_final_equity:,.2f}",
        f"  75th percentile:         ${result.percentile_75:,.2f}",
        f"  95th percentile (best):  ${result.percentile_95:,.2f}",
        "",
        "  RISK ASSESSMENT",
        "-" * 55,
        f"  Probability of ruin:     {result.probability_of_ruin:.1f}%",
        f"  Max drawdown (median):   {result.max_drawdown_median:.1f}%",
        f"  Max drawdown (95th):     {result.max_drawdown_95th:.1f}%",
        f"  Confidence profitable:   {result.confidence_profitable:.1f}%",
        "=" * 55,
    ]
    return "\n".join(lines)


@dataclass(frozen=True)
class EquityCurveMCResult:
    """Results from equity curve Monte Carlo via block bootstrap."""

    iterations: int
    mean_annual_return: float
    ci_annual_return: Tuple[float, float]   # (5th, 95th percentile)
    mean_max_drawdown: float
    ci_max_drawdown: Tuple[float, float]    # (5th, 95th percentile)
    mean_sharpe: float
    ci_sharpe: Tuple[float, float]
    ruin_probability: float                  # fraction of paths hitting threshold
    mean_recovery_time: float               # bars to recover from max DD


def _block_resample(
    daily_returns: List[float],
    block_size: int,
    rng: random.Random,
) -> List[float]:
    """Resample daily_returns using block bootstrap.

    Randomly picks blocks of consecutive returns with replacement
    until total length >= len(daily_returns), then trims to exact length.
    """
    n = len(daily_returns)
    result: List[float] = []
    while len(result) < n:
        start = rng.randint(0, n - 1)
        end = min(start + block_size, n)
        result.extend(daily_returns[start:end])
    return result[:n]


def _equity_curve_stats(
    returns: List[float],
    starting_equity: float,
    ruin_level: float,
    periods_per_year: int,
) -> Tuple[float, float, float, float, bool]:
    """Compute stats from a single resampled return series.

    Returns:
        (annual_return, max_dd_pct, sharpe, recovery_time, hit_ruin)
    """
    n = len(returns)
    equity = starting_equity
    peak = starting_equity
    max_dd_pct = 0.0
    trough_bar = 0
    peak_bar = 0
    recovery_time = 0.0
    hit_ruin = False
    found_recovery = False

    for i, r in enumerate(returns):
        equity *= (1.0 + r)
        if equity <= ruin_level:
            hit_ruin = True
        if equity > peak:
            if max_dd_pct > 0.0 and not found_recovery:
                recovery_time = float(i - trough_bar)
                found_recovery = True
            peak = equity
            peak_bar = i
        if peak > 0:
            dd = (peak - equity) / peak * 100.0
            if dd > max_dd_pct:
                max_dd_pct = dd
                trough_bar = i
                found_recovery = False

    # If never recovered from max DD, use distance to end
    if not found_recovery and max_dd_pct > 0.0:
        recovery_time = float(n - trough_bar)

    # Annual return: geometric
    final_equity = equity
    total_return = (final_equity / starting_equity) if starting_equity > 0 else 0.0
    if n > 0 and total_return > 0:
        annual_return = total_return ** (periods_per_year / n) - 1.0
    else:
        annual_return = -1.0 if total_return <= 0 else 0.0

    # Sharpe ratio
    if n > 1:
        mean_r = sum(returns) / n
        var_r = sum((r - mean_r) ** 2 for r in returns) / (n - 1)
        std_r = math.sqrt(var_r) if var_r > 0 else 0.0
        sharpe = (mean_r / std_r * math.sqrt(periods_per_year)) if std_r > 0 else 0.0
    else:
        sharpe = 0.0

    return annual_return, max_dd_pct, sharpe, recovery_time, hit_ruin


def run_equity_curve_monte_carlo(
    daily_returns: List[float],
    starting_equity: float = 100000.0,
    iterations: int = 10000,
    block_size: int = 5,
    ruin_threshold: float = 0.50,
    seed: int = 42,
    periods_per_year: int = 252,
) -> EquityCurveMCResult:
    """Block bootstrap Monte Carlo on equity curves.

    Unlike run_monte_carlo() which reshuffles individual trades,
    this preserves serial correlation by resampling blocks of consecutive returns.

    Algorithm:
    1. Divide daily_returns into blocks of block_size
    2. For each iteration:
       a. Randomly sample blocks with replacement until total length >= len(daily_returns)
       b. Trim to exact length
       c. Build equity curve from block-resampled returns
       d. Compute: final return, max drawdown, Sharpe, recovery time
    3. Aggregate across iterations: means, CIs, ruin probability

    Uses random.Random(seed) for determinism.

    Sharpe = (mean_return / std_return) * sqrt(periods_per_year)
    Recovery time = bars from max DD trough to new equity high
    Ruin = equity drops below starting * (1 - ruin_threshold)

    Args:
        daily_returns: List of daily return values (e.g. 0.01 = 1%).
        starting_equity: Initial account balance.
        iterations: Number of bootstrap resamples (min 100).
        block_size: Size of consecutive return blocks to sample.
        ruin_threshold: Fraction loss that constitutes ruin (0.50 = 50%).
        seed: RNG seed for reproducibility.
        periods_per_year: Trading periods per year for annualization.

    Returns:
        EquityCurveMCResult with aggregated statistics.

    Raises:
        ValueError: If daily_returns is empty or iterations < 1.
    """
    if not daily_returns:
        raise ValueError("daily_returns must not be empty")
    if iterations < 1:
        raise ValueError("iterations must be >= 1")

    iterations = max(iterations, 100)
    block_size = max(block_size, 1)
    rng = random.Random(seed)
    ruin_level = starting_equity * (1.0 - ruin_threshold)

    annual_returns: List[float] = []
    max_drawdowns: List[float] = []
    sharpes: List[float] = []
    recovery_times: List[float] = []
    ruin_count = 0

    for _ in range(iterations):
        resampled = _block_resample(daily_returns, block_size, rng)
        ann_ret, max_dd, sharpe, rec_time, hit_ruin = _equity_curve_stats(
            resampled, starting_equity, ruin_level, periods_per_year,
        )
        annual_returns.append(ann_ret)
        max_drawdowns.append(max_dd)
        sharpes.append(sharpe)
        recovery_times.append(rec_time)
        if hit_ruin:
            ruin_count += 1

    # Sort for percentile computation
    annual_returns_sorted = sorted(annual_returns)
    max_drawdowns_sorted = sorted(max_drawdowns)
    sharpes_sorted = sorted(sharpes)

    n = len(annual_returns)
    mean_ann = sum(annual_returns) / n
    mean_dd = sum(max_drawdowns) / n
    mean_sh = sum(sharpes) / n
    mean_rec = sum(recovery_times) / n

    return EquityCurveMCResult(
        iterations=iterations,
        mean_annual_return=round(mean_ann, 6),
        ci_annual_return=(
            round(_percentile(annual_returns_sorted, 5.0), 6),
            round(_percentile(annual_returns_sorted, 95.0), 6),
        ),
        mean_max_drawdown=round(mean_dd, 4),
        ci_max_drawdown=(
            round(_percentile(max_drawdowns_sorted, 5.0), 4),
            round(_percentile(max_drawdowns_sorted, 95.0), 4),
        ),
        mean_sharpe=round(mean_sh, 4),
        ci_sharpe=(
            round(_percentile(sharpes_sorted, 5.0), 4),
            round(_percentile(sharpes_sorted, 95.0), 4),
        ),
        ruin_probability=round(ruin_count / iterations, 4),
        mean_recovery_time=round(mean_rec, 2),
    )


if __name__ == "__main__":
    # Standalone demo with synthetic trade data
    demo_trades = [
        150.0, -80.0, 200.0, -120.0, 90.0, -60.0, 180.0, -40.0,
        -150.0, 300.0, -90.0, 110.0, -70.0, 250.0, -100.0, 160.0,
        -50.0, 130.0, -110.0, 220.0, -80.0, 170.0, -130.0, 140.0,
        -60.0, 190.0, -95.0, 210.0, -75.0, 160.0, -85.0, 145.0,
    ]
    print(f"Demo: {len(demo_trades)} trades, starting equity $10,000\n")
    mc_result = run_monte_carlo(demo_trades, starting_equity=10000.0, iterations=5000, seed=42)
    print(print_summary(mc_result))
    print(f"\nJSON report:\n{generate_report(mc_result)}")
