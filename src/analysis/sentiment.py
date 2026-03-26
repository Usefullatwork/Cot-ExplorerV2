"""Sentiment and macro indicator fetchers.

Extracted from v1 fetch_all.py lines 529-682.
Note: these functions DO make HTTP calls — they are data fetchers, not pure analysis.
"""

from __future__ import annotations

import json
import logging
import re
import urllib.parse
import urllib.request
from typing import Optional

from src.core.models import FearGreed, NewsSentiment

log = logging.getLogger(__name__)


def fetch_fear_greed() -> FearGreed | None:
    """Fetch the CNN Fear & Greed index."""
    try:
        url = "https://production.dataviz.cnn.io/index/fearandgreed/graphdata"
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/120.0",
                "Accept": "application/json, text/plain, */*",
                "Referer": "https://edition.cnn.com/markets/fear-and-greed",
                "Origin": "https://edition.cnn.com",
            },
        )
        with urllib.request.urlopen(req, timeout=8) as r:
            d = json.loads(r.read())
        return FearGreed(
            score=round(d["fear_and_greed"]["score"], 1),
            rating=d["fear_and_greed"]["rating"],
        )
    except Exception as e:
        log.error(f"Fear&Greed FEIL: {e}")
        return None


def fetch_news_sentiment() -> NewsSentiment | None:
    """Fetch RSS news, score risk-on/risk-off keywords.

    Returns sentiment with score (-1..1), label, top_headlines and key_drivers.
    """
    RISK_ON = [
        "peace",
        "ceasefire",
        "deal",
        "agreement",
        "truce",
        "treaty",
        "stimulus",
        "rate cut",
        "rate cuts",
        "recovery",
        "trade deal",
        "tariff pause",
        "tariff reduction",
        "tariff removed",
        "de-escalation",
        "deescalation",
        "accord",
        "optimism",
        "soft landing",
        "talks progress",
        "diplomatic",
        "breakthrough",
        "resolved",
        "lifted sanctions",
    ]
    RISK_OFF = [
        "war",
        "attack",
        "invasion",
        "escalation",
        "sanctions",
        "default",
        "crisis",
        "collapse",
        "recession",
        "military strike",
        "nuclear",
        "terror",
        "conflict",
        "threatens",
        "tariff hike",
        "new tariffs",
        "imposed tariffs",
        "sell-off",
        "selloff",
        "bank run",
        "debt crisis",
        "banking crisis",
        "crash",
        "downgrade",
        "emergency",
        "missile",
    ]
    feeds = [
        "https://news.google.com/rss/search?q=economy+markets+geopolitics&hl=en-US&gl=US&ceid=US:en",
        "https://feeds.bbci.co.uk/news/world/rss.xml",
    ]
    headlines: list[str] = []
    for url in feeds:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=7) as r:
                txt = r.read().decode("utf-8", errors="replace")
            titles = re.findall(r"<title><!\[CDATA\[(.*?)\]\]></title>", txt)
            if not titles:
                titles = re.findall(r"<title>(.*?)</title>", txt)
            headlines.extend(titles[1:16])
        except Exception as e:
            log.error(f"Nyheter FEIL ({url[:45]}): {e}")
    if not headlines:
        return None

    ro_count = roff_count = 0
    drivers: list[dict] = []
    for h in headlines:
        hl = h.lower()
        ro = sum(1 for w in RISK_ON if w in hl)
        roff = sum(1 for w in RISK_OFF if w in hl)
        if ro > roff:
            ro_count += 1
            drivers.append({"headline": h[:90], "type": "risk_on"})
        elif roff > ro:
            roff_count += 1
            drivers.append({"headline": h[:90], "type": "risk_off"})
    total = ro_count + roff_count
    if total == 0:
        label, net = "neutral", 0.0
    else:
        net = round((ro_count - roff_count) / total, 2)
        label = "risk_on" if net >= 0.3 else "risk_off" if net <= -0.3 else "neutral"

    return NewsSentiment(
        score=net,
        label=label,
        top_headlines=headlines[:5],
        key_drivers=drivers[:6],
        ro_count=ro_count,
        roff_count=roff_count,
        headlines_n=len(headlines),
    )


# ---------------------------------------------------------------------------
# Macro indicator symbols — mirrors v1 MACRO_SYMBOLS
# ---------------------------------------------------------------------------
MACRO_SYMBOLS: dict[str, str] = {
    "HYG": "HYG",  # iShares High Yield Corp Bond ETF
    "TIP": "TIP",  # iShares TIPS Bond ETF
    "TNX": "^TNX",  # 10-year Treasury yield
    "IRX": "^IRX",  # 3-month Treasury bill
    "Copper": "HG=F",  # Copper futures
    "EEM": "EEM",  # iShares MSCI Emerging Markets ETF
}


