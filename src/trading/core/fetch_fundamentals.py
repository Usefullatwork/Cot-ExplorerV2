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

import urllib.request
import json
import os
import time
from datetime import datetime, timezone

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

FRED_SERIES = {
    "GDP":     {"id": "A191RL1Q225SBEA", "type": "level",   "label": "GDP Growth QoQ (%)"},
    "Retail":  {"id": "RSAFS",           "type": "mom",     "label": "Retail Sales MoM (%)"},
    "ConConf": {"id": "UMCSENT",         "type": "level",   "label": "UoM Consumer Sentiment"},
    "CPI":     {"id": "CPIAUCSL",        "type": "yoy",     "label": "CPI YoY (%)"},
    "PPI":     {"id": "PPIACO",          "type": "yoy",     "label": "PPI YoY (%)"},
    "PCE":     {"id": "PCEPI",           "type": "yoy",     "label": "PCE YoY (%)"},
    "IntRate": {"id": "FEDFUNDS",        "type": "level",   "label": "Fed Funds Rate (%)"},
    "NFP":     {"id": "PAYEMS",          "type": "mom_abs", "label": "NFP Change (k)"},
    "Unemp":   {"id": "UNRATE",          "type": "level",   "label": "Unemployment Rate (%)"},
    "Claims":  {"id": "ICSA",            "type": "level",   "label": "Initial Claims (k)"},
    "ADP":     {"id": "ADPMNUSNERNSA",   "type": "level",   "label": "ADP Change (k)"},
    "JOLTS":   {"id": "JTSJOL",          "type": "level",   "label": "JOLTS Openings (k)"},
}

INDICATOR_WEIGHTS = {
    "GDP": 1.0, "mPMI": 2.0, "sPMI": 2.0, "Retail": 1.5, "ConConf": 1.5,
    "CPI": 2.0, "PPI": 1.0, "PCE": 2.0, "IntRate": 1.5,
    "NFP": 2.0, "Unemp": 1.5, "Claims": 1.5, "ADP": 1.0, "JOLTS": 1.0,
}

CATEGORIES = {
    "econ_growth": ["GDP", "mPMI", "sPMI", "Retail", "ConConf"],
    "inflation":   ["CPI", "PPI", "PCE", "IntRate"],
    "jobs":        ["NFP", "Unemp", "Claims", "ADP", "JOLTS"],
}

CAT_WEIGHTS_FX = {"econ_growth": 0.25, "inflation": 0.40, "jobs": 0.35}
CAT_WEIGHTS_EQ = {"econ_growth": 0.50, "inflation": 0.10, "jobs": 0.40}

INSTRUMENT_USD_DIR = {
    "EURUSD": -1, "GBPUSD": -1, "AUDUSD": -1,
    "USDJPY": +1, "DXY":    +1,
    "Gold":   -1, "Silver": -1,
    "SPX":    +1, "NAS100": +1,
    "Brent":  +1, "WTI":    +1,
}

EQ_INSTRUMENTS = {"SPX", "NAS100", "Brent", "WTI"}


def fetch_fred_api(series_id, limit=16):
    """Fetch observations from FRED API."""
    if not FRED_API_KEY:
        print(f"  FRED API key not set - skipping {series_id}")
        return []
    url = (f"https://api.stlouisfed.org/fred/series/observations"
           f"?series_id={series_id}&api_key={FRED_API_KEY}"
           f"&file_type=json&sort_order=desc&limit={limit}")
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
        print(f"  FRED {series_id} ERROR: {e}")
        return []


