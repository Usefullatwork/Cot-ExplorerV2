"""COT data routes — latest positions, history, and summary."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from src.db import repository as repo

router = APIRouter(prefix="/api/v1", tags=["cot"])

_DATA_DIR = Path(__file__).resolve().parents[3] / "data"


@router.get("/cot")
def cot_latest() -> list[dict]:
    """All latest COT positions (from combined/latest.json or DB).

    Falls back to the static JSON file produced by fetch_cot.py when the
    database has not been populated yet.
    """
    combined_path = _DATA_DIR / "combined" / "latest.json"
    if combined_path.exists():
        with open(combined_path) as f:
            return json.load(f)
    return []


@router.get("/cot/{symbol}/history")
def cot_history(
    symbol: str,
    start: Optional[str] = Query(None, description="Start date YYYY-MM-DD"),
    end: Optional[str] = Query(None, description="End date YYYY-MM-DD"),
    report_type: Optional[str] = Query(None, description="tff, legacy, disaggregated, supplemental"),
) -> list[dict]:
    """Time series of COT positions for a given symbol."""
    rows = repo.get_cot_history(
        symbol=symbol,
        start=start,
        end=end,
        report_type=report_type,
    )
    if not rows:
        raise HTTPException(status_code=404, detail=f"No COT data for symbol {symbol}")
    return [
        {
            "date": r.date,
            "symbol": r.symbol,
            "market": r.market,
            "report_type": r.report_type,
            "open_interest": r.open_interest,
            "change_oi": r.change_oi,
            "spec_long": r.spec_long,
            "spec_short": r.spec_short,
            "spec_net": r.spec_net,
            "comm_long": r.comm_long,
            "comm_short": r.comm_short,
            "comm_net": r.comm_net,
            "nonrept_long": r.nonrept_long,
            "nonrept_short": r.nonrept_short,
            "nonrept_net": r.nonrept_net,
            "change_spec_net": r.change_spec_net,
            "category": r.category,
        }
        for r in rows
    ]


@router.get("/cot/summary")
def cot_summary() -> dict:
    """Top movers and positioning extremes from latest combined data."""
    combined_path = _DATA_DIR / "combined" / "latest.json"
    if not combined_path.exists():
        return {"top_movers": [], "extremes": []}

    with open(combined_path) as f:
        data: list[dict] = json.load(f)

    # Top movers — largest absolute change in speculator net
    movers = sorted(data, key=lambda d: abs(d.get("change_spec_net", 0)), reverse=True)
    top_movers = [
        {
            "market": m.get("navn_no", m.get("market", "")),
            "symbol": m.get("symbol", ""),
            "change_spec_net": m.get("change_spec_net", 0),
            "report": m.get("report", ""),
        }
        for m in movers[:10]
    ]

    # Extremes — markets where speculators are most lopsided
    def _spec_ratio(d: dict) -> float:
        spec = d.get("spekulanter", {})
        total = spec.get("long", 0) + spec.get("short", 0)
        if total == 0:
            return 0.5
        return spec.get("long", 0) / total

    with_ratio = [(d, _spec_ratio(d)) for d in data]
    with_ratio.sort(key=lambda x: abs(x[1] - 0.5), reverse=True)
    extremes = [
        {
            "market": d.get("navn_no", d.get("market", "")),
            "symbol": d.get("symbol", ""),
            "long_pct": round(r * 100, 1),
            "short_pct": round((1 - r) * 100, 1),
            "report": d.get("report", ""),
        }
        for d, r in with_ratio[:10]
    ]

    return {"top_movers": top_movers, "extremes": extremes}
