#!/usr/bin/env python3
"""
fetch_all.py - Full analysis pipeline.

Orchestrates all data fetching and analysis:
  1. Loads COT data, calendar, fundamentals from disk
  2. Fetches live prices from multiple sources (Twelvedata -> Stooq -> Yahoo)
  3. Runs SMC analysis on multiple timeframes (15m, 1H, 4H)
  4. Builds multi-timeframe level maps with weighted merging
  5. Scores each instrument on 12 criteria
  6. Generates macro overview with VIX regime, dollar smile, conflicts
  7. Saves complete macro.json for dashboard/push_signals

Data source priority: Twelvedata (forex/gold) -> Stooq (daily) -> Yahoo (fallback)
Realtime overlay: Finnhub quotes patch last bar when available.

Output: data/prices/macro_latest.json

Zero external dependencies - stdlib only (except optional smc import).
"""

import logging
import urllib.request
import urllib.parse
import json
import os
import sys
import time
import re
from datetime import datetime, timezone, timedelta

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(_DIR, "..", "..", ".."))
DATA_DIR = os.path.join(PROJECT_ROOT, "data")
OUT = os.path.join(DATA_DIR, "prices", "macro_latest.json")
os.makedirs(os.path.join(DATA_DIR, "prices"), exist_ok=True)

# Import SMC engine
sys.path.insert(0, _DIR)
try:
    from smc import run_smc
    SMC_OK = True
except ImportError:
    SMC_OK = False
    log.warning("SMC not available")

# ---------------------------------------------------------------------------
# Instrument definitions
# ---------------------------------------------------------------------------
INSTRUMENTS = [
    {"key": "EURUSD", "navn": "EUR/USD",  "symbol": "EURUSD=X", "label": "Valuta", "kat": "valuta", "klasse": "A", "session": "London 08:00-12:00 CET"},
    {"key": "USDJPY", "navn": "USD/JPY",  "symbol": "JPY=X",    "label": "Valuta", "kat": "valuta", "klasse": "A", "session": "London 08:00-12:00 CET"},
    {"key": "GBPUSD", "navn": "GBP/USD",  "symbol": "GBPUSD=X", "label": "Valuta", "kat": "valuta", "klasse": "A", "session": "London 08:00-12:00 CET"},
    {"key": "AUDUSD", "navn": "AUD/USD",  "symbol": "AUDUSD=X", "label": "Valuta", "kat": "valuta", "klasse": "A", "session": "London 08:00-12:00 CET"},
    {"key": "Gold",   "navn": "Gull",     "symbol": "GC=F",     "label": "Ravare", "kat": "ravarer", "klasse": "B", "session": "London Fix 10:30 / NY Fix 15:00 CET"},
    {"key": "Silver", "navn": "Solv",     "symbol": "SI=F",     "label": "Ravare", "kat": "ravarer", "klasse": "B", "session": "London Fix 10:30 / NY Fix 15:00 CET"},
    {"key": "Brent",  "navn": "Brent",    "symbol": "BZ=F",     "label": "Ravare", "kat": "ravarer", "klasse": "B", "session": "London Fix 10:30 / NY Fix 15:00 CET"},
    {"key": "WTI",    "navn": "WTI",      "symbol": "CL=F",     "label": "Ravare", "kat": "ravarer", "klasse": "B", "session": "London Fix 10:30 / NY Fix 15:00 CET"},
    {"key": "SPX",    "navn": "S&P 500",  "symbol": "^GSPC",    "label": "Aksjer", "kat": "aksjer",  "klasse": "C", "session": "NY Open 14:30-17:00 CET"},
    {"key": "NAS100", "navn": "Nasdaq",   "symbol": "^NDX",     "label": "Aksjer", "kat": "aksjer",  "klasse": "C", "session": "NY Open 14:30-17:00 CET"},
    {"key": "VIX",    "navn": "VIX",      "symbol": "^VIX",     "label": "Vol",    "kat": "aksjer",  "klasse": "C", "session": "NY Open 14:30-17:00 CET"},
    {"key": "DXY",    "navn": "DXY",      "symbol": "DX-Y.NYB", "label": "Valuta", "kat": "valuta",  "klasse": "A", "session": "London 08:00-12:00 CET"},
]

# API keys from environment
TWELVEDATA_API_KEY = os.environ.get("TWELVEDATA_API_KEY", "")
FINNHUB_API_KEY = os.environ.get("FINNHUB_API_KEY", "")

# ---------------------------------------------------------------------------
# Data source mappings (see src/trading/scrapers/ for individual modules)
# ---------------------------------------------------------------------------
TD_FREE_SYMBOLS = {"EURUSD=X", "JPY=X", "GBPUSD=X", "AUDUSD=X", "GC=F", "HYG", "TIP", "EEM"}

TWELVEDATA_MAP = {
    "EURUSD=X": "EUR/USD", "JPY=X": "USD/JPY", "GBPUSD=X": "GBP/USD",
    "AUDUSD=X": "AUD/USD", "GC=F": "XAU/USD", "HYG": "HYG", "TIP": "TIP", "EEM": "EEM",
}
TD_INTERVAL = {"1d": "1day", "15m": "15min", "60m": "1h"}
TD_SIZE = {"1y": 365, "5d": 500, "60d": 500, "30d": 35}

STOOQ_MAP = {
    "EURUSD=X": "eurusd", "JPY=X": "usdjpy", "GBPUSD=X": "gbpusd", "AUDUSD=X": "audusd",
    "GC=F": "xauusd", "SI=F": "xagusd", "BZ=F": "co.f", "CL=F": "cl.f",
    "^GSPC": "^spx", "^NDX": "^ndx", "^VIX": "^vix", "DX-Y.NYB": "dxy.f",
    "HG=F": "hg.f", "HYG": "hyg.us", "TIP": "tip.us", "EEM": "eem.us",
}
STOOQ_DAYS = {"1y": 400, "30d": 35, "5d": 7}