def score_indicator(key, current, previous):
    """Score an indicator -2..+2 for USD bullish/bearish bias."""
    if current is None:
        return 0

    if key in ("mPMI", "sPMI"):
        if current > 56:     s = 2
        elif current > 52:   s = 1
        elif current > 50:   s = 0
        elif current > 47:   s = -1
        else:                s = -2
        if previous is not None:
            delta = current - previous
            if delta > 2 and s < 2:      s += 1
            elif delta < -2 and s > -2:  s -= 1
        return max(-2, min(2, s))

    if key in ("CPI", "PPI", "PCE"):
        if current > 4.5:     level_s = 2
        elif current > 2.5:   level_s = 1
        elif current > 1.5:   level_s = 0
        elif current > 0.5:   level_s = -1
        else:                  level_s = -2
        trend_s = 0
        if previous is not None:
            if current > previous + 0.2:     trend_s = 1
            elif current < previous - 0.2:   trend_s = -1
        return max(-2, min(2, level_s + trend_s))

    if key == "IntRate":
        if previous is None:
            return 1 if current >= 3.5 else 0
        delta = round(current - previous, 3)
        if delta > 0.1:      return 2
        elif delta > 0:      return 1
        elif delta == 0:     return 1 if current >= 4.0 else 0
        elif delta > -0.1:   return -1
        else:                return -2

    if key == "NFP":
        if current > 250:     s = 2
        elif current > 150:   s = 1
        elif current > 50:    s = 0
        elif current > 0:     s = -1
        else:                  s = -2
        if previous is not None and previous != 0:
            if current > 0 and previous > 0 and current > previous * 1.5 and s < 2:
                s += 1
            elif current < 0 and previous < 0 and s > -2:
                s -= 1
        return max(-2, min(2, s))

    if key == "ADP":
        val = current / 1000 if abs(current) > 5000 else current
        if val > 250:     return 2
        elif val > 150:   return 1
        elif val > 50:    return 0
        elif val > 0:     return -1
        else:             return -2

    if key == "Unemp":
        if current < 3.5:     s = 2
        elif current < 4.0:   s = 1
        elif current < 4.5:   s = 0
        elif current < 5.0:   s = -1
        else:                  s = -2
        if previous is not None:
            if current < previous:     s = min(2, s + 1)
            elif current > previous:   s = max(-2, s - 1)
        return s

    if key == "Claims":
        k = current / 1000
        if k < 200:       s = 2
        elif k < 225:     s = 1
        elif k < 260:     s = 0
        elif k < 300:     s = -1
        else:              s = -2
        if previous is not None:
            pk = previous / 1000
            if k < pk:     s = min(2, s + 1)
            elif k > pk:   s = max(-2, s - 1)
        return s

    if key == "JOLTS":
        if current > 9000:     return 2
        elif current > 7500:   return 1
        elif current > 6000:   return 0
        elif current > 4500:   return -1
        else:                   return -2

    if key == "GDP":
        if current > 3.0:     return 2
        elif current > 1.5:   return 1
        elif current > 0:     return 0
        elif current > -1:    return -1
        else:                  return -2

    if key == "Retail":
        if current > 1.0:      return 2
        elif current > 0.3:    return 1
        elif current > -0.3:   return 0
        elif current > -0.8:   return -1
        else:                   return -2

    if key == "ConConf":
        if current > 90:     s = 2
        elif current > 75:   s = 1
        elif current > 65:   s = 0
        elif current > 55:   s = -1
        else:                 s = -2
        if previous is not None:
            if current > previous:     s = min(2, s + 1)
            elif current < previous:   s = max(-2, s - 1)
        return max(-2, min(2, s))

    return 0


