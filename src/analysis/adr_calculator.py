"""Average Daily Range (ADR) calculator.

Computes the 20-day ADR for instruments using daily price data.
ADR = mean(high - low) over the last N trading days.

All functions are pure: no DB, no HTTP, no side effects.
"""

from __future__ import annotations

from typing import NamedTuple


class ADRResult(NamedTuple):
    """ADR calculation result for a single instrument."""

    instrument: str
    adr: float          # Absolute ADR in price units
    adr_pct: float      # ADR as percentage of current price
    current_price: float
    days_used: int       # Actual number of days used in calculation


def calculate_adr(
    instrument: str,
    highs: list[float],
    lows: list[float],
    current_price: float,
    period: int = 20,
) -> ADRResult:
    """Calculate Average Daily Range for an instrument.

    Args:
        instrument: Instrument key (e.g. "EURUSD").
        highs: List of daily high prices, most recent last.
        lows: List of daily low prices, most recent last.
        current_price: Current/latest price.
        period: Number of days to average (default 20).

    Returns:
        ADRResult with absolute and percentage ADR.

    Raises:
        ValueError: If highs and lows have different lengths or are empty.
    """
    if len(highs) != len(lows):
        raise ValueError(f"highs ({len(highs)}) and lows ({len(lows)}) must have same length")
    if not highs:
        raise ValueError("No price data provided")

    # Take the last `period` days
    h = highs[-period:]
    lo = lows[-period:]
    days_used = len(h)

    ranges = [high - low for high, low in zip(h, lo) if high > 0 and low > 0]
    if not ranges:
        return ADRResult(
            instrument=instrument,
            adr=0.0,
            adr_pct=0.0,
            current_price=current_price,
            days_used=0,
        )

    adr = sum(ranges) / len(ranges)
    adr_pct = (adr / current_price * 100) if current_price > 0 else 0.0

    return ADRResult(
        instrument=instrument,
        adr=round(adr, 5),
        adr_pct=round(adr_pct, 2),
        current_price=current_price,
        days_used=days_used,
    )


def calculate_adr_batch(
    price_data: list[dict],
    period: int = 20,
) -> list[ADRResult]:
    """Calculate ADR for multiple instruments.

    Args:
        price_data: List of dicts with keys:
            instrument, highs, lows, current_price
        period: Number of days to average.

    Returns:
        List of ADRResult sorted by adr_pct descending.
    """
    results = []
    for item in price_data:
        try:
            result = calculate_adr(
                instrument=item["instrument"],
                highs=item["highs"],
                lows=item["lows"],
                current_price=item["current_price"],
                period=period,
            )
            results.append(result)
        except (ValueError, KeyError):
            continue

    return sorted(results, key=lambda r: r.adr_pct, reverse=True)


def to_dict(result: ADRResult) -> dict:
    """Convert ADRResult to JSON-serializable dict."""
    return {
        "instrument": result.instrument,
        "adr": result.adr,
        "adr_pct": result.adr_pct,
        "current_price": result.current_price,
        "days_used": result.days_used,
    }
