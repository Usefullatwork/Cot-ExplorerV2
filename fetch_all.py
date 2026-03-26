#!/usr/bin/env python3
"""Macro analysis pipeline — orchestrates price fetching, technical/SMC/COT/
sentiment analysis, writes combined output to data/macro/latest.json.

Production entry point called by update.sh and src/pipeline/runner.py.
"""
import json, logging, os
from datetime import datetime, timezone
from pathlib import Path

from src.analysis.technical import calc_atr, calc_ema, to_4h
from src.analysis.levels import (
    get_pdh_pdl_pdc, get_pwh_pwl, get_session_status,
    find_intraday_levels, find_swing_levels, is_at_level, merge_tagged_levels,
)
from src.analysis.setup_builder import make_setup_l2l
from src.analysis.cot_analyzer import classify_cot_bias, classify_cot_momentum
from src.analysis.sentiment import (
    detect_conflict, fetch_fear_greed as _fetch_fg,
    fetch_news_sentiment as _fetch_news, fetch_macro_indicators as _fetch_macro,
)
from src.analysis.smc import run_smc
from src.trading.core.price_fetcher import (
    fetch_prices, INSTRUMENTS, NEWS_CONFIRMS_MAP, COT_MAP,
)

log = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")

BASE = Path(__file__).resolve().parent / "data"
OUT  = os.path.join(BASE, "macro", "latest.json")
os.makedirs(os.path.join(BASE, "macro"), exist_ok=True)

# ── Helpers ───────────────────────────────────────────────────────

def _setup_to_dict(setup):
    """Convert SetupL2L Pydantic model to plain dict, or pass through None/dict."""
    if setup is None:
        return None
    if hasattr(setup, "model_dump"):
        return setup.model_dump()
    return setup


def get_binary_risk(calendar_events, instrument_key, hours=4):
    risks = []
    for ev in calendar_events:
        if ev.get('impact') != 'High': continue
        ha = ev.get('hours_away', 99)
        if ha < 0 or ha > hours: continue
        berorte = ev.get('berorte', [])
        if instrument_key in berorte or not berorte:
            risks.append({'title': ev['title'], 'cet': ev['cet'], 'country': ev['country']})
    return risks


def fmt_level(tagged, typ, atr, curr):
    out = []
    for i, l in enumerate(tagged[:5]):
        lr = round(l["price"], 5 if l["price"] < 100 else 2)
        out.append({
            "name":     l.get("source", f"{typ}{i+1}"),
            "level":    lr,
            "weight":   l.get("weight", 1),
            "dist_atr": round(abs(l["price"] - curr) / (atr or 1), 1),
        })
    return out


def _smc_block(smc_result):
    """Format SMC result dict into output block."""
    if not smc_result:
        return {"structure":None,"supply_zones":[],"demand_zones":[],"bos_levels":[],
                "last_swing_high":None,"last_swing_low":None}
    return {
        "structure":    smc_result["structure"],
        "supply_zones": smc_result["supply_zones"],
        "demand_zones": smc_result["demand_zones"],
        "bos_levels":   smc_result["bos_levels"],
        "last_swing_high": smc_result["last_swing_high"],
        "last_swing_low":  smc_result["last_swing_low"],
    }

# ── Pipeline orchestration ────────────────────────────────────────

def _load_json(path):
    """Load JSON file or return None."""
    if not os.path.exists(path):
        return None
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return None


