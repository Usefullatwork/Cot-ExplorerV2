"""Geo-intelligence API routes: seismic, COMEX inventory, news intel, chokepoints, signals."""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.analysis.geo_classifier import GeoEventType, classify_and_score
from src.analysis.geo_signals import GeoSignal, generate_geo_signals
from src.analysis.regime_detector import (
    ENERGY_INSTRUMENTS,
    RISK_ASSETS,
    SAFE_HAVENS,
    MarketRegime,
    detect_regime,
    get_regime_adjustments,
)
from src.db.engine import session_ctx
from src.db.models import ComexInventory, GeoIntelArticle, SeismicEvent
from src.trading.scrapers import chokepoints, comex, energy_infra, intel_feed, seismic

router = APIRouter(prefix="/api/v1/geointel", tags=["geointel"])

_COLOR = {"gold": "#FFD700", "silver": "#C0C0C0", "copper": "#B87333", "geopolitical": "#FF4444"}


def _run_query(fn: Any) -> Any:
    """Execute *fn(session)* inside a transactional scope and return the result."""
    with session_ctx() as session:
        return fn(session)


# ── Response models ──────────────────────────────────────────────────────────

class SeismicEventResponse(BaseModel):
    id: int; mag: float; lat: float; lon: float; depth_km: float
    place: str; event_time: str; region: Optional[str] = None; url: str

class ComexMetalResponse(BaseModel):
    metal: str; registered: int; eligible: int; total: int; coverage_pct: float

class ComexResponse(BaseModel):
    gold: Optional[ComexMetalResponse] = None; silver: Optional[ComexMetalResponse] = None
    copper: Optional[ComexMetalResponse] = None; stress_index: float = 0.0

class IntelArticleResponse(BaseModel):
    title: str; url: str; source: str; time: str; category: str; color: str

class ChokepointResponse(BaseModel):
    name: str; lat: float; lon: float; throughput: str
    cargo_types: list[str]; affected_instruments: list[str]; risk_level: str


# ── Endpoints ────────────────────────────────────────────────────────────────

@router.get("/seismic", response_model=list[SeismicEventResponse], summary="Mining-region earthquakes")
def get_seismic(live: bool = Query(False, description="Force live fetch from USGS")) -> list[dict]:
    """Return seismic events from DB or live fetch."""
    if live:
        events = seismic.fetch()
        _store_seismic(events)
        return [{"id": 0, "mag": e["mag"], "lat": e["lat"], "lon": e["lon"], "depth_km": e["depth_km"],
                 "place": e["place"], "event_time": str(e["time"]), "region": e["region"], "url": e["url"]}
                for e in events]

    def _q(s: Session) -> list[dict]:
        rows = s.execute(select(SeismicEvent).order_by(SeismicEvent.fetched_at.desc()).limit(100)).scalars().all()
        return [{"id": r.id, "mag": r.mag, "lat": r.lat, "lon": r.lon, "depth_km": r.depth_km,
                 "place": r.place, "event_time": r.event_time, "region": r.region, "url": r.url} for r in rows]
    return _run_query(_q)


@router.get("/comex", response_model=ComexResponse, summary="COMEX warehouse inventory")
def get_comex(live: bool = Query(False, description="Force live fetch from CME")) -> dict:
    """Return COMEX inventory from DB or live fetch."""
    if live:
        data = comex.fetch()
        _store_comex(data)
        return {k: data.get(k) for k in ("gold", "silver", "copper", "stress_index")}

    def _q(s: Session) -> dict:
        result: dict[str, Any] = {"gold": None, "silver": None, "copper": None, "stress_index": 0.0}
        for metal in ("gold", "silver", "copper"):
            row = s.execute(select(ComexInventory).where(ComexInventory.metal == metal)
                            .order_by(ComexInventory.fetched_at.desc()).limit(1)).scalar()
            if row:
                result[metal] = {"metal": row.metal, "registered": row.registered, "eligible": row.eligible,
                                 "total": row.total, "coverage_pct": row.coverage_pct}
                result["stress_index"] = max(result["stress_index"], row.stress_index)
        return result
    return _run_query(_q)


