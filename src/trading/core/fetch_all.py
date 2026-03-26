#!/usr/bin/env python3
"""fetch_all.py - Full analysis pipeline. Fetches prices, runs SMC/COT analysis,
scores instruments on 12 criteria, outputs data/prices/macro_latest.json.
Data priority: Twelvedata -> Stooq -> Yahoo. Finnhub overlay on last bar."""

import json, logging, os, sys, time, urllib.parse, urllib.request
from datetime import datetime, timezone, timedelta

log = logging.getLogger(__name__)

_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(_DIR, "..", "..", ".."))
DATA_DIR = os.path.join(PROJECT_ROOT, "data")
OUT = os.path.join(DATA_DIR, "prices", "macro_latest.json")
os.makedirs(os.path.join(DATA_DIR, "prices"), exist_ok=True)

sys.path.insert(0, _DIR)
try:
    from smc import run_smc
    SMC_OK = True
except ImportError:
    SMC_OK = False

# Analysis modules
from src.analysis.technical import calc_atr, calc_ema, to_4h
from src.analysis.levels import (get_pdh_pdl_pdc, get_pwh_pwl, get_session_status,
    find_intraday_levels, find_swing_levels, is_at_level, merge_tagged_levels)
from src.analysis.setup_builder import make_setup_l2l
from src.analysis.cot_analyzer import classify_cot_bias, classify_cot_momentum
from src.analysis.sentiment import (fetch_fear_greed as _fetch_fear_greed,
    fetch_news_sentiment as _fetch_news_sentiment,
    fetch_macro_indicators as _fetch_macro_indicators, detect_conflict)

# Instrument definitions
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

TWELVEDATA_API_KEY = os.environ.get("TWELVEDATA_API_KEY", "")
FINNHUB_API_KEY = os.environ.get("FINNHUB_API_KEY", "")
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


def fetch_yahoo(symbol, interval="1d", range_="1y"):
    """Fetch OHLC from Yahoo Finance. Returns [(h,l,c), ...] or []."""
    url = (f"https://query1.finance.yahoo.com/v8/finance/chart/"
           f"{urllib.parse.quote(symbol)}?interval={interval}&range={range_}")
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            d = json.loads(r.read())
        q = d["chart"]["result"][0]["indicators"]["quote"][0]
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
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"}), timeout=12) as r:
            d = json.loads(r.read())
        if d.get("status") == "error":
            log.warning("TD %s: %s", td_sym, d.get("message", ""))
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
    """Fetch daily OHLC from Stooq."""
    stooq_sym = STOOQ_MAP.get(symbol)
    if not stooq_sym:
        return []
    days = STOOQ_DAYS.get(range_, 400)
    d2 = datetime.now(timezone.utc).strftime("%Y%m%d")
    d1 = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y%m%d")
    url = f"https://stooq.com/q/d/l/?s={stooq_sym}&i=d&d1={d1}&d2={d2}"
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"}), timeout=10) as r:
            text = r.read().decode(errors="replace")
        rows = []
        for line in text.strip().split("\n")[1:]:
            parts = line.strip().split(",")
            if len(parts) >= 5:
                try:
                    h, l, c = float(parts[2]), float(parts[3]), float(parts[4])
                    if h and l and c:
                        rows.append((h, l, c))
                except (ValueError, IndexError):
                    pass
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
    url = f"https://finnhub.io/api/v1/quote?symbol={urllib.parse.quote(fh_sym)}&token={FINNHUB_API_KEY}"
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"}), timeout=8) as r:
            d = json.loads(r.read())
        c, h, l = d.get("c", 0), d.get("h", 0), d.get("l", 0)
        return (h, l, c) if c and h and l else None
    except Exception as e:
        log.error("Finnhub %s: %s", fh_sym, e)
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

def fetch_fear_greed():
    r = _fetch_fear_greed()
    return r.model_dump() if r else None

def fetch_news_sentiment():
    r = _fetch_news_sentiment()
    return r.model_dump() if r else None