def main():
    fund_data = _load_json(os.path.join(BASE, "fundamentals", "latest.json")) or {}
    if fund_data:
        log.info(f"Fundamentals: {len(fund_data.get('indicators',{}))} indikatorer lastet ({fund_data.get('usd_fundamental',{}).get('bias','?')} USD)")

    cal_data = _load_json(os.path.join(BASE, 'calendar', 'latest.json')) or {}
    calendar_events = cal_data.get('events', [])
    if calendar_events:
        log.info(f'Kalender: {len(calendar_events)} events lastet')

    cot_data = {}
    cot_raw = _load_json(os.path.join(BASE, "combined", "latest.json"))
    if cot_raw:
        for d in cot_raw:
            cot_data[d["market"].lower()] = d

    log.info("Henter Fear & Greed...")
    fg_model = _fetch_fg()
    fg = fg_model.model_dump() if fg_model else None
    if fg: log.info(f"  -> {fg['score']} ({fg['rating']})")

    log.info("Henter nyhetssentiment...")
    ns_model = _fetch_news()
    news_sentiment = ns_model.model_dump() if ns_model else None

    prices, levels = {}, {}

    for inst in INSTRUMENTS:
        log.info(f"Henter {inst['navn']}...")

        daily    = fetch_prices(inst["symbol"], "1d",  "1y")
        rows_15m = fetch_prices(inst["symbol"], "15m", "5d")
        rows_1h  = fetch_prices(inst["symbol"], "60m", "60d")
        h4       = to_4h(rows_1h) if rows_1h else []

        if not daily or len(daily) < 15:
            continue

        curr = daily[-1][2]
        if rows_15m and len(rows_15m) > 0:
            curr = rows_15m[-1][2]

        atr_d    = calc_atr(daily, 14)
        atr_15m  = calc_atr(rows_15m, 14) if len(rows_15m) >= 15 else None
        atr_4h   = calc_atr(h4, 14) if len(h4) >= 15 else None
        sma200   = sum(r[2] for r in daily[-200:]) / min(200, len(daily))

        c1  = daily[-2][2] if len(daily)>=2  else curr
        c5  = daily[-6][2] if len(daily)>=6  else curr
        c20 = daily[-21][2] if len(daily)>=21 else curr
        prices[inst["key"]] = {
            "price":  round(curr, 4 if curr<100 else 2),
            "chg1d":  round((curr/c1-1)*100,  2),
            "chg5d":  round((curr/c5-1)*100,  2),
            "chg20d": round((curr/c20-1)*100, 2),
        }

        if inst["key"] == "VIX": continue

        smc = smc_1h = smc_4h = None
        if rows_15m and len(rows_15m) > 50:
            try: smc = run_smc(rows_15m, swing_length=5)
            except Exception as e: log.error(f"  SMC 15m FEIL: {e}")
        if rows_1h and len(rows_1h) > 50:
            try: smc_1h = run_smc(rows_1h, swing_length=10)
            except Exception as e: log.error(f"  SMC 1H FEIL: {e}")
        if h4 and len(h4) > 30:
            try: smc_4h = run_smc(h4, swing_length=5)
            except Exception as e: log.error(f"  SMC 4H FEIL: {e}")

        pdh, pdl, pdc = get_pdh_pdl_pdc(daily)
        pwh, pwl      = get_pwh_pwl(daily)
        raw_res, raw_sup = [], []
        if pwh and pwh > curr: raw_res.append({"price": pwh, "source": "PWH", "weight": 5})
        if pwl and pwl < curr: raw_sup.append({"price": pwl, "source": "PWL", "weight": 5})
        if pdh and pdh > curr: raw_res.append({"price": pdh, "source": "PDH", "weight": 4})
        if pdl and pdl < curr: raw_sup.append({"price": pdl, "source": "PDL", "weight": 4})
        if pdc:
            if pdc > curr: raw_res.append({"price": pdc, "source": "PDC", "weight": 3})
            elif pdc < curr: raw_sup.append({"price": pdc, "source": "PDC", "weight": 3})

        res_d, sup_d = find_swing_levels(daily)
        raw_res.extend({"price": r, "source": "D1", "weight": 3} for r in res_d if r > curr)
        raw_sup.extend({"price": s, "source": "D1", "weight": 3} for s in sup_d if s < curr)
        res_4h, sup_4h = find_swing_levels(h4, n=3) if len(h4) >= 10 else ([], [])
        raw_res.extend({"price": r, "source": "4H", "weight": 2} for r in res_4h if r > curr)
        raw_sup.extend({"price": s, "source": "4H", "weight": 2} for s in sup_4h if s < curr)
        for smc_result, src_label, w in [(smc_1h,"SMC1H",3),(smc_4h,"SMC4H",2),(smc,"SMC15m",1)]:
            if not smc_result: continue
            for z in smc_result.get("supply_zones", []):
                if z["poi"] > curr:
                    raw_res.append({"price":z["poi"],"source":src_label,"weight":w,
                                    "zone_top":z["top"],"zone_bottom":z["bottom"]})
            for z in smc_result.get("demand_zones", []):
                if z["poi"] < curr:
                    raw_sup.append({"price":z["poi"],"source":src_label,"weight":w,
                                    "zone_top":z["top"],"zone_bottom":z["bottom"]})

        res_15m, sup_15m = find_intraday_levels(rows_15m) if rows_15m else ([], [])
        raw_res.extend({"price": r, "source": "15m", "weight": 1} for r in res_15m if r > curr)
        raw_sup.extend({"price": s, "source": "15m", "weight": 1} for s in sup_15m if s < curr)
        atr_for_merge = atr_15m if atr_15m else (atr_d * 0.4 if atr_d else None)
        tagged_res = merge_tagged_levels(raw_res, curr, atr_for_merge)
        tagged_sup = merge_tagged_levels(raw_sup, curr, atr_for_merge)

        closes_d  = [r[2] for r in daily]
        closes_15 = [r[2] for r in rows_15m] if rows_15m else []
        ema9_d    = calc_ema(closes_d,  9)
        ema9_15m  = calc_ema(closes_15, 9) if closes_15 else None

        d1_bull  = curr > ema9_d   if ema9_d  else None
        m15_bull = curr > ema9_15m if ema9_15m else None
        d1_regime  = ("BULLISH" if d1_bull  else "BEARISH") if d1_bull  is not None else "NØYTRAL"
        m15_regime = ("BULLISH" if m15_bull else "BEARISH") if m15_bull is not None else "NØYTRAL"

        if d1_bull and m15_bull:       align = "bull"
        elif not d1_bull and not m15_bull: align = "bear"
        else:                           align = "mixed"

        session_now = get_session_status()
        cot_key   = COT_MAP.get(inst["key"],"")
        cot_entry = cot_data.get(cot_key, {})
        spec_net  = (cot_entry.get("spekulanter") or {}).get("net", 0) or 0
        oi        = cot_entry.get("open_interest", 1) or 1
        cot_bias, cot_pct = classify_cot_bias(spec_net, oi)
        cot_color = "bull" if cot_pct>4 else "bear" if cot_pct<-4 else "neutral"
        _cot_chg  = cot_entry.get("change_spec_net", 0) or 0
        cot_momentum = classify_cot_momentum(_cot_chg, spec_net)
        above_sma = curr > sma200
        chg5      = prices[inst["key"]]["chg5d"]
        chg20     = prices[inst["key"]]["chg20d"]
        fg_score  = fg["score"] if fg else 50

        at_sup = any(is_at_level(curr, l["price"], atr_for_merge or atr_d*0.4, l["weight"])
                     for l in tagged_sup) if tagged_sup else False
        at_res = any(is_at_level(curr, l["price"], atr_for_merge or atr_d*0.4, l["weight"])
                     for l in tagged_res) if tagged_res else False
        at_level_now = at_sup or at_res

        nearest_sup_w = tagged_sup[0]["weight"] if tagged_sup else 0
        nearest_res_w = tagged_res[0]["weight"] if tagged_res else 0
        htf_level_nearby = max(nearest_sup_w, nearest_res_w) >= 3

        klasse = inst["klasse"]
        sesjon_aktiv = session_now["active"]
        sesjon_riktig = (
            (klasse == "A" and "London" in session_now["label"]) or
            (klasse == "B" and ("London" in session_now["label"] or "NY" in session_now["label"])) or
            (klasse == "C" and "NY" in session_now["label"])
        )

        dir_color = "bull" if (above_sma and chg5>0) else "bear" if (not above_sma and chg5<0) else ("bull" if above_sma else "bear")
        cot_confirms = (cot_bias == "LONG" and dir_color == "bull") or (cot_bias == "SHORT" and dir_color == "bear")
        cot_strong   = abs(cot_pct) > 10
        no_event_risk = len(get_binary_risk(calendar_events, inst["key"], hours=4)) == 0

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
        nc_map   = NEWS_CONFIRMS_MAP.get(inst["key"], (None, None))
        if ns_label == "risk_on" and nc_map[0]:
            news_confirms_dir = (nc_map[0] == dir_color)
        elif ns_label == "risk_off" and nc_map[1]:
            news_confirms_dir = (nc_map[1] == dir_color)
        else:
            news_confirms_dir = False
        news_headwind = (
            (ns_label == "risk_on" and nc_map[0] and nc_map[0] != dir_color) or
            (ns_label == "risk_off" and nc_map[1] and nc_map[1] != dir_color)
        )
        inst_fund       = fund_data.get("instrument_scores", {}).get(inst["key"], {})
        inst_fund_score = inst_fund.get("score", 0)
        inst_fund_bias  = inst_fund.get("bias", "neutral")
        fund_confirms   = (inst_fund_score > 0.3 and dir_color == "bull") or \
                          (inst_fund_score < -0.3 and dir_color == "bear")
        score_details = [
            {"kryss": "Over SMA200 (D1 trend)",         "verdi": above_sma},
            {"kryss": "Momentum 20d bekrefter",          "verdi": (chg20 > 0 if dir_color == "bull" else chg20 < 0)},
            {"kryss": "COT bekrefter retning",           "verdi": cot_confirms},
            {"kryss": "COT sterk posisjonering (>10%)",  "verdi": cot_strong},
            {"kryss": "Pris VED HTF-nivå nå",            "verdi": at_level_now},
            {"kryss": "HTF-nivå D1/Ukentlig",            "verdi": htf_level_nearby},
            {"kryss": "D1 + 4H trend kongruent",         "verdi": align in ("bull","bear")},
            {"kryss": "Ingen event-risiko (4t)",          "verdi": no_event_risk},
            {"kryss": "Nyhetssentiment bekrefter",        "verdi": news_confirms_dir},
            {"kryss": "Fundamental bekrefter",            "verdi": fund_confirms},
            {"kryss": "BOS 1H/4H bekrefter retning",      "verdi": bos_confirms},
            {"kryss": "SMC 1H struktur bekrefter",         "verdi": smc_struct_confirms},
        ]
        score       = sum(1 for s in score_details if s["verdi"])
        max_score   = len(score_details)
        grade       = "A+" if score>=11 else "A" if score>=9 else "B" if score>=6 else "C"
        grade_color = "bull" if score>=11 else "warn" if score>=9 else "bear"

        if score >= 6 and cot_confirms and htf_level_nearby:
            timeframe_bias = "MAKRO"
        elif score >= 4 and htf_level_nearby:
            timeframe_bias = "SWING"
        elif score >= 2 and at_level_now and sesjon_aktiv:
            timeframe_bias = "SCALP"
        else:
            timeframe_bias = "WATCHLIST"

        vix_price = (prices.get("VIX") or {}).get("price", 20)
        pos_size  = "Full" if vix_price<20 else "Halv" if vix_price<30 else "Kvart"
        atr_for_setup = atr_15m if atr_15m else (atr_d * 0.4)
        setup_long  = _setup_to_dict(make_setup_l2l(curr, atr_for_setup, atr_d, tagged_sup, tagged_res, "long",  klasse))
        setup_short = _setup_to_dict(make_setup_l2l(curr, atr_for_setup, atr_d, tagged_sup, tagged_res, "short", klasse))
        for s in [setup_long, setup_short]:
            if s: s["session"] = inst["session"]
        active_setup = setup_long if dir_color == "bull" else setup_short
        t1_s = active_setup["t1"] if active_setup else None
        rr_s = active_setup["rr_t1"] if active_setup else None
        if t1_s is None:
            cands = [l for l in (tagged_res if dir_color == "bull" else tagged_sup)
                     if abs(l["price"] - curr) >= (atr_15m or atr_d * 0.4) * 1.5]
            pot = next((l for l in cands if l["weight"] >= 2), cands[0] if cands else None)
            t1_s = f"~{round(pot['price'], 5 if pot['price'] < 100 else 2)}" if pot else "-"
            rr_s = "-"
        atr_s = f"{atr_15m:.5f}" if atr_15m else "N/A"
        dir_tag, htf_tag = ("^" if dir_color == "bull" else "v"), (f"HTF:w{max(nearest_sup_w, nearest_res_w)}" if htf_level_nearby else "noHTF")
        log.info(f"  {inst['navn']:10s} {curr:.5f}  ATR15m={atr_s}  {grade}({score}/{max_score}) {dir_tag} {htf_tag}  T1:{t1_s}  R:R:{rr_s}")

        levels[inst["key"]] = {
            "name":          inst["navn"],
            "label":         inst["label"],
            "klasse":        klasse,
            "session":       inst["session"],
            "class":         inst["kat"][0].upper(),
            "current":       round(curr, 5 if curr<100 else 2),
            "atr14":         round(atr_15m, 5) if atr_15m else None,
            "atr_15m":       round(atr_15m, 5) if atr_15m else None,
            "atr_daily":     round(atr_d,   5) if atr_d   else None,
            "atr_4h":        round(atr_4h,  5) if atr_4h  else None,
            "at_level_now":  at_level_now,
            "status":        "aktiv" if at_level_now else "watchlist",
            "pdh": round(pdh,5) if pdh else None,
            "pdl": round(pdl,5) if pdl else None,
            "pdc": round(pdc,5) if pdc else None,
            "pwh": round(pwh,5) if pwh else None,
            "pwl": round(pwl,5) if pwl else None,
            "ema9_d1":       round(ema9_d,   5) if ema9_d   else None,
            "ema9_15m":      round(ema9_15m, 5) if ema9_15m else None,
            "ema9_above":    curr > ema9_d if ema9_d else None,
            "d1_regime":     d1_regime,
            "m15_regime":    m15_regime,
            "regime_align":  align,
            "session_now":   session_now,
            "sma200":        round(sma200, 4 if sma200<100 else 2),
            "sma200_pos":    "over" if above_sma else "under",
            "chg5d":         chg5,
            "chg20d":        chg20,
            "dir_color":     dir_color,
            "grade":         grade,
            "grade_color":   grade_color,
            "score":         score,
            "score_pct":     round(score/max_score*100),
            "score_details": score_details,
            "news_headwind": news_headwind,
            "news_sentiment_label": ns_label,
            "open_interest": oi,
            "resistances":   fmt_level(tagged_res, "R", atr_15m or atr_d, curr),
            "supports":      fmt_level(tagged_sup, "S", atr_15m or atr_d, curr),
            "setup_long":    setup_long,
            "setup_short":   setup_short,
            "binary_risk":   get_binary_risk(calendar_events, inst["key"]),
            "smc":    _smc_block(smc),
            "smc_1h": _smc_block(smc_1h),
            "smc_4h": _smc_block(smc_4h),
            "dxy_conf":      "medvind" if (inst["kat"]=="valuta" and (prices.get("DXY") or {}).get("chg5d",0)<0) else "motvind",
            "pos_size":      pos_size,
            "vix_spread_factor": 1.0 if vix_price<20 else 1.5 if vix_price<30 else 2.0,
            "cot":           {"bias": cot_bias, "color": cot_color, "net": spec_net,
                              "chg": cot_entry.get("change_spec_net",0), "pct": round(abs(cot_pct),1),
                              "momentum": cot_momentum,
                              "date": cot_entry.get("date",""), "report": cot_entry.get("report","")},
            "combined_bias":  "LONG" if dir_color=="bull" else "SHORT",
            "timeframe_bias": timeframe_bias,
            "sentiment":      {"fear_greed": fg},
            "fundamentals": {
                "score":      inst_fund_score,
                "bias":       inst_fund_bias,
                "confirms":   fund_confirms,
                "categories": {
                    cat: fund_data.get("category_scores", {}).get(cat, {})
                    for cat in ("econ_growth", "inflation", "jobs")
                },
                "indicators": fund_data.get("indicators", {}),
                "usd_bias":   fund_data.get("usd_fundamental", {}).get("bias", "neutral"),
                "updated":    fund_data.get("updated", ""),
            },
        }

    log.info("Henter makro-indikatorer (HYG, TIP, TNX, IRX, Kobber, EM)...")
    macro_ind = _fetch_macro()
    for k, v in macro_ind.items():
        if v: log.info(f"  {k}: {v['price']}  5d={v['chg5d']:+.2f}%")
        else: log.error(f"  {k}: FEIL")
    hyg, tip = macro_ind.get("HYG") or {}, macro_ind.get("TIP") or {}
    tnx, irx = macro_ind.get("TNX") or {}, macro_ind.get("IRX") or {}
    hy_chg5d, hy_stress = hyg.get("chg5d", 0), hyg.get("chg5d", 0) < -1.5
    tip_trend_5d = tip.get("chg5d", 0)
    yield_10y, yield_3m = tnx.get("price"), irx.get("price")
    yield_curve = round(yield_10y - yield_3m, 2) if (yield_10y and yield_3m) else None
    copper_5d = (macro_ind.get("Copper") or {}).get("chg5d", 0)
    em_5d = (macro_ind.get("EEM") or {}).get("chg5d", 0)
    vix_price   = (prices.get("VIX") or {}).get("price", 20)
    dxy_5d      = (prices.get("DXY") or {}).get("chg5d", 0)
    brent_p     = (prices.get("Brent") or {}).get("price", 80)
    fg_score    = fg["score"] if fg else 50
    cot_dxy     = cot_data.get("usd index",{})
    cot_dxy_net = ((cot_dxy.get("spekulanter") or {}).get("net",0) or 0)
    conflicts   = detect_conflict(vix_price, dxy_5d, fg, cot_dxy_net, hy_stress, yield_curve, news_sentiment)

    risk_off_signals = sum([vix_price > 25, hy_stress, (yield_curve or 0) < -0.3, (fg["score"] if fg else 50) < 35])
    if conflicts:
        smile_pos,usd_bias,usd_color,smile_desc = "konflikt","UKLAR","warn","Motstridende signaler: "+" | ".join(conflicts[:2])
    elif vix_price > 30 or risk_off_signals >= 2:
        smile_pos,usd_bias,usd_color,smile_desc = "venstre","STERKT","bull","Risk-off – USD trygg havn"
    elif vix_price < 18 and brent_p < 85 and not hy_stress:
        smile_pos,usd_bias,usd_color,smile_desc = "midten","SVAKT","bear","Goldilocks – svak USD"
    else:
        smile_pos,usd_bias,usd_color,smile_desc = "hoyre","MODERAT","bull","Vekst/inflasjon driver USD"

    if vix_price > 30:
        vix_regime = {"value":vix_price,"label":"Ekstrem frykt – KVART størrelse","color":"bear","regime":"extreme"}
    elif vix_price > 20:
        vix_regime = {"value":vix_price,"label":"Forhøyet – HALV størrelse","color":"warn","regime":"elevated"}
    else:
        vix_regime = {"value":vix_price,"label":"Normalt – full størrelse","color":"bull","regime":"normal"}

    # ── Build and write output ────────────────────────────────
    macro = {
        "date":    datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "cot_date": max((d.get("date","") for d in cot_data.values() if d.get("date")), default="ukjent"),
        "prices":  prices,
        "vix_regime": vix_regime,
        "sentiment": {"fear_greed": fg, "news": news_sentiment, "conflicts": conflicts},
        "dollar_smile": {
            "position":smile_pos,"usd_bias":usd_bias,"usd_color":usd_color,"desc":smile_desc,
            "conflicts": conflicts,
            "inputs": {
                "vix":          vix_price,
                "hy_stress":    hy_stress,
                "hy_chg5d":     hy_chg5d,
                "brent":        brent_p,
                "tip_trend_5d": tip_trend_5d,
                "dxy_trend_5d": dxy_5d,
                "yield_curve":  yield_curve,
                "yield_10y":    yield_10y,
                "yield_3m":     yield_3m,
                "copper_5d":    copper_5d,
                "em_5d":        em_5d,
            }
        },
        "macro_indicators": macro_ind,
        "trading_levels": levels,
        "calendar": calendar_events,
    }

    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(macro, f, ensure_ascii=False, indent=2)
    log.info(f"\nOK -> {OUT}  ({len(levels)} instruments)")
    if conflicts:
        log.info("Konflikter:")
        for c in conflicts:
            log.warning(f"  {c}")


if __name__ == "__main__":
    main()
