"""Oil & gas intelligence scraper — energy prices + segment risk scoring.

Fetches 5 energy instrument prices from Stooq, COT positioning from
CFTC data, and energy-sector news for 8-segment risk scoring.

Ported from V1 fetch_oilgas.py — pure scoring functions extracted from I/O.
"""

from __future__ import annotations

import logging
import time
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# ── Constants ────────────────────────────────────────────────────────────────

PRICE_INDICES: list[dict] = [
    {"id": "brent",   "label": "Brent Crude",    "symbol": "co.f",  "unit": "USD/fat"},
    {"id": "wti",     "label": "WTI Crude",       "symbol": "cl.f",  "unit": "USD/fat"},
    {"id": "natgas",  "label": "Natural Gas",     "symbol": "ng.f",  "unit": "USD/MMBtu"},
    {"id": "rbob",    "label": "Gasoline (RBOB)", "symbol": "rb.f",  "unit": "USD/gal"},
    {"id": "heatoil", "label": "Heating Oil",     "symbol": "ho.f",  "unit": "USD/gal"},
]

COT_MAP: dict[str, list[str]] = {
    "wti":    ["Crude Oil, Light Sweet", "Wti Crude Oil 1St Line", "Wti Financial Crude Oil"],
    "brent":  ["Brent Last Day"],
    "natgas": ["Natural Gas Index: Ep San Juan"],
    "rbob":   ["Gasoline Rbob"],
}

SEGMENTS: list[dict] = [
    {"id": "opec", "name": "OPEC+ Produksjon", "ikon": "🛢️",
     "impact": "Brent, WTI, energiaksjer",
     "keywords": ["opec", "opec+", "saudi", "aramco", "production cut", "output cut", "quota"]},
    {"id": "us_supply", "name": "USA Skifer & Lager", "ikon": "🇺🇸",
     "impact": "WTI, XLE, rig count",
     "keywords": ["eia", "crude inventory", "us crude", "shale", "permian", "rig count", "spr"]},
    {"id": "russia", "name": "Russland & Sanksjoner", "ikon": "⚠️",
     "impact": "Brent premium, europeisk energi",
     "keywords": ["russia oil", "russia gas", "urals", "russian crude", "nord stream", "gazprom"]},
    {"id": "mideast", "name": "Midt-Østen Konflikt", "ikon": "💣",
     "impact": "Brent geopolitisk risiko",
     "keywords": ["iran", "iraq", "israel", "hamas", "hezbollah", "middle east oil", "attack oil"]},
    {"id": "lng", "name": "LNG & Naturgass", "ikon": "🔵",
     "impact": "Henry Hub, TTF Europa",
     "keywords": ["lng", "liquefied natural gas", "henry hub", "ttf", "gas storage", "lng terminal"]},
    {"id": "refinery", "name": "Raffinering & Produkter", "ikon": "🏭",
     "impact": "Crack spread, RBOB, diesel",
     "keywords": ["refinery", "crack spread", "gasoline", "diesel", "refinery outage", "fuel demand"]},
    {"id": "demand", "name": "Global Etterspørsel", "ikon": "📊",
     "impact": "Alle energipriser",
     "keywords": ["oil demand", "iea forecast", "opec forecast", "china demand", "demand outlook"]},
    {"id": "renewable", "name": "Energitransisjon", "ikon": "🌱",
     "impact": "Langsiktig oljeetterspørsel",
     "keywords": ["energy transition", "renewable", "ev demand oil", "peak oil demand"]},
]

NEWS_QUERIES: list[dict] = [
    {"id": "opec",      "query": "OPEC production cut Saudi Arabia crude oil supply"},
    {"id": "prices",    "query": "crude oil price WTI Brent forecast"},
    {"id": "natgas",    "query": "natural gas LNG price Henry Hub TTF"},
    {"id": "geopolit",  "query": "oil supply disruption Middle East Iran Russia sanctions"},
    {"id": "inventory", "query": "EIA crude inventory US oil production shale rig count"},
]

DISRUPTION_WORDS: list[str] = [
    "disruption", "cut", "sanction", "attack", "conflict", "war", "halt",
    "suspend", "shortage", "crisis", "threat", "tension", "surge", "spike",
    "fire", "explosion", "outage", "embargo", "restrict",
]


# ── Pure scoring functions ───────────────────────────────────────────────────


@dataclass(frozen=True)
class SegmentRisk:
    """Risk assessment for a single energy market segment."""

    segment_id: str
    name: str
    risk: str  # "HIGH"/"MEDIUM"/"LOW"
    risk_score: int
    article_count: int


def score_price_signal(dev_ma_pct: float) -> tuple[str, int]:
    """Score price trend based on MA20 deviation.

    Returns (signal_str, numeric_score).
    """
    if dev_ma_pct > 15:
        return "bull", 2
    if dev_ma_pct > 5:
        return "bull-mild", 1
    if dev_ma_pct < -15:
        return "bear", -2
    if dev_ma_pct < -5:
        return "bear-mild", -1
    return "neutral", 0


def score_cot(net_pct: float) -> int:
    """Score COT positioning: -2 to +2."""
    if net_pct > 15:
        return 2
    if net_pct > 5:
        return 1
    if net_pct < -15:
        return -2
    if net_pct < -5:
        return -1
    return 0


