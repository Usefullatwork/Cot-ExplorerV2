"""Pre-built tagged level dicts for setup_builder tests."""

from __future__ import annotations


def make_support_level(
    price: float,
    weight: int = 3,
    source: str = "D1_swing",
    zone_bottom: float | None = None,
) -> dict:
    """Create a support level dict."""
    d: dict = {"price": price, "source": source, "weight": weight}
    if zone_bottom is not None:
        d["zone_bottom"] = zone_bottom
    return d


def make_resistance_level(
    price: float,
    weight: int = 3,
    source: str = "D1_swing",
    zone_top: float | None = None,
) -> dict:
    """Create a resistance level dict."""
    d: dict = {"price": price, "source": source, "weight": weight}
    if zone_top is not None:
        d["zone_top"] = zone_top
    return d


# EURUSD-style levels (price ~1.0850)
EURUSD_SUPPORTS = [
    make_support_level(1.0800, weight=5, source="PWL"),
    make_support_level(1.0820, weight=3, source="D1_swing"),
    make_support_level(1.0835, weight=1, source="15m_pivot"),
]

EURUSD_RESISTANCES = [
    make_resistance_level(1.0900, weight=5, source="PWH"),
    make_resistance_level(1.0880, weight=3, source="D1_swing"),
    make_resistance_level(1.0860, weight=1, source="15m_pivot"),
]
