"""Rolling Pearson correlation matrix for instrument pairs.

Uses only stdlib math — no numpy dependency.  Designed for the 12 core
instruments tracked by the platform.
"""

from __future__ import annotations

import math
from typing import Sequence

# The 12 instruments to correlate.
INSTRUMENTS: list[str] = [
    "EURUSD", "USDJPY", "GBPUSD", "AUDUSD",
    "XAUUSD", "XAGUSD", "UKOIL", "USOIL",
    "SPX", "NAS100", "DXY", "VIX",
]


def pearson(x: list[float], y: list[float]) -> float:
    """Pure Pearson correlation coefficient between two equal-length series.

    Returns 0.0 for degenerate inputs (len < 2 or zero variance).
    """
    n = min(len(x), len(y))
    if n < 2:
        return 0.0

    mean_x = math.fsum(x[:n]) / n
    mean_y = math.fsum(y[:n]) / n

    num = 0.0
    var_x = 0.0
    var_y = 0.0
    for i in range(n):
        dx = x[i] - mean_x
        dy = y[i] - mean_y
        num += dx * dy
        var_x += dx * dx
        var_y += dy * dy

    if var_x == 0.0 or var_y == 0.0:
        return 0.0

    return num / math.sqrt(var_x * var_y)


def calculate_correlation_matrix(
    price_data: dict[str, list[float]],
    window: int = 20,
) -> dict[tuple[str, str], float]:
    """Compute rolling Pearson correlation between all instrument pairs.

    Parameters
    ----------
    price_data:
        Mapping of instrument key -> list of daily close prices (oldest first).
        Only instruments present in the dict are included.
    window:
        Number of trailing observations to use.  Defaults to 20 (one trading
        month).

    Returns
    -------
    dict keyed by ``(instrument_a, instrument_b)`` with the correlation float.
    Pairs are stored in alphabetical order to avoid duplicates.
    Self-correlations (a, a) are omitted.
    """
    keys = sorted(k for k in price_data if len(price_data[k]) >= window)
    matrix: dict[tuple[str, str], float] = {}

    for i, a in enumerate(keys):
        tail_a = price_data[a][-window:]
        for b in keys[i + 1 :]:
            tail_b = price_data[b][-window:]
            corr = pearson(tail_a, tail_b)
            pair = (a, b) if a < b else (b, a)
            matrix[pair] = round(corr, 6)

    return matrix


# ---------------------------------------------------------------------------
# EWMA correlation
# ---------------------------------------------------------------------------


def ewma_correlation(
    returns_a: Sequence[float],
    returns_b: Sequence[float],
    halflife: int = 10,
) -> float:
    """Exponentially-weighted moving average correlation.

    lambda = 1 - 2/(halflife+1)
    Compute EWMA covariance and EWMA variances, then
    corr = cov / (std_a * std_b).

    More responsive to recent data than rolling Pearson.

    Args:
        returns_a: Return series for instrument A.
        returns_b: Return series for instrument B (same length).
        halflife: Decay halflife in periods (default 10).

    Returns:
        Correlation in [-1.0, 1.0].  Returns 0.0 on degenerate input.
    """
    n = min(len(returns_a), len(returns_b))
    if n < 2:
        return 0.0

    decay = 1.0 - 2.0 / (halflife + 1)

    # Compute EWMA means
    mean_a = 0.0
    mean_b = 0.0
    weight_sum = 0.0
    for i in range(n):
        w = decay ** (n - 1 - i)
        mean_a += w * returns_a[i]
        mean_b += w * returns_b[i]
        weight_sum += w

    if weight_sum == 0.0:
        return 0.0

    mean_a /= weight_sum
    mean_b /= weight_sum

    # Compute EWMA covariance and variances
    cov = 0.0
    var_a = 0.0
    var_b = 0.0
    for i in range(n):
        w = decay ** (n - 1 - i)
        da = returns_a[i] - mean_a
        db = returns_b[i] - mean_b
        cov += w * da * db
        var_a += w * da * da
        var_b += w * db * db

    denom = math.sqrt(var_a * var_b)
    if denom == 0.0:
        return 0.0

    result = cov / denom
    return max(-1.0, min(result, 1.0))


# ---------------------------------------------------------------------------
# Correlation regime change detection
# ---------------------------------------------------------------------------


def correlation_regime_change(
    rolling_correlations: Sequence[float],
    threshold_std: float = 2.0,
) -> tuple[bool, float | None]:
    """Detect correlation breakdown/spike.

    Computes mean and std of the correlation series.
    If latest value deviates > threshold_std from mean, flag as regime change.

    Args:
        rolling_correlations: Time series of rolling correlation values.
        threshold_std: Number of standard deviations for detection (default 2.0).

    Returns:
        (is_changed, deviation_score or None).
        is_changed is True when the latest correlation deviates significantly.
    """
    n = len(rolling_correlations)
    if n < 3:
        return (False, None)

    mean = math.fsum(rolling_correlations) / n
    variance = math.fsum((x - mean) ** 2 for x in rolling_correlations) / n
    std = math.sqrt(variance)

    if std == 0.0:
        return (False, None)

    latest = rolling_correlations[-1] if hasattr(rolling_correlations, '__getitem__') else list(rolling_correlations)[-1]
    deviation = abs(latest - mean) / std

    if deviation > threshold_std:
        return (True, round(deviation, 4))
    return (False, round(deviation, 4))


# ---------------------------------------------------------------------------
# Portfolio correlation penalty
# ---------------------------------------------------------------------------


def portfolio_correlation_penalty(
    candidate_returns: Sequence[float],
    existing_returns: list[Sequence[float]],
    block_threshold: float = 0.85,
    penalty_start: float = 0.50,
    halflife: int = 10,
) -> tuple[float, float]:
    """Compute position size penalty based on portfolio correlation.

    Finds max absolute correlation between candidate and any existing
    position using EWMA correlation.

    Args:
        candidate_returns: Return series for the candidate instrument.
        existing_returns: List of return series for current positions.
        block_threshold: Correlation above which position is blocked.
        penalty_start: Correlation above which linear penalty begins.
        halflife: EWMA halflife for correlation computation.

    Returns:
        (multiplier, max_correlation).
        - corr > block_threshold: multiplier = 0.0 (blocked)
        - corr > penalty_start: linear penalty toward 0
        - corr <= penalty_start: multiplier = 1.0
    """
    if not existing_returns:
        return (1.0, 0.0)

    max_corr = 0.0
    for series in existing_returns:
        corr = abs(ewma_correlation(candidate_returns, series, halflife))
        if corr > max_corr:
            max_corr = corr

    if max_corr > block_threshold:
        return (0.0, max_corr)

    if max_corr > penalty_start:
        span = block_threshold - penalty_start
        if span <= 0.0:
            return (0.0, max_corr)
        multiplier = 1.0 - (max_corr - penalty_start) / span
        return (max(0.0, min(multiplier, 1.0)), max_corr)

    return (1.0, max_corr)