FINNHUB_QUOTE_MAP = {
    "^GSPC": "^GSPC", "^NDX": "^NDX", "^VIX": "^VIX",
    "SI=F": "SI1!", "BZ=F": "UKOIL", "CL=F": "USOIL", "HG=F": "HG1!",
}

COT_MAP = {
    "EURUSD": "euro fx", "USDJPY": "japanese yen", "GBPUSD": "british pound",
    "Gold": "gold", "Silver": "silver", "Brent": "crude oil, light sweet",
    "WTI": "crude oil, light sweet", "SPX": "s&p 500 consolidated",
    "NAS100": "nasdaq mini", "DXY": "usd index",
}

NEWS_CONFIRMS_MAP = {
    "SPX": ("bull", "bear"), "NAS100": ("bull", "bear"),
    "Gold": ("bear", "bull"), "Silver": ("bear", "bull"),
    "EURUSD": ("bull", "bear"), "GBPUSD": ("bull", "bear"),
    "AUDUSD": ("bull", "bear"), "USDJPY": ("bull", "bear"),
    "DXY": ("bear", "bull"), "Brent": (None, None),
    "WTI": (None, None), "VIX": ("bear", "bull"),
}


# ---------------------------------------------------------------------------
# Data fetchers
# ---------------------------------------------------------------------------
def fetch_yahoo(symbol, interval="1d", range_="1y"):
    """Fetch OHLC from Yahoo Finance. Returns [(h,l,c), ...] or []."""
    url = (f"https://query1.finance.yahoo.com/v8/finance/chart/"
           f"{urllib.parse.quote(symbol)}?interval={interval}&range={range_}")
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            d = json.loads(r.read())
        res = d["chart"]["result"][0]
        q = res["indicators"]["quote"][0]
        return [(h, l, c) for h, l, c in zip(q.get("high", []), q.get("low", []), q.get("close", []))
                if h and l and c]
    except Exception as e:
        log.error("Yahoo %s (%s): %s", symbol, interval, e)
        return []


def fetch_twelvedata(symbol, interval="1d", outputsize=365):
    """Fetch OHLC from Twelvedata. Returns [(h,l,c), ...] oldest->newest."""
    if not TWELVEDATA_API_KEY or symbol not in TD_FREE_SYMBOLS:
        return []
    td_sym = TWELVEDATA_MAP.get(symbol, symbol)
    td_int = TD_INTERVAL.get(interval, interval)
    url = (f"https://api.twelvedata.com/time_series"
           f"?symbol={urllib.parse.quote(td_sym)}&interval={td_int}"
           f"&outputsize={outputsize}&apikey={TWELVEDATA_API_KEY}")
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=12) as r:
            d = json.loads(r.read())
        if d.get("status") == "error":
            log.warning("TD %s: %s", td_sym, d.get("message", "unknown error"))
            return []
        rows = []
        for v in reversed(d.get("values", [])):
            try:
                rows.append((float(v["high"]), float(v["low"]), float(v["close"])))
            except (ValueError, KeyError):
                continue
        time.sleep(8)  # Free tier: max 8 req/min
        return rows
    except Exception as e:
        log.error("TD %s (%s): %s", td_sym, interval, e)
        return []


def fetch_stooq(symbol, range_="1y"):
    """Fetch daily OHLC from Stooq (no API key, near-realtime)."""
    stooq_sym = STOOQ_MAP.get(symbol)
    if not stooq_sym:
        return []
    days = STOOQ_DAYS.get(range_, 400)
    d2 = datetime.now(timezone.utc).strftime("%Y%m%d")
    d1 = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y%m%d")
    url = f"https://stooq.com/q/d/l/?s={stooq_sym}&i=d&d1={d1}&d2={d2}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            text = r.read().decode(errors="replace")
        lines = text.strip().split("\n")
        rows = []
        for line in lines[1:]:
            parts = line.strip().split(",")
            if len(parts) < 5:
                continue
            try:
                h, l, c = float(parts[2]), float(parts[3]), float(parts[4])
                if h and l and c:
                    rows.append((h, l, c))
            except (ValueError, IndexError):
                continue
        return rows
    except Exception as e:
        log.error("Stooq %s: %s", stooq_sym, e)
        return []


def fetch_finnhub_quote(symbol):
    """Fetch realtime quote from Finnhub."""
    if not FINNHUB_API_KEY:
        return None
    fh_sym = FINNHUB_QUOTE_MAP.get(symbol)
    if not fh_sym:
        return None
    url = (f"https://finnhub.io/api/v1/quote"
           f"?symbol={urllib.parse.quote(fh_sym)}&token={FINNHUB_API_KEY}")
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=8) as r:
            d = json.loads(r.read())
        c, h, l = d.get("c", 0), d.get("h", 0), d.get("l", 0)
        if c and h and l:
            return (h, l, c)
        return None
    except Exception as e:
        log.error("Finnhub %s: %s", fh_sym, e)
        return None


def fetch_fred(series_id):
    """Fetch latest daily value from FRED (no API key needed for CSV)."""
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
        log.error("FRED %s: %s", series_id, e)
        return None


