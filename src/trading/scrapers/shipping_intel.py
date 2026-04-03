"""Shipping intelligence scraper — Baltic indices + route disruption scoring.

Fetches Baltic Dry Index family from Stooq (free, no key), shipping news
from Google News RSS, and scores 8 global shipping routes for disruption risk.

Ported from V1 fetch_shipping.py — pure scoring functions extracted from I/O.
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

INDICES: list[dict] = [
    {"id": "bdi", "label": "Baltic Dry Index",  "symbol": "^bdi", "desc": "Tørrbulk totalt"},
    {"id": "bci", "label": "Baltic Capesize",   "symbol": "^bci", "desc": "Kull & jernmalm"},
    {"id": "bpi", "label": "Baltic Panamax",    "symbol": "^bpi", "desc": "Korn & kull"},
    {"id": "bsi", "label": "Baltic Supramax",   "symbol": "^bsi", "desc": "Korn, stål, fosfat"},
]

ROUTES: list[dict] = [
    {"id": "trans_pacific", "name": "Trans-Pacific", "ikon": "📦", "cargo": "Container",
     "from": "Kina/Asia", "to": "USA Vestkyst",
     "impact": "USD, US-import, Fed-inflasjon",
     "keywords": ["trans-pacific", "asia-us", "la port", "long beach", "us west coast"]},
    {"id": "asia_europe", "name": "Asia–Europa (Suez)", "ikon": "🚢", "cargo": "Container/Tanker",
     "from": "Asia", "to": "Europa",
     "impact": "EUR/USD, europeisk inflasjon",
     "keywords": ["suez", "red sea", "houthi", "bab-el-mandeb", "maersk", "asia-europe"]},
    {"id": "hormuz", "name": "Hormuz-stredet", "ikon": "🛢️", "cargo": "Råolje (VLCC)",
     "from": "Midt-Østen", "to": "Asia/Europa",
     "impact": "Brent, WTI, gass",
     "keywords": ["hormuz", "strait of hormuz", "persian gulf", "iran", "crude tanker"]},
    {"id": "black_sea", "name": "Svartehavet (korn)", "ikon": "🌾", "cargo": "Hvete/Mais",
     "from": "Ukraina/Russland", "to": "Global",
     "impact": "Hvete, mais, WEAT ETF",
     "keywords": ["black sea", "ukraine grain", "russia grain", "grain corridor", "odessa"]},
    {"id": "panama", "name": "Panama-kanalen", "ikon": "🌊", "cargo": "Container/Bulk/LNG",
     "from": "Atlanterhavet", "to": "Stillehavet",
     "impact": "Kina-US handel, LNG",
     "keywords": ["panama canal", "panamax", "canal drought", "panama transit"]},
    {"id": "south_america", "name": "Sør-Amerika (korn/soya)", "ikon": "🌱", "cargo": "Soya/Mais",
     "from": "Brasil/Argentina", "to": "Asia/Europa",
     "impact": "Soyabønner, mais",
     "keywords": ["brazil port", "santos", "paranagua", "argentina grain", "south america grain"]},
    {"id": "australia_bulk", "name": "Australia (råvarer)", "ikon": "⛏️", "cargo": "Kull/Jernmalm",
     "from": "Australia", "to": "Kina/Japan",
     "impact": "Kull, jernmalm, AUD/USD",
     "keywords": ["australia coal", "port hedland", "iron ore", "capesize australia"]},
    {"id": "malacca", "name": "Malakka-stredet", "ikon": "⚓", "cargo": "Olje/Container/LNG",
     "from": "Midt-Østen/Europa", "to": "Japan/Korea/Kina",
     "impact": "Olje, LNG, all Asia-import",
     "keywords": ["malacca", "strait of malacca", "singapore shipping", "tanker malacca"]},
]

DISRUPTION_WORDS: list[str] = [
    "disruption", "delay", "congestion", "strike", "block", "clos", "restrict",
    "sanction", "attack", "conflict", "war", "drought", "low water", "divert",
    "reroute", "avoid", "warning", "alert", "risk", "suspend", "halt", "tension",
    "threat", "incident", "explosion", "fire", "collision", "aground",
]


# ── Pure scoring functions ───────────────────────────────────────────────────


@dataclass(frozen=True)
class RouteRisk:
    """Risk assessment for a single shipping route."""

    route_id: str
    name: str
    risk: str  # "HIGH"/"MEDIUM"/"LOW"
    risk_score: int
    article_count: int


def score_route_risks(
    articles: list[dict],
    routes: list[dict] | None = None,
) -> list[RouteRisk]:
    """Score route disruption risk from news articles.

    For each article headline, check which route keywords match,
    then count disruption words to compute a risk score.
    """
    if routes is None:
        routes = ROUTES

    scores: dict[str, int] = {r["id"]: 0 for r in routes}
    counts: dict[str, int] = {r["id"]: 0 for r in routes}

    for art in articles:
        text = art.get("title", "").lower()
        for route in routes:
            if not any(kw in text for kw in route["keywords"]):
                continue
            disrupt = sum(1 for w in DISRUPTION_WORDS if w in text)
            scores[route["id"]] += 1 + disrupt
            counts[route["id"]] += 1

    results = []
    for r in routes:
        s = scores[r["id"]]
        if s >= 5:
            risk = "HIGH"
        elif s >= 2:
            risk = "MEDIUM"
        else:
            risk = "LOW"
        results.append(RouteRisk(r["id"], r["name"], risk, s, counts[r["id"]]))

    results.sort(key=lambda x: -x.risk_score)
    return results


def classify_overall_risk(route_risks: list[RouteRisk]) -> str:
    """Classify overall shipping risk from individual route risks."""
    high_count = sum(1 for r in route_risks if r.risk == "HIGH")
    medium_count = sum(1 for r in route_risks if r.risk == "MEDIUM")

    if high_count >= 2 or (high_count >= 1 and medium_count >= 2):
        return "HIGH"
    if medium_count >= 3 or high_count >= 1:
        return "MEDIUM"
    return "LOW"


def score_index_signal(dev_ma_pct: float) -> str:
    """Score a Baltic index based on MA20 deviation."""
    if dev_ma_pct > 15:
        return "bull"
    if dev_ma_pct < -15:
        return "bear"
    return "neutral"


# ── I/O functions ────────────────────────────────────────────────────────────


def fetch_baltic_index(symbol: str) -> dict | None:
    """Fetch Baltic index daily data from Stooq."""
    from src.trading.scrapers.stooq import fetch_ohlc

    rows = fetch_ohlc(symbol, "30d")
    if not rows or len(rows) < 2:
        return None

    current = rows[-1][2]  # close
    prev = rows[-2][2]
    chg1d = ((current - prev) / prev) * 100 if prev else 0

    # MA20
    closes = [r[2] for r in rows]
    ma20 = sum(closes[-20:]) / min(len(closes), 20) if closes else current
    dev_ma = ((current - ma20) / ma20) * 100 if ma20 else 0

    return {
        "value": round(current, 1),
        "prev": round(prev, 1),
        "chg1d": round(chg1d, 2),
        "ma20": round(ma20, 1),
        "dev_ma": round(dev_ma, 2),
        "signal": score_index_signal(dev_ma),
        "trend": "STIGENDE" if dev_ma > 0 else "FALLENDE",
    }


def _fetch_shipping_news() -> list[dict]:
    """Fetch shipping news from Google News RSS."""
    queries = [
        "shipping+disruption+delay+port",
        "baltic+dry+index+freight",
        "suez+canal+OR+hormuz+strait+shipping",
    ]
    articles: list[dict] = []
    for query in queries:
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
                link = item.findtext("link", "")
                if title:
                    articles.append({"title": title, "published": pub, "url": link})
        except Exception as exc:
            logger.warning("Shipping news fetch failed for '%s': %s", query, exc)
        time.sleep(2)  # rate limit

    return articles[:50]


def fetch_shipping_report() -> dict:
    """Full shipping intelligence report."""
    now = datetime.now(timezone.utc)

    # Fetch Baltic indices
    indices_data = []
    for idx in INDICES:
        data = fetch_baltic_index(idx["symbol"])
        indices_data.append({**idx, "data": data})

    # Fetch news and score routes
    news = _fetch_shipping_news()
    route_risks = score_route_risks(news)
    overall = classify_overall_risk(route_risks)

    # BDI signal
    bdi_data = next((i["data"] for i in indices_data if i["id"] == "bdi"), None)
    bdi_signal = bdi_data["signal"] if bdi_data else "neutral"

    return {
        "generated": now.strftime("%Y-%m-%d %H:%M UTC"),
        "overall_risk": overall,
        "bdi_signal": bdi_signal,
        "indices": indices_data,
        "routes": [
            {"id": r.route_id, "name": r.name, "risk": r.risk,
             "risk_score": r.risk_score, "articles": r.article_count}
            for r in route_risks
        ],
        "news_count": len(news),
    }