def fetch_macro_indicators():
    return _fetch_macro_indicators()

# Pipeline helpers
_SMC_KEYS = ("structure", "supply_zones", "demand_zones", "bos_levels", "last_swing_high", "last_swing_low")

def _setup_to_dict(m):
    return m.model_dump() if m else None

def _smc_dict(s):
    return {k: s[k] for k in _SMC_KEYS} if s else dict.fromkeys(
        ("structure", "last_swing_high", "last_swing_low"), None,
    ) | {"supply_zones": [], "demand_zones": [], "bos_levels": []}

def _try_smc(rows, min_len, swing_length, label):
    if not SMC_OK or not rows or len(rows) < min_len:
        return None
    try:
        return run_smc(rows, swing_length=swing_length)
    except Exception as e:
        log.error("SMC %s: %s", label, e)
        return None

def _build_raw_levels(curr, daily, h4, rows_15m, smc, smc_1h, smc_4h):
    """Collect raw resistance/support from all timeframes + SMC."""
    raw_res, raw_sup = [], []
    pdh, pdl, pdc = get_pdh_pdl_pdc(daily)
    pwh, pwl = get_pwh_pwl(daily)
    for price, src, w, is_res in [(pwh, "PWH", 5, True), (pwl, "PWL", 5, False),
                                   (pdh, "PDH", 4, True), (pdl, "PDL", 4, False)]:
        if price and ((is_res and price > curr) or (not is_res and price < curr)):
            (raw_res if is_res else raw_sup).append({"price": price, "source": src, "weight": w})
    if pdc:
        t = raw_res if pdc > curr else raw_sup if pdc < curr else None
        if t is not None:
            t.append({"price": pdc, "source": "PDC", "weight": 3})
    for res, sup, src, w in [(*find_swing_levels(daily), "D1", 3)] + \
            ([(*find_swing_levels(h4, n=3), "4H", 2)] if len(h4) >= 10 else []) + \
            ([(*find_intraday_levels(rows_15m), "15m", 1)] if rows_15m else []):
        for r in res:
            if r > curr:
                raw_res.append({"price": r, "source": src, "weight": w})
        for s in sup:
            if s < curr:
                raw_sup.append({"price": s, "source": src, "weight": w})
    for smc_data, src, w in [(smc_1h, "SMC1H", 3), (smc_4h, "SMC4H", 2), (smc, "SMC15m", 1)]:
        if not smc_data:
            continue
        for z in smc_data.get("supply_zones", []):
            if z["poi"] > curr:
                raw_res.append({"price": z["poi"], "source": src, "weight": w,
                                "zone_top": z["top"], "zone_bottom": z["bottom"]})
        for z in smc_data.get("demand_zones", []):
            if z["poi"] < curr:
                raw_sup.append({"price": z["poi"], "source": src, "weight": w,
                                "zone_top": z["top"], "zone_bottom": z["bottom"]})
    return raw_res, raw_sup

def _fmt_levels(tagged, atr, curr):
    return [{"name": l.get("source", "?"),
             "level": round(l["price"], 5 if l["price"] < 100 else 2),
             "weight": l.get("weight", 1),
             "dist_atr": round(abs(l["price"] - curr) / (atr or 1), 1)}
            for l in tagged[:5]]

def _load_json(path):
    if not os.path.exists(path):
        return None
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return None

def _no_to_ascii(s):
    return s.replace("\u00d8", "O").replace("\u00f8", "o")