def fetch_prices(symbol, interval, range_or_size):
    """Priority: Twelvedata -> Stooq (daily) -> Yahoo. Finnhub overlay on last bar."""
    if TWELVEDATA_API_KEY and symbol in TD_FREE_SYMBOLS:
        rows = fetch_twelvedata(symbol, interval, TD_SIZE.get(range_or_size, 365))
        if rows:
            if interval == "1d":
                qt = fetch_finnhub_quote(symbol)
                if qt:
                    rows[-1] = qt
            return rows
    if interval == "1d":
        rows = fetch_stooq(symbol, range_or_size)
        if rows:
            qt = fetch_finnhub_quote(symbol)
            if qt:
                rows[-1] = qt
            return rows
    return fetch_yahoo(symbol, interval, range_or_size)


# ---------------------------------------------------------------------------
# Technical analysis helpers
# ---------------------------------------------------------------------------
def calc_atr(rows, n=14):
    if len(rows) < n + 1:
        return None
    trs = [max(rows[i][0] - rows[i][1], abs(rows[i][0] - rows[i - 1][2]),
               abs(rows[i][1] - rows[i - 1][2])) for i in range(1, len(rows))]
    return sum(trs[-n:]) / n


def calc_ema(closes, n=9):
    if len(closes) < n + 1:
        return None
    k = 2 / (n + 1)
    ema = sum(closes[:n]) / n
    for c in closes[n:]:
        ema = c * k + ema * (1 - k)
    return ema


def to_4h(rows_1h):
    out = []
    for i in range(0, len(rows_1h) - 3, 4):
        grp = rows_1h[i:i + 4]
        h = max(r[0] for r in grp)
        l = min(r[1] for r in grp)
        c = grp[-1][2]
        out.append((h, l, c))
    return out


def get_pdh_pdl_pdc(daily):
    if len(daily) < 2:
        return None, None, None
    return daily[-2][0], daily[-2][1], daily[-2][2]


def get_pwh_pwl(daily):
    if len(daily) < 10:
        return None, None
    week = daily[-8:-1]
    return max(r[0] for r in week), min(r[1] for r in week)


def get_session_status():
    h = datetime.now(timezone.utc).hour
    m = datetime.now(timezone.utc).minute
    cet = (h * 60 + m + 60) % (24 * 60)
    ch = cet // 60
    sessions = []
    if 7 * 60 <= cet < 12 * 60:
        sessions.append("London")
    if 13 * 60 <= cet < 17 * 60:
        sessions.append("NY Overlap")
    if 8 * 60 <= cet < 12 * 60:
        sessions.append("London Fix")
    if not sessions:
        sessions.append("Off-session")
    return {"active": any(s != "Off-session" for s in sessions),
            "label": " / ".join(sessions), "cet_hour": ch}


def find_intraday_levels(rows_15m, n=3):
    rows = rows_15m[-200:] if len(rows_15m) > 200 else rows_15m
    curr = rows[-1][2]
    res, sup = [], []
    for i in range(n, len(rows) - n):
        if rows[i][0] == max(r[0] for r in rows[i - n:i + n + 1]):
            res.append(rows[i][0])
        if rows[i][1] == min(r[1] for r in rows[i - n:i + n + 1]):
            sup.append(rows[i][1])
    r_filt = sorted(list(dict.fromkeys([round(r, 5) for r in res if r > curr])),
                    key=lambda x: abs(x - curr))[:4]
    s_filt = sorted(list(dict.fromkeys([round(s, 5) for s in sup if s < curr])),
                    key=lambda x: abs(x - curr))[:4]
    return r_filt, s_filt


def find_swing_levels(rows, n=5):
    curr = rows[-1][2]
    res, sup = [], []
    for i in range(n, len(rows) - n):
        if rows[i][0] == max(r[0] for r in rows[i - n:i + n + 1]):
            res.append(rows[i][0])
        if rows[i][1] == min(r[1] for r in rows[i - n:i + n + 1]):
            sup.append(rows[i][1])
    r_filt = sorted(list(dict.fromkeys([round(r, 5) for r in res if r > curr])),
                    key=lambda x: abs(x - curr))[:3]
    s_filt = sorted(list(dict.fromkeys([round(s, 5) for s in sup if s < curr])),
                    key=lambda x: abs(x - curr))[:3]
    return r_filt, s_filt


def is_at_level(curr, level, atr_15m, weight=1):
    tight = 0.30 if weight <= 1 else (0.35 if weight == 2 else 0.45)
    return abs(curr - level) <= atr_15m * tight


def merge_tagged_levels(tagged, curr, atr, max_n=6):
    if not tagged:
        return []
    atr_buf = (atr or 0) * 0.5
    merged = []
    for lvl in sorted(tagged, key=lambda x: abs(x["price"] - curr)):
        absorbed = False
        for m in merged:
            if atr_buf > 0 and abs(lvl["price"] - m["price"]) < atr_buf:
                if lvl["weight"] > m["weight"]:
                    m["price"] = lvl["price"]
                    m["source"] = lvl["source"]
                    m["weight"] = lvl["weight"]
                    for k in ("zone_top", "zone_bottom"):
                        if k in lvl:
                            m[k] = lvl[k]
                        else:
                            m.pop(k, None)
                absorbed = True
                break
        if not absorbed:
            merged.append(dict(lvl))
    return sorted(merged, key=lambda x: abs(x["price"] - curr))[:max_n]


