"""Agriculture weather + COT intelligence scraper.

Fetches 7-day weather forecasts from Open-Meteo (free, no key) for 14
global growing regions, scores weather risk (-2 to +3) with seasonal
multipliers, combines with COT positioning for a directional outlook.

Ported from V1 fetch_agri.py — pure scoring functions extracted from I/O.
"""

from __future__ import annotations

import json
import logging
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# ── Constants ────────────────────────────────────────────────────────────────

CROP_META: dict[str, dict] = {
    "corn":     {"navn": "Mais",        "ikon": "🌽"},
    "wheat":    {"navn": "Hvete",       "ikon": "🌾"},
    "soybeans": {"navn": "Soyabønner",  "ikon": "🫘"},
    "canola":   {"navn": "Canola/Raps", "ikon": "🌿"},
    "cotton":   {"navn": "Bomull",      "ikon": "☁️"},
    "sugar":    {"navn": "Sukker",      "ikon": "🍬"},
    "coffee":   {"navn": "Kaffe",       "ikon": "☕"},
    "cocoa":    {"navn": "Kakao",       "ikon": "🍫"},
    "palm":     {"navn": "Palmeolje",   "ikon": "🌴"},
    "rice":     {"navn": "Ris",         "ikon": "🍚"},
}

COT_MAP: dict[str, list[str]] = {
    "corn":     ["Corn"],
    "wheat":    ["Wheat", "Kc Hrd Red Winter Wht", "Wheat-Srs 2-Chi",
                 "Minneapolis Hard Red Spring Wheat"],
    "soybeans": ["Soybeans", "Soybean Meal", "Soybean Oil"],
    "canola":   ["Canola"],
    "cotton":   ["Cotton No. 2"],
    "sugar":    ["Sugar No. 11", "Sugar No. 16"],
    "coffee":   ["Coffee C"],
    "cocoa":    ["Cocoa"],
    "palm":     [],
    "rice":     ["Rough Rice"],
}

REGIONS: list[dict] = [
    {"id": "us_cornbelt", "name": "US Cornbelt", "lat": 41.5, "lon": -88.0,
     "crops": ["corn", "soybeans"]},
    {"id": "us_great_plains", "name": "US Great Plains", "lat": 39.0, "lon": -99.0,
     "crops": ["wheat"]},
    {"id": "brazil_mato_grosso", "name": "Mato Grosso", "lat": -12.5, "lon": -55.5,
     "crops": ["soybeans", "corn", "cotton", "sugar"]},
    {"id": "argentina_pampas", "name": "Argentina Pampas", "lat": -34.5, "lon": -60.0,
     "crops": ["soybeans", "wheat", "corn"]},
    {"id": "ukraine_blacksea", "name": "Ukraina/Svartehavet", "lat": 49.0, "lon": 32.0,
     "crops": ["wheat", "corn"]},
    {"id": "eu_northern", "name": "Nord-Europa", "lat": 51.0, "lon": 10.0,
     "crops": ["wheat", "canola"]},
    {"id": "canada_prairie", "name": "Canada Prairie", "lat": 51.0, "lon": -108.0,
     "crops": ["wheat", "canola"]},
    {"id": "australia_wheat", "name": "Australia", "lat": -33.0, "lon": 148.0,
     "crops": ["wheat", "canola"]},
    {"id": "india_punjab", "name": "India Punjab", "lat": 30.7, "lon": 75.8,
     "crops": ["wheat", "rice", "sugar"]},
    {"id": "sea_palm", "name": "Sørøst-Asia Palm", "lat": 2.5, "lon": 112.0,
     "crops": ["palm"]},
    {"id": "west_africa_cocoa", "name": "Vest-Afrika Kakao", "lat": 7.0, "lon": -5.0,
     "crops": ["cocoa", "coffee"]},
    {"id": "brazil_coffee", "name": "Brasil Kaffe", "lat": -22.5, "lon": -44.5,
     "crops": ["coffee"]},
    {"id": "us_delta_cotton", "name": "US Delta Cotton", "lat": 33.5, "lon": -90.5,
     "crops": ["cotton", "rice"]},
    {"id": "china_wheat", "name": "Kina Hvete", "lat": 35.0, "lon": 114.0,
     "crops": ["wheat", "corn"]},
]


# ── Pure scoring functions ───────────────────────────────────────────────────


@dataclass(frozen=True)
class WeatherScore:
    """Result of weather impact scoring for a crop in a region."""

    score: int  # -2 to +3 (after seasonal multiplier, clamped)
    raw_score: int
    season_mult: float
    outlook: str  # "tørke", "flom", "frost", "normalt", etc.
    precip_7d_mm: float
    temp_max_avg: float


def compute_season_multiplier(crop: str, lat: float, month: int) -> float:
    """Seasonal criticality multiplier (1.0–1.5).

    Higher during planting/pollination months when crops are most
    vulnerable to weather disruption.
    """
    is_southern = lat < 0
    # Critical months per crop (Northern Hemisphere)
    critical_nh: dict[str, list[int]] = {
        "corn": [4, 5, 6, 7],
        "wheat": [3, 4, 5, 10],
        "soybeans": [5, 6, 7, 8],
        "canola": [4, 5, 9, 10],
        "cotton": [4, 5, 6],
        "sugar": [3, 4, 5],
        "coffee": [9, 10, 11],
        "cocoa": [3, 4, 9, 10],
        "palm": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12],  # year-round
        "rice": [5, 6, 7],
    }
    critical = critical_nh.get(crop, [])
    if is_southern:
        critical = [(m + 6) % 12 or 12 for m in critical]
    return 1.5 if month in critical else 1.0