def _fetch_fred(series_id: str) -> float | None:
    """Fetch latest daily value from FRED (Federal Reserve). No API key needed."""
    url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            lines = r.read().decode().strip().split("\n")
        for line in reversed(lines[1:]):
            parts = line.strip().split(",")
            if len(parts) == 2 and parts[1] not in (".", ""):
                return float(parts[1])
        return None
    except Exception as e:
        log.error(f"FRED {series_id} FEIL: {e}")
        return None


def _fetch_yahoo(symbol: str, interval: str = "1d", range_: str = "30d") -> list[tuple[float, float, float]]:
    """Fetch OHLC from Yahoo Finance. Returns [(h,l,c), ...] oldest-first."""
    url = (
        f"https://query1.finance.yahoo.com/v8/finance/chart/"
        f"{urllib.parse.quote(symbol)}?interval={interval}&range={range_}"
    )
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            d = json.loads(r.read())
        res = d["chart"]["result"][0]
        q = res["indicators"]["quote"][0]
        rows = [
            (h, lo, c) for h, lo, c in zip(q.get("high", []), q.get("low", []), q.get("close", [])) if h and lo and c
        ]
        return rows
    except Exception as e:
        log.error(f"FEIL {symbol} ({interval}): {e}")
        return []


def fetch_macro_indicators() -> dict[str, Optional[dict]]:
    """Fetch supplementary macro indicators.

    Returns dict key -> {"price": float, "chg1d": float, "chg5d": float} or None.
    Uses FRED for rates (official Fed data), Yahoo for ETFs and commodities.
    """
    out: dict[str, Optional[dict]] = {}

    # Interest rates from FRED (DGS10 = 10Y, DTB3 = 3-month T-bill)
    for key, series in [("TNX", "DGS10"), ("IRX", "DTB3")]:
        val = _fetch_fred(series)
        if val:
            out[key] = {"price": round(val, 3), "chg1d": 0, "chg5d": 0}
        else:
            # Fallback to Yahoo
            daily = _fetch_yahoo(MACRO_SYMBOLS[key], "1d", "30d")
            if daily and len(daily) >= 2:
                curr = daily[-1][2]
                c5 = daily[-6][2] if len(daily) >= 6 else curr
                out[key] = {
                    "price": round(curr, 3),
                    "chg1d": 0,
                    "chg5d": round((curr / c5 - 1) * 100, 2),
                }
            else:
                out[key] = None

    # ETFs and commodities via Yahoo
    for key in ["HYG", "TIP", "Copper", "EEM"]:
        sym = MACRO_SYMBOLS[key]
        daily = _fetch_yahoo(sym, "1d", "30d")
        if not daily or len(daily) < 6:
            out[key] = None
            continue
        curr = daily[-1][2]
        c5 = daily[-6][2] if len(daily) >= 6 else curr
        c1 = daily[-2][2] if len(daily) >= 2 else curr
        out[key] = {
            "price": round(curr, 4 if curr < 10 else 2),
            "chg1d": round((curr / c1 - 1) * 100, 2),
            "chg5d": round((curr / c5 - 1) * 100, 2),
        }
    return out


def detect_conflict(
    vix: float,
    dxy_5d: float,
    fg: Optional[dict],
    cot_usd: Optional[float],
    hy_stress: bool = False,
    yield_curve: Optional[float] = None,
    news_sent: Optional[dict] = None,
) -> list[str]:
    """Detect macro-level conflicts and divergences.

    Returns a list of human-readable conflict descriptions (Norwegian).
    """
    conflicts: list[str] = []
    if vix > 25 and dxy_5d < 0:
        conflicts.append("VIX>25 men DXY faller – risk-off uten USD-etterspørsel")
    if fg and fg["score"] < 30 and dxy_5d < 0:
        conflicts.append("Ekstrem frykt men USD svekkes – unormalt")
    if fg and fg["score"] > 70 and vix > 22:
        conflicts.append("Grådighet men VIX forhøyet – divergens")
    if cot_usd and cot_usd > 0 and dxy_5d < -1:
        conflicts.append("COT long USD men pris faller – divergens")
    if hy_stress and vix < 20:
        conflicts.append("HY-spreader øker men VIX lav – skjult kredittrisiko")
    if yield_curve is not None and yield_curve < -0.3:
        conflicts.append(f"Rentekurve invertert ({yield_curve:+.2f}%) – resesjonsrisiko")
    # News sentiment vs macro
    if news_sent and news_sent.get("label") == "risk_on" and vix > 25:
        conflicts.append("Nyheter risk-on men VIX forhøyet – sentimentskifte pågår")
    if news_sent and news_sent.get("label") == "risk_off" and fg and fg["score"] > 60:
        conflicts.append("Nyheter risk-off men Fear&Greed viser grådighet – divergens")
    if news_sent and news_sent.get("label") == "risk_on" and fg and fg["score"] < 25:
        conflicts.append("Nyheter risk-on men ekstrem frykt i markedet – potensiell bunnstemning")
    return conflicts
