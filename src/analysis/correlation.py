"""Rolling Pearson correlation matrix for instrument pairs.

Uses only stdlib math — no numpy dependency.  Designed for the 12 core
instruments tracked by the platform.
"""

from __future__ import annotations

import math

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
