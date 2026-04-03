"""General-purpose bootstrap resampler — pure functions, no I/O.

Provides percentile-method bootstrap confidence intervals for arbitrary
statistics (mean, Sharpe ratio, etc.).
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import Callable, Sequence


@dataclass(frozen=True)
class BootstrapCI:
    """Bootstrap confidence interval result."""

    estimate: float
    ci_lower: float
    ci_upper: float
    n_bootstrap: int
    confidence: float


def bootstrap_ci(
    data: Sequence[float],
    stat_fn: Callable[[Sequence[float]], float],
    n_boot: int = 2000,
    confidence: float = 0.95,
    seed: int = 42,
) -> BootstrapCI:
    """Compute bootstrap confidence interval for any statistic.

    Args:
        data: Input data sequence (must be non-empty).
        stat_fn: Function that computes the statistic (e.g., mean).
        n_boot: Number of bootstrap resamples.
        confidence: Confidence level (0-1).
        seed: Random seed for reproducibility.

    Returns:
        BootstrapCI with point estimate, lower, upper bounds.

    Raises:
        ValueError: If data is empty or confidence is out of range.
    """
    if len(data) == 0:
        raise ValueError("data must be non-empty")
    if not 0 < confidence < 1:
        raise ValueError("confidence must be between 0 and 1 (exclusive)")

    rng = random.Random(seed)
    n = len(data)
    data_list = list(data)
    estimate = stat_fn(data_list)

    boot_stats: list[float] = []
    for _ in range(n_boot):
        sample = [rng.choice(data_list) for _ in range(n)]
        boot_stats.append(stat_fn(sample))

    boot_stats.sort()
    alpha = 1.0 - confidence
    lo_idx = max(0, int(math.floor((alpha / 2) * n_boot)))
    hi_idx = min(n_boot - 1, int(math.ceil((1 - alpha / 2) * n_boot)) - 1)

    return BootstrapCI(
        estimate=estimate,
        ci_lower=boot_stats[lo_idx],
        ci_upper=boot_stats[hi_idx],
        n_bootstrap=n_boot,
        confidence=confidence,
    )


def _sharpe_stat(
    returns: Sequence[float], periods_per_year: int,
) -> float:
    """Compute annualized Sharpe ratio from a sequence of returns."""
    n = len(returns)
    if n < 2:
        return 0.0
    mean_r = sum(returns) / n
    var_r = sum((r - mean_r) ** 2 for r in returns) / (n - 1)
    std_r = math.sqrt(var_r) if var_r > 0 else 0.0
    if std_r == 0.0:
        return 0.0
    return (mean_r / std_r) * math.sqrt(periods_per_year)


def bootstrap_sharpe_ci(
    returns: Sequence[float],
    n_boot: int = 1000,
    confidence: float = 0.95,
    seed: int = 42,
    periods_per_year: int = 52,
) -> BootstrapCI:
    """Bootstrap CI specifically for annualized Sharpe ratio.

    Computes Sharpe = (mean / std) * sqrt(periods_per_year) on each
    bootstrap resample.

    Args:
        returns: Sequence of periodic returns.
        n_boot: Number of bootstrap resamples.
        confidence: Confidence level (0-1).
        seed: Random seed for reproducibility.
        periods_per_year: Annualization factor (52 for weekly, 252 for daily).

    Returns:
        BootstrapCI for the annualized Sharpe ratio.

    Raises:
        ValueError: If returns is empty.
    """
    def stat_fn(data: Sequence[float]) -> float:
        return _sharpe_stat(data, periods_per_year)

    return bootstrap_ci(
        data=returns,
        stat_fn=stat_fn,
        n_boot=n_boot,
        confidence=confidence,
        seed=seed,
    )


def bootstrap_mean_ci(
    data: Sequence[float],
    n_boot: int = 2000,
    confidence: float = 0.95,
    seed: int = 42,
) -> BootstrapCI:
    """Convenience: bootstrap CI for the mean.

    Args:
        data: Input data sequence.
        n_boot: Number of bootstrap resamples.
        confidence: Confidence level (0-1).
        seed: Random seed for reproducibility.

    Returns:
        BootstrapCI for the sample mean.
    """
    def mean_fn(d: Sequence[float]) -> float:
        return sum(d) / len(d)

    return bootstrap_ci(
        data=data,
        stat_fn=mean_fn,
        n_boot=n_boot,
        confidence=confidence,
        seed=seed,
    )
