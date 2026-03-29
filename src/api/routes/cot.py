"""COT data routes — latest positions, history, and summary."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from src.db import repository as repo
from src.security.input_validator import sanitize_string, validate_symbol

router = APIRouter(prefix="/api/v1", tags=["cot"])

_DATA_DIR = Path(__file__).resolve().parents[3] / "data"

# ── Sparkline cache (timeseries → last N spec_net values) ───────────────────

_SPARKLINE_WEEKS = 20
_ts_cache: dict[str, list[int]] | None = None


def _load_timeseries_cache() -> dict[str, list[int]]:
    """Load timeseries JSON files into a lookup of symbol_report → spec_net values.

    Returns an empty dict if the timeseries directory doesn't exist yet.
    """
    ts_dir = _DATA_DIR / "timeseries"
    cache: dict[str, list[int]] = {}
    if not ts_dir.is_dir():
        return cache

    for fpath in ts_dir.glob("*.json"):
        if fpath.name == "index.json":
            continue
        try:
            with open(fpath, encoding="utf-8") as f:
                ts = json.load(f)
            data = ts.get("data", [])
            if len(data) < 2:
                continue
            values = [d["spec_net"] for d in data[-_SPARKLINE_WEEKS:]]
            key = f"{ts['symbol'].lower()}_{ts['report']}"
            cache[key] = values
        except (KeyError, ValueError, TypeError):
            continue

    return cache


def _get_sparkline_cache() -> dict[str, list[int]]:
    """Return the cached timeseries data, loading on first call."""
    global _ts_cache  # noqa: PLW0603
    if _ts_cache is None:
        _ts_cache = _load_timeseries_cache()
    return _ts_cache


# ── Response models ──────────────────────────────────────────────────────────


class CotPositionResponse(BaseModel):
    """A single COT position record with speculator, commercial, and non-reportable breakdowns."""

    date: str = Field(..., description="Report date (YYYY-MM-DD)", examples=["2026-03-21"])
    symbol: str = Field(..., description="CFTC contract code", examples=["099741"])
    market: str = Field(..., description="Market name", examples=["Euro Fx"])
    report_type: str = Field("", description="Report type", examples=["tff"])
    open_interest: int = Field(0, description="Total open interest")
    change_oi: int = Field(0, description="Change in open interest")
    spec_long: int = Field(0, description="Speculator long positions")
    spec_short: int = Field(0, description="Speculator short positions")
    spec_net: int = Field(0, description="Speculator net (long - short)")
    comm_long: int = Field(0, description="Commercial long positions")
    comm_short: int = Field(0, description="Commercial short positions")
    comm_net: int = Field(0, description="Commercial net (long - short)")
    nonrept_long: int = Field(0, description="Non-reportable long positions")
    nonrept_short: int = Field(0, description="Non-reportable short positions")
    nonrept_net: int = Field(0, description="Non-reportable net (long - short)")
    change_spec_net: int = Field(0, description="Weekly change in speculator net")
    category: Optional[str] = Field(None, description="Asset category", examples=["valuta"])

    model_config = {"extra": "allow"}


class CotMoverItem(BaseModel):
    """A top mover in COT positioning."""

    market: str = Field(..., description="Market name")
    symbol: str = Field(..., description="CFTC contract code")
    change_spec_net: int = Field(0, description="Change in speculator net positioning")
    report: str = Field("", description="Report type")


class CotExtremeItem(BaseModel):
    """A market with extreme speculator positioning."""

    market: str = Field(..., description="Market name")
    symbol: str = Field(..., description="CFTC contract code")
    long_pct: float = Field(..., description="Speculator long percentage")
    short_pct: float = Field(..., description="Speculator short percentage")
    report: str = Field("", description="Report type")


class CotSummaryResponse(BaseModel):
    """COT summary with top movers and positioning extremes."""

    top_movers: list[CotMoverItem] = Field(default_factory=list, description="Top 10 largest weekly changes")
    extremes: list[CotExtremeItem] = Field(default_factory=list, description="Top 10 most lopsided positions")


# ── Endpoints ────────────────────────────────────────────────────────────────


@router.get(
    "/cot",
    response_model=list[CotPositionResponse],
    summary="Latest COT positions",
    description="Returns all latest COT positions from the combined data file or database.",
)
def cot_latest() -> list[dict]:
    """All latest COT positions (from combined/latest.json or DB).

    Falls back to the static JSON file produced by fetch_cot.py when the
    database has not been populated yet.
    """
    combined_path = _DATA_DIR / "combined" / "latest.json"
    if not combined_path.exists():
        combined_path = _DATA_DIR / "cot" / "combined" / "latest.json"
    if not combined_path.exists():
        return []

    with open(combined_path, encoding="utf-8") as f:
        markets: list[dict] = json.load(f)

    # Map "report" → "report_type" for Pydantic response model
    for m in markets:
        if "report_type" not in m and "report" in m:
            m["report_type"] = m["report"]

    # Inject sparkline data from timeseries cache
    ts = _get_sparkline_cache()
    if ts:
        for m in markets:
            sym = (m.get("symbol") or "").lower()
            report = m.get("report_type", m.get("report", ""))
            key = f"{sym}_{report}"
            history = ts.get(key)
            if history:
                m["cot_history"] = history

    return markets


@router.get(
    "/cot/{symbol}/history",
    response_model=list[CotPositionResponse],
    summary="COT history for a symbol",
    description="Returns a time series of COT positions for a given CFTC contract symbol.",
)
def cot_history(
    symbol: str,
    start: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    end: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
    report_type: Optional[str] = Query(None, description="Report type: tff, legacy, disaggregated, or supplemental"),
) -> list[dict]:
    """Time series of COT positions for a given symbol."""
    try:
        symbol = validate_symbol(symbol)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if start:
        start = sanitize_string(start, max_length=10)
    if end:
        end = sanitize_string(end, max_length=10)
    if report_type:
        report_type = sanitize_string(report_type, max_length=50)

    rows = repo.get_cot_history(
        symbol=symbol,
        start=start,
        end=end,
        report_type=report_type,
    )
    if rows:
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

    # Fallback: read from combined JSON and filter by symbol
    for path in [_DATA_DIR / "combined" / "latest.json", _DATA_DIR / "cot" / "combined" / "latest.json"]:
        if not path.exists():
            continue
        try:
            with open(path, encoding="utf-8") as f:
                all_markets: list[dict] = json.load(f)
        except (json.JSONDecodeError, OSError):
            continue
        matches = [m for m in all_markets if m.get("symbol") == symbol]
        if report_type:
            matches = [m for m in matches if m.get("report") == report_type]
        if matches:
            for m in matches:
                if "report_type" not in m and "report" in m:
                    m["report_type"] = m["report"]
            return matches

    raise HTTPException(status_code=404, detail=f"No COT data for symbol {symbol}")


@router.get(
    "/cot/summary",
    response_model=CotSummaryResponse,
    summary="COT summary",
    description="Returns the top 10 movers (largest weekly change) and top 10 positioning extremes.",
)
def cot_summary() -> dict:
    """Top movers and positioning extremes from latest combined data."""
    combined_path = _DATA_DIR / "combined" / "latest.json"
    if not combined_path.exists():
        combined_path = _DATA_DIR / "cot" / "combined" / "latest.json"
    if not combined_path.exists():
        return {"top_movers": [], "extremes": []}

    with open(combined_path, encoding="utf-8") as f:
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
