"""Portfolio-level risk management: VaR, CVaR, correlation sizing, regime limits.

Adds portfolio-wide risk gates on top of the per-trade checks in
``src/trading/bot/risk_manager.py``.  All functions are pure -- no I/O,
no DB, no side effects.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Sequence

from scipy import stats as scipy_stats


@dataclass(frozen=True)
class VaRResult:
    """Value at Risk calculation results."""

    var_95: float
    var_99: float
    cvar_95: float
    cvar_99: float
    lookback_days: int
    n_returns: int


@dataclass(frozen=True)
class CorrelationSizingResult:
    """Result of correlation-based position sizing."""

    adjusted_multiplier: float
    max_correlation: float
    blocked: bool
    reason: str


@dataclass(frozen=True)
class RegimeLimits:
    """Position limits for current regime."""

    regime: str
    max_positions: int
    current_positions: int
    can_open: bool
    reason: str


# ---------------------------------------------------------------------------
# Default regime position limits (matches regime_detector.py regimes)
# ---------------------------------------------------------------------------

_DEFAULT_REGIME_LIMITS: dict[str, int] = {
    "normal": 5,
    "risk_off": 3,
    "crisis": 1,
    "war_footing": 2,
    "energy_shock": 2,
    "sanctions": 2,
}


# ---------------------------------------------------------------------------
# VaR / CVaR
# ---------------------------------------------------------------------------


def compute_portfolio_var(
    returns: Sequence[float],
    confidence_95: float = 0.95,
    confidence_99: float = 0.99,
) -> VaRResult:
    """Compute historical VaR and CVaR from a return series.

    Historical method: sort returns ascending, VaR = percentile at
    (1 - confidence).  CVaR (Expected Shortfall) = mean of all returns
    worse than (or equal to) VaR.

    Returns are expected as decimals (0.01 = 1 %).

    Args:
        returns: Sequence of portfolio daily returns.
        confidence_95: Confidence level for the 95 % VaR.
        confidence_99: Confidence level for the 99 % VaR.

    Returns:
        VaRResult with all four risk metrics.
    """
    n = len(returns)
    if n < 2:
        return VaRResult(
            var_95=0.0,
            var_99=0.0,
            cvar_95=0.0,
            cvar_99=0.0,
            lookback_days=n,
            n_returns=n,
        )

    sorted_rets = sorted(returns)

    var_95 = _historical_var(sorted_rets, confidence_95)
    var_99 = _historical_var(sorted_rets, confidence_99)
    cvar_95 = _cvar(sorted_rets, var_95)
    cvar_99 = _cvar(sorted_rets, var_99)

    return VaRResult(
        var_95=var_95,
        var_99=var_99,
        cvar_95=cvar_95,
        cvar_99=cvar_99,
        lookback_days=n,
        n_returns=n,
    )


def _historical_var(sorted_returns: list[float], confidence: float) -> float:
    """VaR from pre-sorted returns at the given confidence level.

    The VaR is returned as a positive number representing the loss
    (negated left-tail percentile).
    """
    n = len(sorted_returns)
    idx = int(math.floor((1.0 - confidence) * n))
    idx = max(0, min(idx, n - 1))
    return -sorted_returns[idx]


def _cvar(sorted_returns: list[float], var_value: float) -> float:
    """CVaR (Expected Shortfall): mean of returns <= -var_value."""
    tail = [r for r in sorted_returns if r <= -var_value]
    if not tail:
        return var_value
    return -sum(tail) / len(tail)


def compute_parametric_var(
    returns: Sequence[float],
    confidence: float = 0.95,
) -> float:
    """Parametric VaR assuming a normal distribution.

    VaR = -(mean - z_score * std).
    Uses ``scipy.stats.norm.ppf`` for the z-score.

    Args:
        returns: Sequence of portfolio daily returns.
        confidence: Confidence level (e.g. 0.95).

    Returns:
        Positive VaR value (loss magnitude).
    """
    n = len(returns)
    if n < 2:
        return 0.0

    mean = sum(returns) / n
    variance = sum((r - mean) ** 2 for r in returns) / (n - 1)
    std = math.sqrt(variance)

    if std == 0.0:
        return 0.0

    z = scipy_stats.norm.ppf(1.0 - confidence)  # negative for left tail
    return -(mean + z * std)


# ---------------------------------------------------------------------------
# VaR gate
# ---------------------------------------------------------------------------


def check_var_gate(
    var_pct: float,
    max_var_pct: float = 0.02,
) -> tuple[bool, str]:
    """Gate check: block new positions if VaR exceeds *max_var_pct*.

    Args:
        var_pct: Current portfolio VaR as a decimal fraction of equity.
        max_var_pct: Maximum allowed VaR (default 2 %).

    Returns:
        (allowed, reason) tuple.
    """
    if var_pct > max_var_pct:
        return (
            False,
            f"VaR gate: {var_pct:.4f} > max {max_var_pct:.4f}",
        )
    return (True, f"VaR within limit: {var_pct:.4f} <= {max_var_pct:.4f}")


# ---------------------------------------------------------------------------
# Correlation-based sizing
# ---------------------------------------------------------------------------


def pearson_correlation(x: Sequence[float], y: Sequence[float]) -> float:
    """Compute Pearson correlation coefficient (stdlib math only).

    Args:
        x: First data series.
        y: Second data series (same length as *x*).

    Returns:
        Correlation in [-1.0, 1.0].  Returns 0.0 on degenerate input.
    """
    n = min(len(x), len(y))
    if n < 2:
        return 0.0

    mean_x = sum(x[:n]) / n
    mean_y = sum(y[:n]) / n

    cov = 0.0
    var_x = 0.0
    var_y = 0.0
    for i in range(n):
        dx = x[i] - mean_x
        dy = y[i] - mean_y
        cov += dx * dy
        var_x += dx * dx
        var_y += dy * dy

    denom = math.sqrt(var_x * var_y)
    if denom == 0.0:
        return 0.0

    return cov / denom


def compute_correlation_sizing(
    candidate_returns: Sequence[float],
    existing_returns: list[Sequence[float]],
    block_threshold: float = 0.85,
    penalty_start: float = 0.5,
) -> CorrelationSizingResult:
    """Compute position size adjustment based on portfolio correlation.

    Finds the maximum absolute Pearson correlation between *candidate_returns*
    and any series in *existing_returns*.

    - |corr| > block_threshold  -> blocked (multiplier = 0)
    - |corr| > penalty_start   -> linear penalty toward 0
    - |corr| <= penalty_start  -> multiplier = 1.0

    Args:
        candidate_returns: Return series of the candidate instrument.
        existing_returns: List of return series for currently held positions.
        block_threshold: Correlation above which the position is blocked.
        penalty_start: Correlation above which a linear penalty begins.

    Returns:
        CorrelationSizingResult with the adjusted multiplier.
    """
    if not existing_returns:
        return CorrelationSizingResult(
            adjusted_multiplier=1.0,
            max_correlation=0.0,
            blocked=False,
            reason="no existing positions",
        )

    max_corr = 0.0
    for series in existing_returns:
        corr = abs(pearson_correlation(candidate_returns, series))
        if corr > max_corr:
            max_corr = corr

    if max_corr > block_threshold:
        return CorrelationSizingResult(
            adjusted_multiplier=0.0,
            max_correlation=max_corr,
            blocked=True,
            reason=f"correlation {max_corr:.3f} > block threshold {block_threshold}",
        )

    if max_corr > penalty_start:
        span = block_threshold - penalty_start
        multiplier = 1.0 - (max_corr - penalty_start) / span
        multiplier = max(0.0, min(multiplier, 1.0))
        return CorrelationSizingResult(
            adjusted_multiplier=round(multiplier, 4),
            max_correlation=max_corr,
            blocked=False,
            reason=f"correlation penalty: {max_corr:.3f} in [{penalty_start}, {block_threshold}]",
        )

    return CorrelationSizingResult(
        adjusted_multiplier=1.0,
        max_correlation=max_corr,
        blocked=False,
        reason=f"correlation {max_corr:.3f} below penalty start {penalty_start}",
    )


# ---------------------------------------------------------------------------
# Regime position limits
# ---------------------------------------------------------------------------


def compute_regime_position_limit(
    regime: str,
    current_positions: int = 0,
    limits: dict[str, int] | None = None,
) -> RegimeLimits:
    """Check if new positions can be opened under the current regime.

    Default limits per regime:
        normal=5, risk_off=3, crisis=1, war_footing=2,
        energy_shock=2, sanctions=2.

    Args:
        regime: Regime name string (lowercase, matching MarketRegime values).
        current_positions: Number of currently open positions.
        limits: Optional override for the regime->max_positions mapping.

    Returns:
        RegimeLimits with ``can_open`` indicating whether another position
        may be opened.
    """
    lim = limits if limits is not None else _DEFAULT_REGIME_LIMITS
    max_pos = lim.get(regime, 5)

    can_open = current_positions < max_pos
    if can_open:
        reason = f"{regime}: {current_positions}/{max_pos} positions, room for more"
    else:
        reason = f"{regime}: {current_positions}/{max_pos} positions, limit reached"

    return RegimeLimits(
        regime=regime,
        max_positions=max_pos,
        current_positions=current_positions,
        can_open=can_open,
        reason=reason,
    )
