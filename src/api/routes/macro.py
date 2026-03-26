"""Macro data routes — Dollar Smile, VIX regime, indicators."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter

from src.api.middleware.cache import macro_cache
from src.db import repository as repo

router = APIRouter(prefix="/api/v1", tags=["macro"])

_DATA_DIR = Path(__file__).resolve().parents[3] / "data"


@router.get(
    "/macro",
    summary="Full macro panel",
    description=(
        "Returns the complete macro environment: Dollar Smile, VIX regime, conflicts, prices, calendar."
        " Prefers DB snapshot; falls back to data/macro/latest.json."
    ),
)
def macro_panel() -> dict:
    """Full macro panel: Dollar Smile, VIX regime, conflicts, prices.

    Prefers the DB snapshot; falls back to data/macro/latest.json.
    """
    cached = macro_cache.get("macro_panel")
    if cached is not None:
        return cached

    snap = repo.get_latest_macro()
    if snap and snap.full_json:
        result = json.loads(snap.full_json)
        macro_cache.set("macro_panel", result)
        return result

    macro_path = _DATA_DIR / "macro" / "latest.json"
    if macro_path.exists():
        with open(macro_path) as f:
            result = json.load(f)
        macro_cache.set("macro_panel", result)
        return result

    return {"error": "No macro data available. Run the pipeline first."}


@router.get(
    "/macro/indicators",
    summary="Macro indicators subset",
    description="Returns price data for key macro indicators: HYG, TIP, TNX, IRX, Copper, EEM.",
)
def macro_indicators() -> dict:
    """Subset of macro indicators: HYG, TIP, TNX, IRX, Copper, EEM.

    Falls back to reading from data/macro/latest.json prices dict.
    """
    cached = macro_cache.get("macro_indicators")
    if cached is not None:
        return cached

    snap = repo.get_latest_macro()
    if snap and snap.full_json:
        full = json.loads(snap.full_json)
        prices = full.get("prices", {})
    else:
        macro_path = _DATA_DIR / "macro" / "latest.json"
        if macro_path.exists():
            with open(macro_path) as f:
                prices = json.load(f).get("prices", {})
        else:
            return {}

    indicator_keys = ["HYG", "TIP", "TNX", "IRX", "Copper", "EEM"]
    result = {k: prices[k] for k in indicator_keys if k in prices}
    macro_cache.set("macro_indicators", result)
    return result