def main():
    """Run the full analysis pipeline."""
    cot_data = {}
    raw = _load_json(os.path.join(DATA_DIR, "cot", "combined", "latest.json"))
    if raw:
        for d in raw:
            cot_data[d["market"].lower()] = d
    cal_raw = _load_json(os.path.join(DATA_DIR, "prices", "calendar_latest.json"))
    calendar_events = (cal_raw or {}).get("events", [])
    if calendar_events:
        log.info("Calendar: %d events loaded", len(calendar_events))

    def get_binary_risk(instrument_key, hours=4):
        return [{"title": ev["title"], "cet": ev["cet"], "country": ev["country"]}
                for ev in calendar_events
                if ev.get("impact") == "High" and 0 <= ev.get("hours_away", 99) <= hours
                and (instrument_key in ev.get("berorte", []) or not ev.get("berorte", []))]

    fund_data = _load_json(os.path.join(DATA_DIR, "prices", "fundamentals_latest.json")) or {}
    if fund_data:
        log.info("Fundamentals: %d indicators loaded", len(fund_data.get("indicators", {})))
    log.info("Fetching Fear & Greed...")
    fg = fetch_fear_greed()
    if fg:
        log.info("  -> %s (%s)", fg["score"], fg["rating"])
    log.info("Fetching news sentiment...")
    news_sentiment = fetch_news_sentiment()

    prices, levels = {}, {}
    for inst in INSTRUMENTS:
        log.info("Fetching %s...", inst["navn"])
        daily = fetch_prices(inst["symbol"], "1d", "1y")
        rows_15m = fetch_prices(inst["symbol"], "15m", "5d")
        rows_1h = fetch_prices(inst["symbol"], "60m", "60d")
        h4 = to_4h(rows_1h) if rows_1h else []
        if not daily or len(daily) < 15:
            continue
        curr = rows_15m[-1][2] if rows_15m else daily[-1][2]
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

        smc = _try_smc(rows_15m, 50, 5, "15m")
        smc_1h = _try_smc(rows_1h, 50, 10, "1H")
        smc_4h = _try_smc(h4, 30, 5, "4H")
        raw_res, raw_sup = _build_raw_levels(curr, daily, h4, rows_15m, smc, smc_1h, smc_4h)
        atr_merge = atr_15m or (atr_d * 0.4 if atr_d else None)
        tagged_res = merge_tagged_levels(raw_res, curr, atr_merge)
        tagged_sup = merge_tagged_levels(raw_sup, curr, atr_merge)

        # EMA regime
        ema9_d = calc_ema([r[2] for r in daily], 9)
        ema9_15m = calc_ema([r[2] for r in rows_15m], 9) if rows_15m else None
        d1_bull = curr > ema9_d if ema9_d else None
        m15_bull = curr > ema9_15m if ema9_15m else None
        align = "bull" if (d1_bull and m15_bull) else "bear" if (not d1_bull and not m15_bull) else "mixed"

        # COT
        cot_entry = cot_data.get(COT_MAP.get(inst["key"], ""), {})
        spec_net = (cot_entry.get("spekulanter") or {}).get("net", 0) or 0
        oi = cot_entry.get("open_interest", 1) or 1
        cot_bias, cot_pct = classify_cot_bias(spec_net, oi)
        cot_bias = _no_to_ascii(cot_bias)
        cot_color = "bull" if cot_pct > 4 else "bear" if cot_pct < -4 else "neutral"
        _cot_chg = cot_entry.get("change_spec_net", 0) or 0
        cot_momentum = _no_to_ascii(classify_cot_momentum(_cot_chg, spec_net))

        # Scoring inputs
        above_sma = curr > sma200
        chg5, chg20 = prices[inst["key"]]["chg5d"], prices[inst["key"]]["chg20d"]
        session_now = get_session_status()
        atr_lvl = atr_merge or atr_d * 0.4
        at_sup = any(is_at_level(curr, l["price"], atr_lvl, l["weight"]) for l in tagged_sup) if tagged_sup else False
        at_res = any(is_at_level(curr, l["price"], atr_lvl, l["weight"]) for l in tagged_res) if tagged_res else False
        at_level_now = at_sup or at_res
        htf_level_nearby = max(tagged_sup[0]["weight"] if tagged_sup else 0,
                               tagged_res[0]["weight"] if tagged_res else 0) >= 3
        dir_color = "bull" if (above_sma and chg5 > 0) else "bear" if (not above_sma and chg5 < 0) else ("bull" if above_sma else "bear")
        cot_confirms = (cot_bias == "LONG" and dir_color == "bull") or (cot_bias == "SHORT" and dir_color == "bear")
        no_event_risk = not get_binary_risk(inst["key"], hours=4)
        bos_all = (smc_1h or {}).get("bos_levels", []) + (smc_4h or {}).get("bos_levels", [])
        recent_bos = sorted(bos_all, key=lambda b: b["idx"], reverse=True)[:3]
        bos_confirms = any((b["type"] == "BOS_opp" and dir_color == "bull") or
                           (b["type"] == "BOS_ned" and dir_color == "bear") for b in recent_bos)
        smc_1h_struct = (smc_1h or {}).get("structure", "MIXED")
        smc_struct_ok = ((dir_color == "bull" and smc_1h_struct in ("BULLISH", "BULLISH_SVAK")) or
                         (dir_color == "bear" and smc_1h_struct in ("BEARISH", "BEARISH_SVAK")))
        ns_label = (news_sentiment or {}).get("label", "neutral")
        nc = NEWS_CONFIRMS_MAP.get(inst["key"], (None, None))
        news_ok = (nc[0] == dir_color) if (ns_label == "risk_on" and nc[0]) else \
                  (nc[1] == dir_color) if (ns_label == "risk_off" and nc[1]) else False
        inst_fund = fund_data.get("instrument_scores", {}).get(inst["key"], {})
        fund_ok = (inst_fund.get("score", 0) > 0.3 and dir_color == "bull") or \
                  (inst_fund.get("score", 0) < -0.3 and dir_color == "bear")

        score_details = [
            {"check": "Above SMA200", "value": above_sma},
            {"check": "20d momentum confirms", "value": (chg20 > 0 if dir_color == "bull" else chg20 < 0)},
            {"check": "COT confirms direction", "value": cot_confirms},
            {"check": "COT strong (>10%)", "value": abs(cot_pct) > 10},
            {"check": "Price AT HTF level", "value": at_level_now},
            {"check": "HTF level D1/Weekly", "value": htf_level_nearby},
            {"check": "D1 + 4H trend aligned", "value": align in ("bull", "bear")},
            {"check": "No event risk (4h)", "value": no_event_risk},
            {"check": "News confirms", "value": news_ok},
            {"check": "Fundamentals confirm", "value": fund_ok},
            {"check": "BOS 1H/4H confirms", "value": bos_confirms},
            {"check": "SMC 1H structure confirms", "value": smc_struct_ok},
        ]
        score = sum(1 for s in score_details if s["value"])
        max_score = len(score_details)
        grade = "A+" if score >= 11 else "A" if score >= 9 else "B" if score >= 6 else "C"
        if score >= 6 and cot_confirms and htf_level_nearby:
            tf_bias = "MAKRO"
        elif score >= 4 and htf_level_nearby:
            tf_bias = "SWING"
        elif score >= 2 and at_level_now and session_now["active"]:
            tf_bias = "SCALP"
        else:
            tf_bias = "WATCHLIST"

        vix_price = (prices.get("VIX") or {}).get("price", 20)
        atr_setup = atr_15m or (atr_d * 0.4)
        log.info("  %s %s  %s(%d/%d) %s  TF:%s", f"{inst['navn']:10s}", f"{curr:.5f}",
                 grade, score, max_score, "^" if dir_color == "bull" else "v", tf_bias)

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
            "resistances": _fmt_levels(tagged_res, atr_15m or atr_d, curr),
            "supports": _fmt_levels(tagged_sup, atr_15m or atr_d, curr),
            "setup_long": _setup_to_dict(make_setup_l2l(curr, atr_setup, atr_d, tagged_sup, tagged_res, "long", inst["klasse"])),
            "setup_short": _setup_to_dict(make_setup_l2l(curr, atr_setup, atr_d, tagged_sup, tagged_res, "short", inst["klasse"])),
            "binary_risk": get_binary_risk(inst["key"]),
            "smc": _smc_dict(smc), "smc_1h": _smc_dict(smc_1h), "smc_4h": _smc_dict(smc_4h),
            "pos_size": "Full" if vix_price < 20 else "Halv" if vix_price < 30 else "Kvart",
            "cot": {"bias": cot_bias, "color": cot_color, "net": spec_net,
                    "chg": cot_entry.get("change_spec_net", 0), "pct": round(abs(cot_pct), 1),
                    "momentum": cot_momentum},
            "combined_bias": "LONG" if dir_color == "bull" else "SHORT",
            "timeframe_bias": tf_bias,
            "sentiment": {"fear_greed": fg},
            "fundamentals": {"score": inst_fund.get("score", 0),
                             "bias": inst_fund.get("bias", "neutral"), "confirms": fund_ok},
        }

    # Macro assembly
    log.info("Fetching macro indicators...")
    macro_ind = fetch_macro_indicators()
    hyg = macro_ind.get("HYG") or {}
    hy_stress = hyg.get("chg5d", 0) < -1.5
    tnx, irx = macro_ind.get("TNX") or {}, macro_ind.get("IRX") or {}
    yield_10y, yield_3m = tnx.get("price"), irx.get("price")
    yield_curve = round(yield_10y - yield_3m, 2) if (yield_10y and yield_3m) else None
    vix_price = (prices.get("VIX") or {}).get("price", 20)
    dxy_5d = (prices.get("DXY") or {}).get("chg5d", 0)
    brent_p = (prices.get("Brent") or {}).get("price", 80)
    cot_dxy_net = ((cot_data.get("usd index", {}).get("spekulanter") or {}).get("net", 0) or 0)
    conflicts = detect_conflict(vix_price, dxy_5d, fg, cot_dxy_net, hy_stress, yield_curve, news_sentiment)

    risk_off_n = sum([vix_price > 25, hy_stress, (yield_curve or 0) < -0.3, (fg["score"] if fg else 50) < 35])
    if conflicts:
        smile_pos, usd_bias, usd_color, smile_desc = (
            "konflikt", "UKLAR", "warn", "Conflicting signals: " + " | ".join(conflicts[:2]))
    elif vix_price > 30 or risk_off_n >= 2:
        smile_pos, usd_bias, usd_color, smile_desc = ("venstre", "STERKT", "bull", "Risk-off - USD safe haven")
    elif vix_price < 18 and brent_p < 85 and not hy_stress:
        smile_pos, usd_bias, usd_color, smile_desc = ("midten", "SVAKT", "bear", "Goldilocks - weak USD")
    else:
        smile_pos, usd_bias, usd_color, smile_desc = ("hoyre", "MODERAT", "bull", "Growth/inflation driving USD")

    if vix_price > 30:
        vix_regime = {"value": vix_price, "label": "Extreme fear - QUARTER size", "color": "bear", "regime": "extreme"}
    elif vix_price > 20:
        vix_regime = {"value": vix_price, "label": "Elevated - HALF size", "color": "warn", "regime": "elevated"}
    else:
        vix_regime = {"value": vix_price, "label": "Normal - full size", "color": "bull", "regime": "normal"}

    macro = {
        "date": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "cot_date": max((d.get("date", "") for d in cot_data.values() if d.get("date")), default="unknown"),
        "prices": prices, "vix_regime": vix_regime,
        "sentiment": {"fear_greed": fg, "news": news_sentiment, "conflicts": conflicts},
        "dollar_smile": {"position": smile_pos, "usd_bias": usd_bias, "usd_color": usd_color,
                         "desc": smile_desc, "conflicts": conflicts,
                         "inputs": {"vix": vix_price, "hy_stress": hy_stress,
                                    "brent": brent_p, "yield_curve": yield_curve}},
        "macro_indicators": macro_ind, "trading_levels": levels, "calendar": calendar_events,
    }
    with open(OUT, "w") as f:
        json.dump(macro, f, ensure_ascii=False, indent=2)
    log.info("OK -> %s  (%d instruments)", OUT, len(levels))
    for c in conflicts:
        log.warning("  CONFLICT: %s", c)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    main()