def compute_indicator(key, cfg, obs):
    """Compute current/previous values and score for an indicator."""
    if not obs:
        return None
    t = cfg["type"]
    date = obs[-1][0]
    raw_cur = obs[-1][1]
    raw_prev = obs[-2][1] if len(obs) >= 2 else None

    if t == "level":
        current = round(raw_cur, 3)
        previous = round(raw_prev, 3) if raw_prev is not None else None
    elif t == "yoy":
        if len(obs) < 13:
            return None
        current = round((obs[-1][1] / obs[-13][1] - 1) * 100, 2)
        previous = round((obs[-2][1] / obs[-14][1] - 1) * 100, 2) if len(obs) >= 14 else None
    elif t == "mom":
        if len(obs) < 2:
            return None
        current = round((obs[-1][1] / obs[-2][1] - 1) * 100, 2)
        previous = round((obs[-2][1] / obs[-3][1] - 1) * 100, 2) if len(obs) >= 3 else None
    elif t == "mom_abs":
        if len(obs) < 2:
            return None
        current = round(obs[-1][1] - obs[-2][1], 1)
        previous = round(obs[-2][1] - obs[-3][1], 1) if len(obs) >= 3 else None
    else:
        current, previous = raw_cur, raw_prev

    score = score_indicator(key, current, previous)
    trend = ("opp" if current > previous else "ned" if current < previous else "flat") \
            if previous is not None else "ukjent"

    display_cur = round(current / 1000, 1) if key == "Claims" else current
    display_prev = round(previous / 1000, 1) if (key == "Claims" and previous is not None) else previous

    if key == "ADP" and abs(current) > 5000:
        display_cur = round(current / 1000, 1)
        display_prev = round(previous / 1000, 1) if previous is not None else None

    return {
        "key": key, "label": cfg["label"],
        "current": display_cur, "previous": display_prev,
        "date": date, "score": score, "trend": trend,
    }


def try_calendar_pmi(data_dir):
    """Try to load PMI data from ForexFactory calendar."""
    cal_path = os.path.join(data_dir, "prices", "calendar_latest.json")
    if not os.path.exists(cal_path):
        return {}
    try:
        with open(cal_path) as f:
            cal = json.load(f)
    except Exception:
        return {}

    pmi_map = {}
    for ev in cal.get("events", []):
        if ev.get("country") != "USD":
            continue
        title = ev.get("title", "").lower()
        actual = ev.get("actual", "")
        if not actual:
            continue
        try:
            act_val = float(str(actual).replace("%", "").strip())
        except (ValueError, AttributeError):
            continue
        try:
            fore_val = float(str(ev.get("forecast", "")).replace("%", "").strip()) \
                       if ev.get("forecast") else None
        except (ValueError, AttributeError):
            fore_val = None
        try:
            prev_val = float(str(ev.get("previous", "")).replace("%", "").strip()) \
                       if ev.get("previous") else None
        except (ValueError, AttributeError):
            prev_val = None

        base_score = score_indicator("mPMI", act_val, prev_val)
        if fore_val is not None:
            diff = act_val - fore_val
            surprise = 2 if diff > 1 else 1 if diff > 0 else -2 if diff < -1 else -1 if diff < 0 else 0
        else:
            surprise = 0
        final_score = max(-2, min(2, base_score + surprise))

        entry = {"actual": act_val, "forecast": fore_val, "previous": prev_val,
                 "surprise": surprise, "score": final_score}
        if "ism manufacturing" in title or ("manufacturing pmi" in title and "flash" not in title):
            pmi_map["mPMI"] = entry
        elif ("ism services" in title or ("services pmi" in title and "flash" not in title)
              or "non-manufacturing" in title):
            pmi_map["sPMI"] = entry

    return pmi_map


def weighted_cat_avg(cat_keys, indicators):
    """Weighted average of indicator scores within a category."""
    total_score = 0.0
    total_w = 0.0
    for k in cat_keys:
        if k in indicators:
            w = INDICATOR_WEIGHTS.get(k, 1.0)
            total_score += indicators[k]["score"] * w
            total_w += w
    return round(total_score / total_w, 3) if total_w > 0 else 0.0


def consensus_multiplier(cat_scores):
    """Calculate multiplier based on category agreement/disagreement."""
    THRESHOLD = 0.35
    infl_dir = 1 if cat_scores.get("inflation", 0) > THRESHOLD else \
              -1 if cat_scores.get("inflation", 0) < -THRESHOLD else 0
    jobs_dir = 1 if cat_scores.get("jobs", 0) > THRESHOLD else \
              -1 if cat_scores.get("jobs", 0) < -THRESHOLD else 0
    growth_dir = 1 if cat_scores.get("econ_growth", 0) > THRESHOLD else \
                -1 if cat_scores.get("econ_growth", 0) < -THRESHOLD else 0

    dirs = [d for d in [infl_dir, jobs_dir, growth_dir] if d != 0]

    if len(dirs) >= 2 and all(d == dirs[0] for d in dirs):
        return 1.5
    elif len(dirs) == 2 and dirs[0] != dirs[1]:
        return 0.65
    elif len(dirs) == 1:
        return 1.0
    else:
        return 0.5


