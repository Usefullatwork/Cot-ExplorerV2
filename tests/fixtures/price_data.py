"""Price data generators for tests — EURUSD-style prices with deterministic randomness."""

from __future__ import annotations

import random

BASE_PRICE = 1.0850
DAILY_ATR = 0.0060
INTRADAY_ATR_15M = 0.0012


def make_daily_rows(
    n: int = 30, base: float = BASE_PRICE, atr: float = DAILY_ATR, seed: int = 42
) -> list[tuple[float, float, float]]:
    """Generate n daily (high, low, close) rows with random walk."""
    rng = random.Random(seed)
    rows: list[tuple[float, float, float]] = []
    price = base
    for _ in range(n):
        move = rng.gauss(0, atr * 0.5)
        high = round(price + abs(rng.gauss(0, atr * 0.3)), 5)
        low = round(price - abs(rng.gauss(0, atr * 0.3)), 5)
        if high <= low:
            high = low + atr * 0.1
        close = round(low + rng.random() * (high - low), 5)
        rows.append((high, low, close))
        price = close + move
    return rows


def make_15m_rows(
    n: int = 200, base: float = BASE_PRICE, atr: float = INTRADAY_ATR_15M, seed: int = 42
) -> list[tuple[float, float, float]]:
    """Generate n 15-minute (high, low, close) rows."""
    return make_daily_rows(n=n, base=base, atr=atr, seed=seed)


def make_1h_rows(
    n: int = 100, base: float = BASE_PRICE, seed: int = 42
) -> list[tuple[float, float, float]]:
    """Generate n 1-hour rows."""
    return make_daily_rows(n=n, base=base, atr=DAILY_ATR * 0.4, seed=seed)


def make_smc_bullish_rows(n: int = 60, seed: int = 42) -> list[tuple[float, float, float]]:
    """Generate rows with clear HH/HL pattern for bullish SMC structure.

    Creates a zigzag pattern with upward bias so find_pivot_highs/lows
    can detect clear swing points.
    """
    import math

    rows: list[tuple[float, float, float]] = []
    base = 1.0800
    for i in range(n):
        # Zigzag with upward trend
        trend = 0.0001 * i
        zigzag = 0.0030 * math.sin(i * math.pi / 8)  # ~16 bar cycle
        mid = base + trend + zigzag
        spread = 0.0010
        high = round(mid + spread, 5)
        low = round(mid - spread, 5)
        close = round(mid + 0.0002, 5)
        rows.append((high, low, close))
    return rows


def make_smc_bearish_rows(n: int = 60, seed: int = 42) -> list[tuple[float, float, float]]:
    """Generate rows with clear LH/LL pattern for bearish SMC structure."""
    import math

    rows: list[tuple[float, float, float]] = []
    base = 1.0900
    for i in range(n):
        trend = -0.0001 * i
        zigzag = 0.0030 * math.sin(i * math.pi / 8)
        mid = base + trend + zigzag
        spread = 0.0010
        high = round(mid + spread, 5)
        low = round(mid - spread, 5)
        close = round(mid - 0.0002, 5)
        rows.append((high, low, close))
    return rows


def make_flat_rows(
    n: int = 30, price: float = BASE_PRICE
) -> list[tuple[float, float, float]]:
    """Generate n rows at exactly the same price (edge case testing)."""
    return [(price, price, price)] * n