# ---------------------------------------------------------------------------
# Setup generation
# ---------------------------------------------------------------------------
def make_setup_l2l(curr, atr_15m, atr_daily, sup_tagged, res_tagged, direction, klasse, min_rr=1.5):
    """Level-to-level setup with structural stop loss."""
    if not atr_15m or atr_15m <= 0:
        return None
    if not atr_daily or atr_daily <= 0:
        atr_daily = atr_15m * 5

    def structural_sl(entry_level, entry_obj, dir_):
        buf = atr_daily * 0.15
        w = entry_obj.get("weight", 1)
        if dir_ == "long":
            zone_bot = entry_obj.get("zone_bottom")
            if zone_bot and zone_bot < entry_level:
                return round(zone_bot - buf, 5)
            sl_buf = atr_daily * (0.5 if w >= 4 else 0.3)
            return round(entry_level - sl_buf, 5)
        else:
            zone_top = entry_obj.get("zone_top")
            if zone_top and zone_top > entry_level:
                return round(zone_top + buf, 5)
            sl_buf = atr_daily * (0.5 if w >= 4 else 0.3)
            return round(entry_level + sl_buf, 5)

    def best_t1(levels, entry, min_dist):
        cands = sorted(levels, key=lambda x: (-x["weight"], abs(x["price"] - entry)))
        for l in cands:
            p = l["price"]
            ok = (p > entry + min_dist) if direction == "long" else (p < entry - min_dist)
            if ok:
                q = "htf" if l["weight"] >= 3 else ("4h" if l["weight"] >= 2 else "weak")
                return dict(l, t1_quality=q)
        return None

    if direction == "long":
        if not sup_tagged or not res_tagged:
            return None
        entry_obj = sup_tagged[0]
        entry_level = entry_obj["price"]
        entry_w = entry_obj["weight"]
        entry_dist = curr - entry_level
        max_entry_dist = atr_daily * (0.3 if entry_w <= 1 else 0.7 if entry_w == 2 else 1.0)
        if entry_dist < 0 or entry_dist > max_entry_dist:
            return None
        sl = structural_sl(entry_level, entry_obj, "long")
        risk = entry_level - sl
        if risk <= 0:
            return None
        t1_obj = best_t1(res_tagged, entry_level, risk * min_rr)
        if t1_obj is None:
            return None
        t1 = t1_obj["price"]
        res_after = [l for l in res_tagged if l["price"] > t1]
        t2 = res_after[0]["price"] if res_after else round(t1 + risk, 5)
        rr1 = round((t1 - entry_level) / risk, 2)
        rr2 = round((t2 - entry_level) / risk, 2)
        at_level = is_at_level(curr, entry_level, atr_15m, entry_w)
        sl_src = "zone" if entry_obj.get("zone_bottom") else "struktur"
        return {
            "entry": round(entry_level, 5), "sl": sl, "sl_type": sl_src,
            "t1": round(t1, 5), "t2": round(t2, 5),
            "rr_t1": rr1, "rr_t2": rr2, "min_rr": min_rr,
            "risk_atr_d": round(risk / atr_daily, 2),
            "entry_dist_atr": round(entry_dist / atr_daily, 2),
            "entry_weight": entry_w, "t1_source": t1_obj["source"],
            "t1_quality": t1_obj["t1_quality"],
            "status": "aktiv" if at_level else "watchlist",
            "timeframe": "D1/4H",
        }
    else:
        if not res_tagged or not sup_tagged:
            return None
        entry_obj = res_tagged[0]
        entry_level = entry_obj["price"]
        entry_w = entry_obj["weight"]
        entry_dist = entry_level - curr
        max_entry_dist = atr_daily * (0.3 if entry_w <= 1 else 0.7 if entry_w == 2 else 1.0)
        if entry_dist < 0 or entry_dist > max_entry_dist:
            return None
        sl = structural_sl(entry_level, entry_obj, "short")
        risk = sl - entry_level
        if risk <= 0:
            return None
        t1_obj = best_t1(sup_tagged, entry_level, risk * min_rr)
        if t1_obj is None:
            return None
        t1 = t1_obj["price"]
        sup_after = [l for l in sup_tagged if l["price"] < t1]
        t2 = sup_after[0]["price"] if sup_after else round(t1 - risk, 5)
        rr1 = round((entry_level - t1) / risk, 2)
        rr2 = round((entry_level - t2) / risk, 2)
        at_level = is_at_level(curr, entry_level, atr_15m, entry_w)
        sl_src = "zone" if entry_obj.get("zone_top") else "struktur"
        return {
            "entry": round(entry_level, 5), "sl": sl, "sl_type": sl_src,
            "t1": round(t1, 5), "t2": round(t2, 5),
            "rr_t1": rr1, "rr_t2": rr2, "min_rr": min_rr,
            "risk_atr_d": round(risk / atr_daily, 2),
            "entry_dist_atr": round(entry_dist / atr_daily, 2),
            "entry_weight": entry_w, "t1_source": t1_obj["source"],
            "t1_quality": t1_obj["t1_quality"],
            "status": "aktiv" if at_level else "watchlist",
            "timeframe": "D1/4H",
        }


# ---------------------------------------------------------------------------
# Sentiment and macro helpers
# ---------------------------------------------------------------------------
def fetch_fear_greed():
    try:
        url = "https://production.dataviz.cnn.io/index/fearandgreed/graphdata"
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/120.0",
            "Accept": "application/json, text/plain, */*",
            "Referer": "https://edition.cnn.com/markets/fear-and-greed",
            "Origin": "https://edition.cnn.com",
        })
        with urllib.request.urlopen(req, timeout=8) as r:
            d = json.loads(r.read())
        return {"score": round(d["fear_and_greed"]["score"], 1),
                "rating": d["fear_and_greed"]["rating"]}
    except Exception as e:
        log.error("Fear&Greed: %s", e)
        return None