@router.get("/intel", response_model=list[IntelArticleResponse], summary="Geo-intelligence news")
def get_intel(
    live: bool = Query(False, description="Force live fetch from Google News"),
    category: Optional[str] = Query(None, description="Filter: gold, silver, copper, geopolitical"),
) -> list[dict]:
    """Return intel articles from DB or live fetch."""
    if live:
        articles = intel_feed.fetch()
        _store_articles(articles)
        return [a for a in articles if not category or a["category"] == category]

    def _q(s: Session) -> list[dict]:
        stmt = select(GeoIntelArticle).order_by(GeoIntelArticle.fetched_at.desc()).limit(100)
        if category:
            stmt = stmt.where(GeoIntelArticle.category == category)
        rows = s.execute(stmt).scalars().all()
        return [{"title": r.title, "url": r.url, "source": r.source, "time": r.published_at,
                 "category": r.category, "color": _COLOR.get(r.category, "#888888")} for r in rows]
    return _run_query(_q)


@router.get("/chokepoints", response_model=list[ChokepointResponse], summary="Maritime chokepoints with risk")
def get_chokepoints_route(
    assess: bool = Query(False, description="Assess risk using latest intel articles"),
) -> list[dict]:
    """Return chokepoints, optionally with risk assessed from news."""
    if not assess:
        return chokepoints.get_chokepoints()

    def _q(s: Session) -> list[dict]:
        rows = s.execute(select(GeoIntelArticle).order_by(GeoIntelArticle.fetched_at.desc()).limit(50)).scalars().all()
        return chokepoints.assess_risk([{"title": r.title} for r in rows])
    return _run_query(_q)


@router.get("/energy-infra", summary="Energy infrastructure map data")
def get_energy_infra() -> dict:
    """Return pipelines, LNG terminals, and shipping lanes for map overlay."""
    return {
        "pipelines": energy_infra.PIPELINES,
        "lng_terminals": energy_infra.LNG_TERMINALS,
        "shipping_lanes": energy_infra.SHIPPING_LANES,
    }


@router.get("/mine-locations", summary="Mining operation locations")
def get_mine_locations() -> dict:
    """Return global mining operation locations with commodity metadata."""
    return {"mines": energy_infra.MINES}


# ── DB persistence helpers ───────────────────────────────────────────────────

def _store_seismic(events: list[dict]) -> None:
    if not events:
        return
    now = datetime.now(timezone.utc)
    def _w(s: Session) -> None:
        for e in events:
            s.add(SeismicEvent(mag=e["mag"], lat=e["lat"], lon=e["lon"], depth_km=e["depth_km"],
                               place=e["place"], event_time=str(e["time"]), region=e.get("region"),
                               url=e["url"], fetched_at=now))
    _run_query(_w)

def _store_comex(data: dict) -> None:
    now, stress = datetime.now(timezone.utc), data.get("stress_index", 0.0)
    def _w(s: Session) -> None:
        for metal in ("gold", "silver", "copper"):
            m = data.get(metal)
            if m:
                s.add(ComexInventory(metal=metal, registered=m["registered"], eligible=m["eligible"],
                                     total=m["total"], coverage_pct=m["coverage_pct"],
                                     stress_index=stress, fetched_at=now))
    _run_query(_w)

def _store_articles(articles: list[dict]) -> None:
    if not articles:
        return
    now = datetime.now(timezone.utc)
    def _w(s: Session) -> None:
        for a in articles:
            s.add(GeoIntelArticle(title=a["title"], url=a["url"], source=a["source"],
                                  published_at=a.get("time", ""), category=a["category"], fetched_at=now))
    _run_query(_w)


# ── Geo-signal response models ──────────────────────────────────────────────

class TradeImpactResponse(BaseModel):
    instrument: str
    direction: str
    strength: str
    reasoning: str

class GeoSignalResponse(BaseModel):
    event_type: str
    confidence: float
    impacts: list[TradeImpactResponse]
    source_articles: list[dict]
    generated_at: str
    expires_hours: int

class ClassifiedEventResponse(BaseModel):
    title: str
    source: str
    event_types: list[dict]  # [{type, confidence}, ...]


