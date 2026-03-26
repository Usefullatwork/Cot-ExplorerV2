#!/usr/bin/env python3
"""
fetch_fundamentals.py - Fundamental macro data fetcher and scorer.

Fetches economic indicators from FRED API and scores them +/-2 per indicator
for USD bullish/bearish bias. Builds EdgeFinder-style category scores.

Categories:
  - Economic Growth: GDP QoQ, Retail Sales MoM, UoM Consumer Confidence
  - Inflation:       CPI YoY, PPI YoY, PCE YoY, Fed Funds Rate
  - Jobs Market:     NFP, Unemployment Rate, Initial Claims, ADP, JOLTS

PMI is sourced from ForexFactory calendar data (ISM series are not freely
available on FRED).

Weighting for high-probability setups:
  - Within category: per indicator weight (NFP/Claims/CPI/PCE heaviest)
  - Between categories: inflation 0.40 * jobs 0.35 * growth 0.25 (for FX/metals)
  - Consensus multiplier: x1.4 when inflation+jobs agree, x0.7 when opposed

Output: data/prices/fundamentals_latest.json
"""

import json
import logging
import os
import time
import urllib.request
from datetime import datetime, timezone

from src.analysis.fundamental_scoring import (
    compute_indicator,
    consensus_multiplier,
    weighted_cat_avg,
)
from src.config.fundamentals import (
    CAT_WEIGHTS_EQ,
    CAT_WEIGHTS_FX,
    CATEGORIES,
    EQ_INSTRUMENTS,
    FRED_SERIES,
    INSTRUMENT_USD_DIR,
)
from src.trading.core.pmi_calendar import try_calendar_pmi

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(_DIR, "..", "..", ".."))
DATA_DIR = os.path.join(PROJECT_ROOT, "data")
OUT = os.path.join(DATA_DIR, "prices", "fundamentals_latest.json")
os.makedirs(os.path.join(DATA_DIR, "prices"), exist_ok=True)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
FRED_API_KEY = os.environ.get("FRED_API_KEY", "")


def fetch_fred_api(series_id: str, limit: int = 16) -> list[tuple[str, float]]:
    """Fetch observations from FRED API."""
    if not FRED_API_KEY:
        log.warning("FRED API key not set - skipping %s", series_id)
        return []
    url = (
        f"https://api.stlouisfed.org/fred/series/observations"
        f"?series_id={series_id}&api_key={FRED_API_KEY}"
        f"&file_type=json&sort_order=desc&limit={limit}"
    )
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=12) as r:
            d = json.loads(r.read())
        obs = []
        for o in d.get("observations", []):
            if o.get("value") not in (".", "", None):
                try:
                    obs.append((o["date"], float(o["value"])))
                except (ValueError, KeyError):
                    pass
        return list(reversed(obs))
    except Exception as e:
        log.error("FRED %s: %s", series_id, e)
        return []


def main() -> None:
    """Fetch fundamentals, score them, and save output."""
    log.info("=== fetch_fundamentals.py ===")
    log.info("FRED API key: %s", "***" + FRED_API_KEY[-4:] if FRED_API_KEY else "NOT SET")

    indicators = {}

    for key, cfg in FRED_SERIES.items():
        log.info("Fetching %s (%s)...", key, cfg["id"])
        limit = 16 if cfg["type"] == "yoy" else 6
        obs = fetch_fred_api(cfg["id"], limit=limit)
        result = compute_indicator(key, cfg, obs)
        if result:
            indicators[key] = result
            log.info("  -> %s (%s)  score=%+d", result["current"], result["trend"], result["score"])
        else:
            log.warning("  -> ERROR or insufficient data for %s", key)
        time.sleep(0.15)

    cal_pmi = try_calendar_pmi(DATA_DIR)
    for k, pmi in cal_pmi.items():
        indicators[k] = {
            "key": k,
            "label": "ISM Manufacturing PMI" if k == "mPMI" else "ISM Services NMI",
            "current": pmi["actual"],
            "previous": pmi.get("previous"),
            "forecast": pmi.get("forecast"),
            "surprise": pmi.get("surprise", 0),
            "score": pmi["score"],
            "trend": "ukjent",
            "source": "calendar",
        }

    cat_avgs = {}
    category_scores = {}
    for cat, keys in CATEGORIES.items():
        avg = weighted_cat_avg(keys, indicators)
        count = sum(1 for k in keys if k in indicators)
        cat_avgs[cat] = avg
        category_scores[cat] = {
            "score": round(sum(indicators[k]["score"] for k in keys if k in indicators), 2),
            "avg": avg,
            "count": count,
            "bias": "bullish" if avg >= 0.4 else "bearish" if avg <= -0.4 else "neutral",
            "keys": keys,
        }

    multiplier = consensus_multiplier(cat_avgs)

    usd_raw = (
        cat_avgs.get("econ_growth", 0) * CAT_WEIGHTS_FX["econ_growth"]
        + cat_avgs.get("inflation", 0) * CAT_WEIGHTS_FX["inflation"]
        + cat_avgs.get("jobs", 0) * CAT_WEIGHTS_FX["jobs"]
    )
    usd_score = round(usd_raw * multiplier, 3)

    if usd_score > 0.7:
        usd_bias = "strong_bullish"
    elif usd_score > 0.25:
        usd_bias = "bullish"
    elif usd_score < -0.7:
        usd_bias = "strong_bearish"
    elif usd_score < -0.25:
        usd_bias = "bearish"
    else:
        usd_bias = "neutral"

    instrument_scores = {}
    for inst_key, direction in INSTRUMENT_USD_DIR.items():
        cat_w = CAT_WEIGHTS_EQ if inst_key in EQ_INSTRUMENTS else CAT_WEIGHTS_FX
        raw = (
            cat_avgs.get("econ_growth", 0) * cat_w["econ_growth"]
            + cat_avgs.get("inflation", 0) * cat_w["inflation"]
            + cat_avgs.get("jobs", 0) * cat_w["jobs"]
        )
        raw_with_consensus = raw * multiplier * direction
        score_inst = round(max(-2.0, min(2.0, raw_with_consensus)), 2)
        if score_inst > 0.7:
            bias = "strong_bullish"
        elif score_inst > 0.25:
            bias = "bullish"
        elif score_inst < -0.7:
            bias = "strong_bearish"
        elif score_inst < -0.25:
            bias = "bearish"
        else:
            bias = "neutral"
        instrument_scores[inst_key] = {
            "score": score_inst,
            "bias": bias,
            "direction": direction,
        }

    output = {
        "updated": datetime.now(timezone.utc).isoformat(),
        "consensus_multi": multiplier,
        "usd_fundamental": {"score": usd_score, "bias": usd_bias, "n": len(indicators)},
        "category_scores": category_scores,
        "indicators": indicators,
        "instrument_scores": instrument_scores,
    }
    with open(OUT, "w") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    log.info("Saved -> %s", OUT)
    log.info("Consensus multiplier: x%s", multiplier)
    log.info("USD fundamental: %s  (score=%+.3f)", usd_bias.upper(), usd_score)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    main()