def combine_energy_signal(price_score: int, cot_score: int) -> str:
    """Combine price trend + COT into directional signal."""
    total = price_score + cot_score
    if total >= 3:
        return "STERKT BULLISH"
    if total >= 1:
        return "BULLISH"
    if total <= -3:
        return "STERKT BEARISH"
    if total <= -1:
        return "BEARISH"
    return "NØYTRAL"


def score_energy_segments(
    articles: list[dict],
    segments: list[dict] | None = None,
) -> list[SegmentRisk]:
    """Score energy segment risk from news articles."""
    if segments is None:
        segments = SEGMENTS

    scores: dict[str, int] = {s["id"]: 0 for s in segments}
    counts: dict[str, int] = {s["id"]: 0 for s in segments}

    for art in articles:
        text = art.get("title", "").lower()
        for seg in segments:
            if not any(kw in text for kw in seg["keywords"]):
                continue
            disrupt = sum(1 for w in DISRUPTION_WORDS if w in text)
            scores[seg["id"]] += 1 + disrupt
            counts[seg["id"]] += 1

    results = []
    for s in segments:
        sc = scores[s["id"]]
        if sc >= 5:
            risk = "HIGH"
        elif sc >= 2:
            risk = "MEDIUM"
        else:
            risk = "LOW"
        results.append(SegmentRisk(s["id"], s["name"], risk, sc, counts[s["id"]]))

    results.sort(key=lambda x: -x.risk_score)
    return results


def classify_overall_risk(segment_risks: list[SegmentRisk]) -> str:
    """Classify overall energy risk from segment assessments."""
    high = sum(1 for s in segment_risks if s.risk == "HIGH")
    medium = sum(1 for s in segment_risks if s.risk == "MEDIUM")

    if high >= 2 or (high >= 1 and medium >= 2):
        return "HIGH"
    if medium >= 3 or high >= 1:
        return "MEDIUM"
    return "LOW"


# ── I/O functions ────────────────────────────────────────────────────────────


def fetch_energy_prices() -> list[dict]:
    """Fetch energy instrument prices from Stooq."""
    from src.trading.scrapers.stooq import fetch_ohlc

    results = []
    for idx in PRICE_INDICES:
        rows = fetch_ohlc(idx["symbol"], "30d")
        if not rows or len(rows) < 2:
            results.append({**idx, "price": None})
            continue

        current = rows[-1][2]
        prev = rows[-2][2]
        chg1d = ((current - prev) / prev) * 100 if prev else 0

        closes = [r[2] for r in rows]
        ma20 = sum(closes[-20:]) / min(len(closes), 20) if closes else current
        dev_ma = ((current - ma20) / ma20) * 100 if ma20 else 0

        signal, _ = score_price_signal(dev_ma)
        trend = "STIGENDE" if dev_ma > 2 else ("FALLENDE" if dev_ma < -2 else "SIDELENGS")

        results.append({
            **idx,
            "price": {
                "value": round(current, 2),
                "prev": round(prev, 2),
                "chg1d": round(chg1d, 2),
                "ma20": round(ma20, 2),
                "dev_ma": round(dev_ma, 2),
                "signal": signal,
                "trend": trend,
            },
        })
    return results


def _fetch_energy_news() -> list[dict]:
    """Fetch energy news from Google News RSS."""
    articles: list[dict] = []
    for q in NEWS_QUERIES:
        query = q["query"].replace(" ", "+")
        url = f"https://news.google.com/rss/search?q={query}&hl=en-US&gl=US&ceid=US:en"
        req = urllib.request.Request(url, headers={
            "User-Agent": "CotExplorerV2/2.1",
            "Accept": "application/rss+xml",
        })
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                root = ET.fromstring(resp.read())
            for item in root.iter("item"):
                title = item.findtext("title", "")
                pub = item.findtext("pubDate", "")
                if title:
                    articles.append({"title": title, "published": pub, "category": q["id"]})
        except Exception as exc:
            logger.warning("Energy news fetch failed for '%s': %s", q["id"], exc)
        time.sleep(2)  # rate limit

    return articles[:50]


def fetch_oilgas_report(cot_data: list[dict] | None = None) -> dict:
    """Full oil & gas intelligence report."""
    now = datetime.now(timezone.utc)

    instruments = fetch_energy_prices()
    news = _fetch_energy_news()
    segment_risks = score_energy_segments(news)
    overall_risk = classify_overall_risk(segment_risks)

    # Brent-WTI spread
    brent = next((i for i in instruments if i["id"] == "brent"), None)
    wti = next((i for i in instruments if i["id"] == "wti"), None)
    spread = None
    if brent and brent.get("price") and wti and wti.get("price"):
        spread = round(brent["price"]["value"] - wti["price"]["value"], 2)

    # Overall signal from first instrument (Brent)
    overall_signal = "NØYTRAL"
    if brent and brent.get("price"):
        _, price_score = score_price_signal(brent["price"]["dev_ma"])
        overall_signal = combine_energy_signal(price_score, 0)

    return {
        "generated": now.strftime("%Y-%m-%d %H:%M UTC"),
        "overall_risk": overall_risk,
        "overall_signal": overall_signal,
        "brent_wti_spread": spread,
        "instruments": instruments,
        "segments": [
            {"id": s.segment_id, "name": s.name, "risk": s.risk,
             "risk_score": s.risk_score, "articles": s.article_count}
            for s in segment_risks
        ],
        "news_count": len(news),
    }