class RegimeResponse(BaseModel):
    regime: str
    adjustments: dict
    safe_havens: list[str]
    risk_assets: list[str]
    energy_instruments: list[str]
    safe_haven_only: bool


# ── Geo-signal endpoints ────────────────────────────────────────────────────

@router.get("/regime", response_model=RegimeResponse, summary="Current market regime")
def get_regime(
    vix_price: float = Query(15.0, description="Current VIX price"),
    vix_5d_change: float = Query(0.0, description="VIX 5-day percentage change"),
    oil_5d_change: float = Query(0.0, description="Oil 5-day percentage change"),
    dxy_5d_change: float = Query(0.0, description="DXY 5-day percentage change"),
    geo_events: str = Query("", description="Comma-separated GeoEventType values"),
) -> dict:
    """Return the current market regime with parameter adjustments.

    Accepts macro indicators and active geo-event types, returns the
    detected regime, parameter overrides, and affected instrument lists.
    """
    active_events = [e.strip() for e in geo_events.split(",") if e.strip()]

    regime = detect_regime(
        vix_price=vix_price,
        vix_5d_change=vix_5d_change,
        oil_5d_change=oil_5d_change,
        active_geo_events=active_events,
        dxy_5d_change=dxy_5d_change,
    )
    adjustments = get_regime_adjustments(regime)

    return {
        "regime": regime.value,
        "adjustments": adjustments,
        "safe_havens": sorted(SAFE_HAVENS),
        "risk_assets": sorted(RISK_ASSETS),
        "energy_instruments": sorted(ENERGY_INSTRUMENTS),
        "safe_haven_only": adjustments.get("safe_haven_only", False),
    }


@router.get("/signals", response_model=list[GeoSignalResponse], summary="Active geo-signals")
def get_geo_signals(
    live: bool = Query(False, description="Force live fetch of articles before generating signals"),
) -> list[dict]:
    """Return active pre-trade geo-signals (not expired).

    Fetches articles from DB (or live if requested), classifies them,
    and generates directional trade signals per event type.
    """
    if live:
        articles = intel_feed.fetch()
        _store_articles(articles)
    else:
        def _q(s: Session) -> list[dict]:
            rows = s.execute(
                select(GeoIntelArticle).order_by(GeoIntelArticle.fetched_at.desc()).limit(100)
            ).scalars().all()
            return [{"title": r.title, "url": r.url, "source": r.source,
                     "time": r.published_at, "category": r.category} for r in rows]
        articles = _run_query(_q)

    signals = generate_geo_signals(articles)

    # Convert dataclass signals to dicts for JSON serialisation.
    result: list[dict] = []
    for sig in signals:
        result.append({
            "event_type": sig.event_type.value,
            "confidence": sig.confidence,
            "impacts": [asdict(imp) for imp in sig.impacts],
            "source_articles": sig.source_articles,
            "generated_at": sig.generated_at,
            "expires_hours": sig.expires_hours,
        })
    return result


@router.get("/events", response_model=list[ClassifiedEventResponse], summary="Classified events")
def get_classified_events(
    live: bool = Query(False, description="Force live fetch of articles"),
    category: Optional[str] = Query(None, description="Filter: gold, silver, copper, geopolitical"),
) -> list[dict]:
    """Return classified events with event types and confidence scores.

    Each article is independently classified and scored against all
    geo-event types.
    """
    if live:
        articles = intel_feed.fetch()
        _store_articles(articles)
    else:
        def _q(s: Session) -> list[dict]:
            stmt = select(GeoIntelArticle).order_by(GeoIntelArticle.fetched_at.desc()).limit(100)
            if category:
                stmt = stmt.where(GeoIntelArticle.category == category)
            rows = s.execute(stmt).scalars().all()
            return [{"title": r.title, "url": r.url, "source": r.source,
                     "time": r.published_at, "category": r.category} for r in rows]
        articles = _run_query(_q)

    result: list[dict] = []
    for article in articles:
        title = article.get("title", "")
        source = article.get("source", "")
        scored = classify_and_score(title, source)
        if scored:
            result.append({
                "title": title,
                "source": source,
                "event_types": [
                    {"type": et.value, "confidence": conf}
                    for et, conf in scored
                ],
            })
    return result