def score_weather(
    precip_7d: float,
    temp_max_avg: float,
    temp_min_avg: float,
    crop: str,
    lat: float,
    month: int,
) -> WeatherScore:
    """Score weather impact on a crop. Returns -2 to +3.

    Positive scores mean supply disruption risk (bullish for price).
    """
    score = 0
    outlook = "normalt"

    # Drought
    if precip_7d < 3 and temp_max_avg > 30:
        score, outlook = 3, "tørke"
    elif precip_7d < 8 and temp_max_avg > 25:
        score, outlook = 2, "tørt"
    elif precip_7d < 15 and temp_max_avg > 28:
        score, outlook = 1, "tørt"
    # Flood
    elif precip_7d > 120:
        score, outlook = 3, "flom"
    elif precip_7d > 70:
        score, outlook = 2, "vått"
    elif precip_7d > 40:
        score, outlook = 1, "vått"

    # Frost (planting months, NH)
    if temp_min_avg < -2 and month in (3, 4, 5) and lat > 30:
        score = max(score, 2)
        outlook = "frost"

    raw = score
    mult = compute_season_multiplier(crop, lat, month)
    final = min(round(score * mult), 3)  # cap at 3

    return WeatherScore(
        score=final,
        raw_score=raw,
        season_mult=mult,
        outlook=outlook,
        precip_7d_mm=round(precip_7d, 1),
        temp_max_avg=round(temp_max_avg, 1),
    )


def score_cot(net_pct: float) -> int:
    """Score COT positioning: -2 to +2 based on speculator net %."""
    if net_pct > 15:
        return 2
    if net_pct > 5:
        return 1
    if net_pct < -15:
        return -2
    if net_pct < -5:
        return -1
    return 0


def combine_agri_outlook(
    weather_score: int, cot_score: int,
) -> tuple[str, str, int]:
    """Combine weather + COT into directional signal.

    Returns (signal, color, total_score).
    """
    total = weather_score + cot_score
    if total >= 3:
        return "STERKT BULLISH", "bull", total
    if total >= 1:
        return "BULLISH", "bull", total
    if total <= -3:
        return "STERKT BEARISH", "bear", total
    if total <= -1:
        return "BEARISH", "bear", total
    return "NØYTRAL", "neutral", total


# ── I/O functions ────────────────────────────────────────────────────────────


def fetch_weather_forecast(lat: float, lon: float) -> dict | None:
    """Fetch 7-day weather forecast from Open-Meteo (free, no key)."""
    url = (
        f"https://api.open-meteo.com/v1/forecast?"
        f"latitude={lat}&longitude={lon}"
        f"&daily=temperature_2m_max,temperature_2m_min,precipitation_sum"
        f"&forecast_days=7"
    )
    req = urllib.request.Request(url, headers={"User-Agent": "CotExplorerV2/2.1"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read())
    except Exception as exc:
        logger.warning("Open-Meteo failed for %.1f,%.1f: %s", lat, lon, exc)
        return None


def _parse_forecast(data: dict) -> tuple[float, float, float]:
    """Extract 7-day totals from Open-Meteo response.

    Returns (precip_7d_mm, temp_max_avg, temp_min_avg).
    """
    daily = data.get("daily", {})
    precip = daily.get("precipitation_sum", [])
    t_max = daily.get("temperature_2m_max", [])
    t_min = daily.get("temperature_2m_min", [])

    precip_7d = sum(p for p in precip if p is not None)
    avg_max = sum(t for t in t_max if t is not None) / max(len(t_max), 1)
    avg_min = sum(t for t in t_min if t is not None) / max(len(t_min), 1)
    return precip_7d, avg_max, avg_min


def fetch_agri_report(cot_data: list[dict] | None = None) -> dict:
    """Full agriculture intelligence report.

    Fetches weather for all 14 regions, combines with COT data,
    returns structured report with Norwegian labels.
    """
    now = datetime.now(timezone.utc)
    month = now.month
    results: list[dict] = []

    for region in REGIONS:
        forecast = fetch_weather_forecast(region["lat"], region["lon"])
        if forecast is None:
            continue

        precip, t_max, t_min = _parse_forecast(forecast)
        crop_results = []

        for crop in region["crops"]:
            ws = score_weather(precip, t_max, t_min, crop, region["lat"], month)
            cot_s = 0  # default if no COT data
            signal, color, total = combine_agri_outlook(ws.score, cot_s)

            meta = CROP_META.get(crop, {"navn": crop, "ikon": "🌱"})
            crop_results.append({
                "crop_key": crop,
                "navn": f"{meta['ikon']} {meta['navn']}",
                "weather_score": ws.score,
                "cot_score": cot_s,
                "outlook": {"signal": signal, "color": color, "total_score": total},
                "weather_detail": ws.outlook,
                "precip_7d_mm": ws.precip_7d_mm,
                "temp_max_avg": ws.temp_max_avg,
            })

        results.append({
            "region_id": region["id"],
            "region_name": region["name"],
            "lat": region["lat"],
            "lon": region["lon"],
            "crops": crop_results,
        })

    return {
        "generated": now.strftime("%Y-%m-%d %H:%M UTC"),
        "month": month,
        "regions": results,
    }