def fetch_news_sentiment():
    """Fetch RSS news and score risk-on/risk-off keywords."""
    RISK_ON = [
        "peace", "ceasefire", "deal", "agreement", "truce", "treaty",
        "stimulus", "rate cut", "rate cuts", "recovery", "trade deal",
        "tariff pause", "tariff reduction", "de-escalation", "optimism",
        "soft landing", "talks progress", "diplomatic", "breakthrough",
    ]
    RISK_OFF = [
        "war", "attack", "invasion", "escalation", "sanctions", "default",
        "crisis", "collapse", "recession", "military strike", "nuclear",
        "terror", "conflict", "threatens", "tariff hike", "new tariffs",
        "sell-off", "selloff", "bank run", "crash", "downgrade", "emergency",
    ]
    feeds = [
        "https://news.google.com/rss/search?q=economy+markets+geopolitics&hl=en-US&gl=US&ceid=US:en",
        "https://feeds.bbci.co.uk/news/world/rss.xml",
    ]
    headlines = []
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
            log.error("News (%s): %s", url[:45], e)
    if not headlines:
        return None
    ro_count = roff_count = 0
    drivers = []
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
    return {
        "score": net, "label": label, "top_headlines": headlines[:5],
        "key_drivers": drivers[:6], "ro_count": ro_count,
        "roff_count": roff_count, "headlines_n": len(headlines),
    }


MACRO_SYMBOLS = {
    "HYG": "HYG", "TIP": "TIP", "TNX": "^TNX", "IRX": "^IRX",
    "Copper": "HG=F", "EEM": "EEM",
}


def fetch_macro_indicators():
    """Fetch supplementary macro indicators (yields, HYG, copper, EM)."""
    out = {}
    log.info("FRED: fetching yields...")
    for key, series in [("TNX", "DGS10"), ("IRX", "DTB3")]:
        val = fetch_fred(series)
        if val:
            out[key] = {"price": round(val, 3), "chg1d": 0, "chg5d": 0}
        else:
            daily = fetch_yahoo(MACRO_SYMBOLS[key], "1d", "30d")
            if daily and len(daily) >= 2:
                curr = daily[-1][2]
                c5 = daily[-6][2] if len(daily) >= 6 else curr
                out[key] = {"price": round(curr, 3), "chg1d": 0,
                            "chg5d": round((curr / c5 - 1) * 100, 2)}
            else:
                out[key] = None

    for key in ["HYG", "TIP", "Copper", "EEM"]:
        sym = MACRO_SYMBOLS[key]
        daily = fetch_prices(sym, "1d", "30d")
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


