"""COT (Commitment of Traders) analysis — pure functions, no side effects.

Provides classification of COT data for bias, momentum, and instrument lookup.
"""

from __future__ import annotations

from typing import Optional


def classify_cot_bias(spec_net: float, oi: float) -> tuple[str, float]:
    """Classify COT directional bias from speculator net position and open interest.

    Returns (bias_label, pct) where:
      - bias_label: "LONG" if pct > 4, "SHORT" if pct < -4, "NOYTRAL" otherwise
      - pct: spec_net / oi * 100

    Matches v1 logic (fetch_all.py lines 898-901).
    """
    if oi == 0:
        oi = 1
    pct = spec_net / oi * 100
    if pct > 4:
        bias = "LONG"
    elif pct < -4:
        bias = "SHORT"
    else:
        bias = "NØYTRAL"
    return bias, pct


def classify_cot_momentum(change_spec_net: float, spec_net: float) -> str:
    """Classify COT positioning momentum.

    Returns one of:
      - "ØKER"   — adding to existing position direction
      - "SNUR"   — reducing / reversing position
      - "STABIL" — no change

    Matches v1 logic (fetch_all.py lines 902-908).
    """
    if change_spec_net == 0:
        return "STABIL"
    elif (change_spec_net > 0 and spec_net >= 0) or (change_spec_net < 0 and spec_net <= 0):
        return "ØKER"
    else:
        return "SNUR"


def get_cot_for_instrument(
    cot_data: dict[str, dict],
    instrument_key: str,
    cot_map: dict[str, str],
) -> Optional[dict]:
    """Look up COT data for an instrument.

    Args:
        cot_data: Dict keyed by lowercase market name -> COT record.
        instrument_key: The instrument key (e.g. "EURUSD", "Gold").
        cot_map: Mapping from instrument key to COT market name
                 (e.g. {"EURUSD": "euro fx", "Gold": "gold"}).

    Returns the COT record dict, or None if not found.
    """
    cot_key = cot_map.get(instrument_key, "")
    return cot_data.get(cot_key) if cot_key else None