def main():
    """Fetch fundamentals, score them, and save output."""
    print("=== fetch_fundamentals.py ===")
    print(f"FRED API key: {'***' + FRED_API_KEY[-4:] if FRED_API_KEY else 'NOT SET'}")

    indicators = {}

    for key, cfg in FRED_SERIES.items():
        print(f"  Fetching {key} ({cfg['id']})...")
        limit = 16 if cfg["type"] == "yoy" else 6
        obs = fetch_fred_api(cfg["id"], limit=limit)
        result = compute_indicator(key, cfg, obs)
        if result:
            indicators[key] = result
            print(f"    -> {result['current']} ({result['trend']:5s})  score={result['score']:+d}")
        else:
            print(f"    -> ERROR or insufficient data")
        time.sleep(0.15)

    cal_pmi = try_calendar_pmi(DATA_DIR)
    for k, pmi in cal_pmi.items():
        indicators[k] = {
            "key": k,
            "label": "ISM Manufacturing PMI" if k == "mPMI" else "ISM Services NMI",
            "current": pmi["actual"], "previous": pmi.get("previous"),
            "forecast": pmi.get("forecast"), "surprise": pmi.get("surprise", 0),
            "score": pmi["score"], "trend": "ukjent", "source": "calendar",
        }

    cat_avgs = {}
    category_scores = {}
    for cat, keys in CATEGORIES.items():
        avg = weighted_cat_avg(keys, indicators)
        count = sum(1 for k in keys if k in indicators)
        cat_avgs[cat] = avg
        category_scores[cat] = {
            "score": round(sum(indicators[k]["score"] for k in keys if k in indicators), 2),
            "avg": avg, "count": count,
            "bias": "bullish" if avg >= 0.4 else "bearish" if avg <= -0.4 else "neutral",
            "keys": keys,
        }

    multiplier = consensus_multiplier(cat_avgs)

    usd_raw = (cat_avgs.get("econ_growth", 0) * CAT_WEIGHTS_FX["econ_growth"] +
               cat_avgs.get("inflation", 0) * CAT_WEIGHTS_FX["inflation"] +
               cat_avgs.get("jobs", 0) * CAT_WEIGHTS_FX["jobs"])
    usd_score = round(usd_raw * multiplier, 3)

    if usd_score > 0.7:       usd_bias = "strong_bullish"
    elif usd_score > 0.25:    usd_bias = "bullish"
    elif usd_score < -0.7:    usd_bias = "strong_bearish"
    elif usd_score < -0.25:   usd_bias = "bearish"
    else:                      usd_bias = "neutral"

    instrument_scores = {}
    for inst_key, direction in INSTRUMENT_USD_DIR.items():
        cat_w = CAT_WEIGHTS_EQ if inst_key in EQ_INSTRUMENTS else CAT_WEIGHTS_FX
        raw = (cat_avgs.get("econ_growth", 0) * cat_w["econ_growth"] +
               cat_avgs.get("inflation", 0) * cat_w["inflation"] +
               cat_avgs.get("jobs", 0) * cat_w["jobs"])
        raw_with_consensus = raw * multiplier * direction
        score_inst = round(max(-2.0, min(2.0, raw_with_consensus)), 2)
        if score_inst > 0.7:       bias = "strong_bullish"
        elif score_inst > 0.25:    bias = "bullish"
        elif score_inst < -0.7:    bias = "strong_bearish"
        elif score_inst < -0.25:   bias = "bearish"
        else:                       bias = "neutral"
        instrument_scores[inst_key] = {
            "score": score_inst, "bias": bias, "direction": direction,
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

    print(f"\nSaved -> {OUT}")
    print(f"Consensus multiplier: x{multiplier}")
    print(f"USD fundamental: {usd_bias.upper()}  (score={usd_score:+.3f})")


if __name__ == "__main__":
    main()