def detect_conflict(vix, dxy_5d, fg, cot_usd, hy_stress=False, yield_curve=None, news_sent=None):
    """Detect macro conflicts and divergences."""
    conflicts = []
    if vix > 25 and dxy_5d < 0:
        conflicts.append("VIX>25 but DXY falling - risk-off without USD demand")
    if fg and fg["score"] < 30 and dxy_5d < 0:
        conflicts.append("Extreme fear but USD weakening - abnormal")
    if fg and fg["score"] > 70 and vix > 22:
        conflicts.append("Greed but VIX elevated - divergence")
    if cot_usd and cot_usd > 0 and dxy_5d < -1:
        conflicts.append("COT long USD but price falling - divergence")
    if hy_stress and vix < 20:
        conflicts.append("HY spreads widening but VIX low - hidden credit risk")
    if yield_curve is not None and yield_curve < -0.3:
        conflicts.append(f"Yield curve inverted ({yield_curve:+.2f}%) - recession risk")
    if news_sent and news_sent.get("label") == "risk_on" and vix > 25:
        conflicts.append("News risk-on but VIX elevated - sentiment shift in progress")
    if news_sent and news_sent.get("label") == "risk_off" and fg and fg["score"] > 60:
        conflicts.append("News risk-off but Fear&Greed shows greed - divergence")
    return conflicts


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------
def main():
    """Run the full analysis pipeline."""
    # Load COT data
    cot_data = {}
    cot_file = os.path.join(DATA_DIR, "cot", "combined", "latest.json")
    if os.path.exists(cot_file):
        with open(cot_file) as f:
            for d in json.load(f):
                cot_data[d["market"].lower()] = d

    # Load calendar
    calendar_events = []
    cal_file = os.path.join(DATA_DIR, "prices", "calendar_latest.json")
    if os.path.exists(cal_file):
        try:
            with open(cal_file) as f:
                cal_data = json.load(f)
            calendar_events = cal_data.get("events", [])
            log.info("Calendar: %d events loaded", len(calendar_events))
        except Exception:
            pass

    def get_binary_risk(instrument_key, hours=4):
        risks = []
        for ev in calendar_events:
            if ev.get("impact") != "High":
                continue
            ha = ev.get("hours_away", 99)
            if ha < 0 or ha > hours:
                continue
            berorte = ev.get("berorte", [])
            if instrument_key in berorte or not berorte:
                risks.append({"title": ev["title"], "cet": ev["cet"], "country": ev["country"]})
        return risks

    # Load fundamentals
    fund_data = {}
    fund_file = os.path.join(DATA_DIR, "prices", "fundamentals_latest.json")
    if os.path.exists(fund_file):
        try:
            with open(fund_file) as f:
                fund_data = json.load(f)
            n = len(fund_data.get("indicators", {}))
            log.info("Fundamentals: %d indicators loaded", n)
        except Exception:
            pass

    # Fear & Greed
    log.info("Fetching Fear & Greed...")
    fg = fetch_fear_greed()
    if fg:
        log.info("  -> %s (%s)", fg["score"], fg["rating"])

    # News sentiment
    log.info("Fetching news sentiment...")
    news_sentiment = fetch_news_sentiment()

    # Prices and setups
    prices, levels = {}, {}

    for inst in INSTRUMENTS:
        log.info("Fetching %s...", inst["navn"])

        daily = fetch_prices(inst["symbol"], "1d", "1y")
        rows_15m = fetch_prices(inst["symbol"], "15m", "5d")
        rows_1h = fetch_prices(inst["symbol"], "60m", "60d")
        h4 = to_4h(rows_1h) if rows_1h else []

        if not daily or len(daily) < 15:
            continue

        curr = daily[-1][2]
        if rows_15m and len(rows_15m) > 0:
            curr = rows_15m[-1][2]

        atr_d = calc_atr(daily, 14)
        atr_15m = calc_atr(rows_15m, 14) if len(rows_15m) >= 15 else None
        atr_4h = calc_atr(h4, 14) if len(h4) >= 15 else None
        sma200 = sum(r[2] for r in daily[-200:]) / min(200, len(daily))

        c1 = daily[-2][2] if len(daily) >= 2 else curr
        c5 = daily[-6][2] if len(daily) >= 6 else curr
        c20 = daily[-21][2] if len(daily) >= 21 else curr
        prices[inst["key"]] = {
            "price": round(curr, 4 if curr < 100 else 2),
            "chg1d": round((curr / c1 - 1) * 100, 2),
            "chg5d": round((curr / c5 - 1) * 100, 2),
            "chg20d": round((curr / c20 - 1) * 100, 2),
        }

        if inst["key"] == "VIX":
            continue

        # SMC analysis
        smc = smc_1h = smc_4h = None
        if SMC_OK and rows_15m and len(rows_15m) > 50:
            try:
                smc = run_smc(rows_15m, swing_length=5)
            except Exception as e:
                log.error("SMC 15m: %s", e)
        if SMC_OK and rows_1h and len(rows_1h) > 50:
            try:
                smc_1h = run_smc(rows_1h, swing_length=10)
            except Exception as e:
                log.error("SMC 1H: %s", e)
        if SMC_OK and h4 and len(h4) > 30:
            try:
                smc_4h = run_smc(h4, swing_length=5)
            except Exception as e:
                log.error("SMC 4H: %s", e)

        # Build multi-timeframe level map
        pdh, pdl, pdc = get_pdh_pdl_pdc(daily)
        pwh, pwl = get_pwh_pwl(daily)
        raw_res, raw_sup = [], []

        if pwh and pwh > curr:
            raw_res.append({"price": pwh, "source": "PWH", "weight": 5})
        if pwl and pwl < curr:
            raw_sup.append({"price": pwl, "source": "PWL", "weight": 5})
        if pdh and pdh > curr:
            raw_res.append({"price": pdh, "source": "PDH", "weight": 4})
        if pdl and pdl < curr:
            raw_sup.append({"price": pdl, "source": "PDL", "weight": 4})
        if pdc:
            if pdc > curr:
                raw_res.append({"price": pdc, "source": "PDC", "weight": 3})
            elif pdc < curr:
                raw_sup.append({"price": pdc, "source": "PDC", "weight": 3})

        res_d, sup_d = find_swing_levels(daily)
        for r in res_d:
            if r > curr:
                raw_res.append({"price": r, "source": "D1", "weight": 3})
        for s in sup_d:
            if s < curr:
                raw_sup.append({"price": s, "source": "D1", "weight": 3})

        res_4h, sup_4h = find_swing_levels(h4, n=3) if len(h4) >= 10 else ([], [])
        for r in res_4h:
            if r > curr:
                raw_res.append({"price": r, "source": "4H", "weight": 2})
        for s in sup_4h:
            if s < curr:
                raw_sup.append({"price": s, "source": "4H", "weight": 2})

        # SMC zones
        for smc_data, src, w in [(smc_1h, "SMC1H", 3), (smc_4h, "SMC4H", 2), (smc, "SMC15m", 1)]:
            if smc_data:
                for z in smc_data.get("supply_zones", []):
                    if z["poi"] > curr:
                        raw_res.append({"price": z["poi"], "source": src, "weight": w,
                                        "zone_top": z["top"], "zone_bottom": z["bottom"]})
                for z in smc_data.get("demand_zones", []):
                    if z["poi"] < curr:
                        raw_sup.append({"price": z["poi"], "source": src, "weight": w,
                                        "zone_top": z["top"], "zone_bottom": z["bottom"]})

        res_15m, sup_15m = find_intraday_levels(rows_15m) if rows_15m else ([], [])
        for r in res_15m:
            if r > curr:
                raw_res.append({"price": r, "source": "15m", "weight": 1})
        for s in sup_15m:
            if s < curr:
                raw_sup.append({"price": s, "source": "15m", "weight": 1})

        atr_for_merge = atr_15m if atr_15m else (atr_d * 0.4 if atr_d else None)
        tagged_res = merge_tagged_levels(raw_res, curr, atr_for_merge)
        tagged_sup = merge_tagged_levels(raw_sup, curr, atr_for_merge)

        # EMA + Regime
        closes_d = [r[2] for r in daily]
        closes_15 = [r[2] for r in rows_15m] if rows_15m else []
        ema9_d = calc_ema(closes_d, 9)
        ema9_15m = calc_ema(closes_15, 9) if closes_15 else None

        d1_bull = curr > ema9_d if ema9_d else None
        m15_bull = curr > ema9_15m if ema9_15m else None
        if d1_bull and m15_bull:
            align = "bull"
        elif not d1_bull and not m15_bull:
            align = "bear"
        else:
            align = "mixed"

        # COT
        cot_key = COT_MAP.get(inst["key"], "")
        cot_entry = cot_data.get(cot_key, {})
        spec_net = (cot_entry.get("spekulanter") or {}).get("net", 0) or 0
        oi = cot_entry.get("open_interest", 1) or 1
        cot_pct = spec_net / oi * 100
        cot_bias = "LONG" if cot_pct > 4 else "SHORT" if cot_pct < -4 else "NEUTRAL"
        cot_color = "bull" if cot_pct > 4 else "bear" if cot_pct < -4 else "neutral"
        _cot_chg = cot_entry.get("change_spec_net", 0) or 0
        if _cot_chg == 0:
            cot_momentum = "STABIL"
        elif (_cot_chg > 0 and spec_net >= 0) or (_cot_chg < 0 and spec_net <= 0):
            cot_momentum = "OKER"
        else:
            cot_momentum = "SNUR"

        # Score
        above_sma = curr > sma200
        chg5 = prices[inst["key"]]["chg5d"]
        chg20 = prices[inst["key"]]["chg20d"]
        session_now = get_session_status()

        at_sup = any(is_at_level(curr, l["price"], atr_for_merge or atr_d * 0.4, l["weight"])
                     for l in tagged_sup) if tagged_sup else False
        at_res = any(is_at_level(curr, l["price"], atr_for_merge or atr_d * 0.4, l["weight"])
                     for l in tagged_res) if tagged_res else False
        at_level_now = at_sup or at_res

        nearest_sup_w = tagged_sup[0]["weight"] if tagged_sup else 0
        nearest_res_w = tagged_res[0]["weight"] if tagged_res else 0
        htf_level_nearby = max(nearest_sup_w, nearest_res_w) >= 3

        dir_color = "bull" if (above_sma and chg5 > 0) else "bear" if (not above_sma and chg5 < 0) else ("bull" if above_sma else "bear")
        cot_confirms = (cot_bias == "LONG" and dir_color == "bull") or (cot_bias == "SHORT" and dir_color == "bear")
        cot_strong = abs(cot_pct) > 10
        no_event_risk = len(get_binary_risk(inst["key"], hours=4)) == 0

        bos_1h_levels = (smc_1h or {}).get("bos_levels", [])
        bos_4h_levels = (smc_4h or {}).get("bos_levels", [])
        recent_bos = sorted(bos_1h_levels + bos_4h_levels, key=lambda b: b["idx"], reverse=True)[:3]
        bos_confirms = any(
            (b["type"] == "BOS_opp" and dir_color == "bull") or
            (b["type"] == "BOS_ned" and dir_color == "bear")
            for b in recent_bos
        )

        smc_1h_structure = (smc_1h or {}).get("structure", "MIXED")
        smc_struct_confirms = (
            (dir_color == "bull" and smc_1h_structure in ("BULLISH", "BULLISH_SVAK")) or
            (dir_color == "bear" and smc_1h_structure in ("BEARISH", "BEARISH_SVAK"))
        )

        ns_label = (news_sentiment or {}).get("label", "neutral")
        nc_map = NEWS_CONFIRMS_MAP.get(inst["key"], (None, None))
        news_confirms_dir = False
        if ns_label == "risk_on" and nc_map[0]:
            news_confirms_dir = (nc_map[0] == dir_color)
        elif ns_label == "risk_off" and nc_map[1]:
            news_confirms_dir = (nc_map[1] == dir_color)

        inst_fund = fund_data.get("instrument_scores", {}).get(inst["key"], {})
        fund_confirms = (inst_fund.get("score", 0) > 0.3 and dir_color == "bull") or \
                        (inst_fund.get("score", 0) < -0.3 and dir_color == "bear")

        score_details = [
            {"check": "Above SMA200", "value": above_sma},
            {"check": "20d momentum confirms", "value": (chg20 > 0 if dir_color == "bull" else chg20 < 0)},
            {"check": "COT confirms direction", "value": cot_confirms},
            {"check": "COT strong (>10%)", "value": cot_strong},
            {"check": "Price AT HTF level", "value": at_level_now},
            {"check": "HTF level D1/Weekly", "value": htf_level_nearby},
            {"check": "D1 + 4H trend aligned", "value": align in ("bull", "bear")},
            {"check": "No event risk (4h)", "value": no_event_risk},
            {"check": "News confirms", "value": news_confirms_dir},
            {"check": "Fundamentals confirm", "value": fund_confirms},
            {"check": "BOS 1H/4H confirms", "value": bos_confirms},
            {"check": "SMC 1H structure confirms", "value": smc_struct_confirms},
        ]
        score = sum(1 for s in score_details if s["value"])
        max_score = len(score_details)
        grade = "A+" if score >= 11 else "A" if score >= 9 else "B" if score >= 6 else "C"

        if score >= 6 and cot_confirms and htf_level_nearby:
            timeframe_bias = "MAKRO"
        elif score >= 4 and htf_level_nearby:
            timeframe_bias = "SWING"
        elif score >= 2 and at_level_now and session_now["active"]:
            timeframe_bias = "SCALP"
        else:
            timeframe_bias = "WATCHLIST"

        vix_price = (prices.get("VIX") or {}).get("price", 20)
        pos_size = "Full" if vix_price < 20 else "Halv" if vix_price < 30 else "Kvart"

        atr_for_setup = atr_15m if atr_15m else (atr_d * 0.4)
        setup_long = make_setup_l2l(curr, atr_for_setup, atr_d, tagged_sup, tagged_res, "long", inst["klasse"])
        setup_short = make_setup_l2l(curr, atr_for_setup, atr_d, tagged_sup, tagged_res, "short", inst["klasse"])

        def fmt_level(tagged, atr):
            out = []
            for l in tagged[:5]:
                lr = round(l["price"], 5 if l["price"] < 100 else 2)
                out.append({
                    "name": l.get("source", "?"), "level": lr,
                    "weight": l.get("weight", 1),
                    "dist_atr": round(abs(l["price"] - curr) / (atr or 1), 1),
                })
            return out

        dir_tag = "^" if dir_color == "bull" else "v"
        log.info("  %s %s  %s(%d/%d) %s  TF:%s", f"{inst['navn']:10s}", f"{curr:.5f}", grade, score, max_score, dir_tag, timeframe_bias)

        def smc_dict(s):
            if not s:
                return {"structure": None, "supply_zones": [], "demand_zones": [],
                        "bos_levels": [], "last_swing_high": None, "last_swing_low": None}
            return {k: s[k] for k in ("structure", "supply_zones", "demand_zones",
                                       "bos_levels", "last_swing_high", "last_swing_low")}

        levels[inst["key"]] = {
            "name": inst["navn"], "label": inst["label"], "klasse": inst["klasse"],
            "session": inst["session"], "current": round(curr, 5 if curr < 100 else 2),
            "atr_15m": round(atr_15m, 5) if atr_15m else None,
            "atr_daily": round(atr_d, 5) if atr_d else None,
            "atr_4h": round(atr_4h, 5) if atr_4h else None,
            "at_level_now": at_level_now, "status": "aktiv" if at_level_now else "watchlist",
            "sma200": round(sma200, 4 if sma200 < 100 else 2),
            "sma200_pos": "over" if above_sma else "under",
            "chg5d": chg5, "chg20d": chg20,
            "dir_color": dir_color, "grade": grade, "score": score,
            "score_details": score_details,
            "resistances": fmt_level(tagged_res, atr_15m or atr_d),
            "supports": fmt_level(tagged_sup, atr_15m or atr_d),
            "setup_long": setup_long, "setup_short": setup_short,
            "binary_risk": get_binary_risk(inst["key"]),
            "smc": smc_dict(smc), "smc_1h": smc_dict(smc_1h), "smc_4h": smc_dict(smc_4h),
            "pos_size": pos_size,
            "cot": {"bias": cot_bias, "color": cot_color, "net": spec_net,
                    "chg": cot_entry.get("change_spec_net", 0), "pct": round(abs(cot_pct), 1),
                    "momentum": cot_momentum},
            "combined_bias": "LONG" if dir_color == "bull" else "SHORT",
            "timeframe_bias": timeframe_bias,
            "sentiment": {"fear_greed": fg},
            "fundamentals": {
                "score": inst_fund.get("score", 0),
                "bias": inst_fund.get("bias", "neutral"),
                "confirms": fund_confirms,
            },
        }

    # Macro indicators
    log.info("Fetching macro indicators...")
    macro_ind = fetch_macro_indicators()

    hyg = macro_ind.get("HYG") or {}
    hy_stress = hyg.get("chg5d", 0) < -1.5
    tnx = macro_ind.get("TNX") or {}
    irx = macro_ind.get("IRX") or {}
    yield_10y = tnx.get("price")
    yield_3m = irx.get("price")
    yield_curve = round(yield_10y - yield_3m, 2) if (yield_10y and yield_3m) else None

    vix_price = (prices.get("VIX") or {}).get("price", 20)
    dxy_5d = (prices.get("DXY") or {}).get("chg5d", 0)
    brent_p = (prices.get("Brent") or {}).get("price", 80)
    cot_dxy = cot_data.get("usd index", {})
    cot_dxy_net = ((cot_dxy.get("spekulanter") or {}).get("net", 0) or 0)
    conflicts = detect_conflict(vix_price, dxy_5d, fg, cot_dxy_net, hy_stress, yield_curve, news_sentiment)

    risk_off_signals = sum([vix_price > 25, hy_stress, (yield_curve or 0) < -0.3,
                            (fg["score"] if fg else 50) < 35])
    if conflicts:
        smile_pos, usd_bias, usd_color, smile_desc = (
            "konflikt", "UKLAR", "warn",
            "Conflicting signals: " + " | ".join(conflicts[:2]))
    elif vix_price > 30 or risk_off_signals >= 2:
        smile_pos, usd_bias, usd_color, smile_desc = (
            "venstre", "STERKT", "bull", "Risk-off - USD safe haven")
    elif vix_price < 18 and brent_p < 85 and not hy_stress:
        smile_pos, usd_bias, usd_color, smile_desc = (
            "midten", "SVAKT", "bear", "Goldilocks - weak USD")
    else:
        smile_pos, usd_bias, usd_color, smile_desc = (
            "hoyre", "MODERAT", "bull", "Growth/inflation driving USD")

    if vix_price > 30:
        vix_regime = {"value": vix_price, "label": "Extreme fear - QUARTER size",
                      "color": "bear", "regime": "extreme"}
    elif vix_price > 20:
        vix_regime = {"value": vix_price, "label": "Elevated - HALF size",
                      "color": "warn", "regime": "elevated"}
    else:
        vix_regime = {"value": vix_price, "label": "Normal - full size",
                      "color": "bull", "regime": "normal"}

    macro = {
        "date": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "cot_date": max((d.get("date", "") for d in cot_data.values() if d.get("date")), default="unknown"),
        "prices": prices,
        "vix_regime": vix_regime,
        "sentiment": {"fear_greed": fg, "news": news_sentiment, "conflicts": conflicts},
        "dollar_smile": {
            "position": smile_pos, "usd_bias": usd_bias,
            "usd_color": usd_color, "desc": smile_desc,
            "conflicts": conflicts,
            "inputs": {
                "vix": vix_price, "hy_stress": hy_stress,
                "brent": brent_p, "yield_curve": yield_curve,
            },
        },
        "macro_indicators": macro_ind,
        "trading_levels": levels,
        "calendar": calendar_events,
    }

    with open(OUT, "w") as f:
        json.dump(macro, f, ensure_ascii=False, indent=2)
    log.info("OK -> %s  (%d instruments)", OUT, len(levels))
    if conflicts:
        log.warning("Conflicts:")
        for c in conflicts:
            log.warning("  - %s", c)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    main()
