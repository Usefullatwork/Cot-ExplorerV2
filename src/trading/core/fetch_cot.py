#!/usr/bin/env python3
"""
fetch_cot.py - CFTC Commitments of Traders data fetcher.

Downloads and parses weekly COT reports from CFTC.gov (public domain data).
Supports TFF, Legacy, Disaggregated, and Supplemental report types.

Reports are saved as JSON to data/cot/ with both dated and latest versions.
Pass --history to also fetch historical data back to each report's start year.

Usage:
    python fetch_cot.py             # Fetch current week only
    python fetch_cot.py --history   # Fetch current + all historical data
"""

import logging
import urllib.request
import zipfile
import csv
import json
import os
import sys
import shutil
from datetime import datetime

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Paths - relative to project root (two levels up from this file)
# ---------------------------------------------------------------------------
_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(_DIR, "..", "..", ".."))
DATA_DIR = os.path.join(PROJECT_ROOT, "data")

# ---------------------------------------------------------------------------
# HTTP opener with browser user-agent (CFTC blocks default Python UA)
# ---------------------------------------------------------------------------
opener = urllib.request.build_opener()
opener.addheaders = [("User-Agent", "Mozilla/5.0")]
urllib.request.install_opener(opener)

# ---------------------------------------------------------------------------
# Report definitions
# ---------------------------------------------------------------------------
YEAR = datetime.now().year
BASE_URL = "https://www.cftc.gov/files/dea/history"

REPORTS = [
    {
        "id": "tff",
        "url": f"{BASE_URL}/fut_fin_txt_{YEAR}.zip",
        "hist_from": 2009,
        "hist_pat": f"{BASE_URL}/fut_fin_txt_YYYY.zip",
    },
    {
        "id": "legacy",
        "url": f"{BASE_URL}/com_disagg_txt_{YEAR}.zip",
        "hist_from": 2010,
        "hist_pat": f"{BASE_URL}/com_disagg_txt_YYYY.zip",
    },
    {
        "id": "disaggregated",
        "url": f"{BASE_URL}/fut_disagg_txt_{YEAR}.zip",
        "hist_from": 2009,
        "hist_pat": f"{BASE_URL}/fut_disagg_txt_YYYY.zip",
    },
    {
        "id": "supplemental",
        "url": f"{BASE_URL}/dea_cit_txt_{YEAR}.zip",
        "hist_from": 2006,
        "hist_pat": f"{BASE_URL}/dea_cit_txt_YYYY.zip",
    },
]

# ---------------------------------------------------------------------------
# Category classification keywords
# ---------------------------------------------------------------------------
CATEGORIES = {
    "aksjer":      ["s&p", "nasdaq", "russell", "nikkei", "msci", "vix", "topix", "dow"],
    "valuta":      ["euro fx", "japanese yen", "british pound", "swiss franc",
                    "canadian dollar", "australian dollar", "nz dollar",
                    "mexican peso", "so african rand", "usd index", "brazilian real"],
    "renter":      ["ust", "sofr", "eurodollar", "treasury", "t-note", "t-bond",
                    "swap", "eris", "federal fund"],
    "ravarer":     ["crude oil", "natural gas", "gasoline", "heating oil",
                    "gold", "silver", "copper", "platinum", "palladium",
                    "lumber", "wti", "brent", "rbob"],
    "krypto":      ["bitcoin", "ether", "solana", "xrp", "cardano",
                    "polkadot", "litecoin", "nano", "zcash", "sui", "doge"],
    "landbruk":    ["corn", "wheat", "soybean", "coffee", "sugar", "cocoa",
                    "cotton", "cattle", "hogs", "lean", "live", "feeder",
                    "oats", "rice", "milk", "butter", "orange juice", "canola"],
    "volatilitet": ["vix"],
}

# ---------------------------------------------------------------------------
# Norwegian market name mapping
# ---------------------------------------------------------------------------
MARKET_NO = {
    "S&P 500 Consolidated":    {"no": "S&P 500",             "info": "De 500 storste selskapene i USA."},
    "Nasdaq":                   {"no": "Nasdaq 100",           "info": "Teknologiindeks. Apple, Microsoft, Nvidia m.fl."},
    "Nasdaq Mini":              {"no": "Nasdaq Mini",          "info": "Mindre Nasdaq-kontrakt."},
    "Russell E":                {"no": "Russell 2000",         "info": "2000 mindre amerikanske selskaper."},
    "Msci Eafe":                {"no": "MSCI Europa/Asia",     "info": "Aksjer utenfor USA: Europa, Japan, Australia."},
    "Msci Em Index":            {"no": "MSCI Fremvoksende",    "info": "Kina, India, Brasil og andre vekstmarkeder."},
    "Nikkei Stock Average":     {"no": "Nikkei (Japan)",       "info": "225 storste selskaper pa Tokyo-borsen."},
    "Vix Futures":              {"no": "VIX - Fryktindeks",    "info": "Hoy verdi = mye usikkerhet i markedet."},
    "Euro Fx":                  {"no": "Euro (EUR/USD)",       "info": "Verdens mest handlede valutapar."},
    "Japanese Yen":             {"no": "Japansk Yen",          "info": "Trygg-havn-valuta i urolige tider."},
    "British Pound":            {"no": "Britisk Pund",         "info": "Pavirkes av Bank of England."},
    "Swiss Franc":              {"no": "Sveitsisk Franc",      "info": "En av de sikreste valutaene i verden."},
    "Canadian Dollar":          {"no": "Kanadisk Dollar",      "info": "Tett knyttet til oljeprisen."},
    "Australian Dollar":        {"no": "Australsk Dollar",     "info": "Ravarevaluta - folger kobber og jernmalm."},
    "Nz Dollar":                {"no": "New Zealand Dollar",   "info": "Barometer for global risikoappetitt."},
    "So African Rand":          {"no": "Sorafrikansk Rand",    "info": "Volatil valuta fra fremvoksende marked."},
    "Usd Index":                {"no": "Dollarindeks (DXY)",   "info": "Styrken til USD mot 6 valutaer."},
    "Ust 2Y Note":              {"no": "USA 2-arig rente",     "info": "Sensitiv for hva sentralbanken (Fed) gjor."},
    "Ust 5Y Note":              {"no": "USA 5-arig rente",     "info": "Mellomlang amerikansk statsrente."},
    "Ust 10Y Note":             {"no": "USA 10-arig rente",    "info": "Viktigste globale rente. Pavirker boliglan verden over."},
    "Ust Bond":                 {"no": "USA 30-arig rente",    "info": "Langsiktig rente for pensjonsfond."},
    "Sofr":                     {"no": "SOFR (dagslansrente)", "info": "Hva banker betaler for korte dollarlan."},
    "Bitcoin":                  {"no": "Bitcoin (BTC)",        "info": "Verdens storste kryptovaluta."},
    "Nano Bitcoin":             {"no": "Bitcoin Mini",         "info": "Mindre Bitcoin-kontrakt (1/100 BTC)."},
    "Nano Bitcoin Perp Style":  {"no": "Bitcoin Mini Perp",    "info": "Bitcoin uten utlopsdato."},
    "Nano Ether":               {"no": "Ethereum Mini",        "info": "Ethereum - plattform for smarte kontrakter."},
    "Nano Ether Perp Style":    {"no": "Ethereum Mini Perp",   "info": "Ethereum uten utlopsdato."},
    "Nano Solana":              {"no": "Solana Mini",          "info": "Solana - rask og billig blokkjede."},
    "Nano Solana Perp Style":   {"no": "Solana Mini Perp",     "info": "Solana uten utlopsdato."},
    "Nano Xrp":                 {"no": "XRP Mini",             "info": "XRP - brukes til internasjonal betaling."},
    "Sol":                      {"no": "Solana (SOL)",         "info": "Solana kryptovaluta."},
    "Xrp":                      {"no": "XRP",                  "info": "XRP kryptovaluta."},
    "Crude Oil, Light Sweet":   {"no": "Raolje (WTI)",         "info": "Amerikansk raolje. Global prisreferanse."},
    "Natural Gas":              {"no": "Naturgass",            "info": "Energiravare for strom og oppvarming."},
    "Gold":                     {"no": "Gull",                 "info": "Trygg havn. Handles globalt som verdilager."},
    "Silver":                   {"no": "Solv",                 "info": "Brukes som investering og i industri."},
    "Copper-Grade #1":          {"no": "Kobber",               "info": "Industrimetall. Hoy ettersporsler = sterk okonomi."},
    "Corn":                     {"no": "Mais",                 "info": "Viktigste kornavling i USA."},
    "Soybeans":                 {"no": "Soyabonner",           "info": "Verdens nest viktigste kornavling."},
    "Wheat-Srw":                {"no": "Hvete",                "info": "Brukes til brod og pasta."},
    "Coffee C":                 {"no": "Kaffe (Arabica)",      "info": "Arabica-kaffe handles pa New York-borsen."},
    "Sugar No. 11":             {"no": "Sukker",               "info": "Rasukker. Viktig for mat og drivstoff."},
    "Cotton No. 2":             {"no": "Bomull",               "info": "Viktigste naturlige tekstilfiber."},
    "Lean Hogs":                {"no": "Svinekjott",           "info": "Futures pa mager svinekjott."},
    "Live Cattle":              {"no": "Storfe",               "info": "Futures pa levende storfe klar for slakt."},
}


def safe_int(val):
    """Safely convert a value to int, handling commas and decimals."""
    try:
        return int(str(val).strip().replace(",", "").split(".")[0])
    except (ValueError, TypeError, AttributeError):
        return 0


def get_category(name):
    """Classify a market name into a category based on keywords."""
    nl = name.lower()
    for cat, keywords in CATEGORIES.items():
        for kw in keywords:
            if kw in nl:
                return cat
    return "annet"


def download_and_extract(url, tmp_dir):
    """Download a ZIP file and extract the CSV within it."""
    zip_path = os.path.join(tmp_dir, "cot.zip")
    try:
        urllib.request.urlretrieve(url, zip_path)
        with zipfile.ZipFile(zip_path, "r") as z:
            z.extractall(tmp_dir)
        for f in os.listdir(tmp_dir):
            if f.endswith(".txt") and f != "cot.zip":
                return os.path.join(tmp_dir, f)
    except Exception as e:
        log.error("Download/extract error: %s", e)
    return None


def parse_file(csv_file, report_id, keep_all=False):
    """Parse a CFTC CSV file into structured market data."""
    results = {}
    try:
        with open(csv_file, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                name = row.get("Market_and_Exchange_Names", "").strip()
                date = row.get("Report_Date_as_YYYY-MM-DD", "").strip()
                sym = row.get("CFTC_Contract_Market_Code", "").strip()
                mkt = name.split("-")[0].strip().title()
                oi = safe_int(row.get("Open_Interest_All", 0))
                chg = safe_int(row.get("Change_in_Open_Interest_All", 0))

                if report_id == "tff":
                    sl = safe_int(row.get("Lev_Money_Positions_Long_All", 0))
                    ss = safe_int(row.get("Lev_Money_Positions_Short_All", 0))
                    il = safe_int(row.get("Asset_Mgr_Positions_Long_All", 0))
                    is_ = safe_int(row.get("Asset_Mgr_Positions_Short_All", 0))
                    dl = safe_int(row.get("Dealer_Positions_Long_All", 0))
                    ds = safe_int(row.get("Dealer_Positions_Short_All", 0))
                    nl = safe_int(row.get("NonRept_Positions_Long_All", 0))
                    ns = safe_int(row.get("NonRept_Positions_Short_All", 0))
                    cs = (safe_int(row.get("Change_in_Lev_Money_Long_All", 0))
                          - safe_int(row.get("Change_in_Lev_Money_Short_All", 0)))
                    entry = {
                        "date": date, "market": mkt, "symbol": sym,
                        "report": "tff", "open_interest": oi,
                        "change_oi": chg, "change_spec_net": cs,
                        "spekulanter": {"long": sl, "short": ss, "net": sl - ss, "label": "Hedge Funds"},
                        "institusjoner": {"long": il, "short": is_, "net": il - is_, "label": "Pensjonsfond"},
                        "meglere": {"long": dl, "short": ds, "net": dl - ds, "label": "Banker/Meglere"},
                        "smahandlere": {"long": nl, "short": ns, "net": nl - ns, "label": "Smahandlere"},
                    }
                elif report_id == "legacy":
                    sl = safe_int(row.get("NonComm_Positions_Long_All", 0))
                    ss = safe_int(row.get("NonComm_Positions_Short_All", 0))
                    cl = safe_int(row.get("Comm_Positions_Long_All", 0))
                    cs_ = safe_int(row.get("Comm_Positions_Short_All", 0))
                    nl = safe_int(row.get("NonRept_Positions_Long_All", 0))
                    ns = safe_int(row.get("NonRept_Positions_Short_All", 0))
                    cs = (safe_int(row.get("Change_in_NonComm_Long_All", 0))
                          - safe_int(row.get("Change_in_NonComm_Short_All", 0)))
                    entry = {
                        "date": date, "market": mkt, "symbol": sym,
                        "report": "legacy", "open_interest": oi,
                        "change_oi": chg, "change_spec_net": cs,
                        "spekulanter": {"long": sl, "short": ss, "net": sl - ss, "label": "Store Spekulanter"},
                        "kommersielle": {"long": cl, "short": cs_, "net": cl - cs_, "label": "Produsenter/Hedgers"},
                        "smahandlere": {"long": nl, "short": ns, "net": nl - ns, "label": "Smahandlere"},
                    }
                elif report_id == "disaggregated":
                    sl = safe_int(row.get("M_Money_Positions_Long_All", 0))
                    ss = safe_int(row.get("M_Money_Positions_Short_All", 0))
                    pl = safe_int(row.get("Prod_Merc_Positions_Long_All", 0))
                    ps = safe_int(row.get("Prod_Merc_Positions_Short_All", 0))
                    nl = safe_int(row.get("NonRept_Positions_Long_All", 0))
                    ns = safe_int(row.get("NonRept_Positions_Short_All", 0))
                    cs = (safe_int(row.get("Change_in_M_Money_Long_All", 0))
                          - safe_int(row.get("Change_in_M_Money_Short_All", 0)))
                    entry = {
                        "date": date, "market": mkt, "symbol": sym,
                        "report": "disaggregated", "open_interest": oi,
                        "change_oi": chg, "change_spec_net": cs,
                        "spekulanter": {"long": sl, "short": ss, "net": sl - ss, "label": "Managed Money"},
                        "produsenter": {"long": pl, "short": ps, "net": pl - ps, "label": "Produsenter"},
                        "smahandlere": {"long": nl, "short": ns, "net": nl - ns, "label": "Smahandlere"},
                    }
                elif report_id == "supplemental":
                    sl = safe_int(row.get("NonComm_Positions_Long_All", 0))
                    ss = safe_int(row.get("NonComm_Positions_Short_All", 0))
                    cl = safe_int(row.get("Comm_Positions_Long_All", 0))
                    cs_ = safe_int(row.get("Comm_Positions_Short_All", 0))
                    il = safe_int(row.get("Index_Positions_Long_All", 0))
                    is_ = safe_int(row.get("Index_Positions_Short_All", 0))
                    nl = safe_int(row.get("NonRept_Positions_Long_All", 0))
                    ns = safe_int(row.get("NonRept_Positions_Short_All", 0))
                    cs = (safe_int(row.get("Change_in_NonComm_Long_All", 0))
                          - safe_int(row.get("Change_in_NonComm_Short_All", 0)))
                    entry = {
                        "date": date, "market": mkt, "symbol": sym,
                        "report": "supplemental", "open_interest": oi,
                        "change_oi": chg, "change_spec_net": cs,
                        "spekulanter": {"long": sl, "short": ss, "net": sl - ss, "label": "Store Spekulanter"},
                        "kommersielle": {"long": cl, "short": cs_, "net": cl - cs_, "label": "Produsenter/Hedgers"},
                        "indeksfond": {"long": il, "short": is_, "net": il - is_, "label": "Indeksfond"},
                        "smahandlere": {"long": nl, "short": ns, "net": nl - ns, "label": "Smahandlere"},
                    }
                else:
                    continue

                entry["kategori"] = get_category(name)
                info = MARKET_NO.get(mkt, {})
                entry["navn_no"] = info.get("no", mkt)
                entry["forklaring"] = info.get("info", "")

                if keep_all:
                    if sym not in results:
                        results[sym] = []
                    results[sym].append(entry)
                else:
                    if mkt not in results or date > results[mkt]["date"]:
                        results[mkt] = entry
    except Exception as e:
        log.error("Parse error: %s", e)

    if keep_all:
        out = []
        for entries in results.values():
            out.extend(entries)
        return out
    return list(results.values())


def save(path, data):
    """Save data as JSON to the given path, creating directories as needed."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def process_report(report, year=None, keep_all=False):
    """Download, extract, and parse a single COT report."""
    url = report["url"] if year is None else report["hist_pat"].replace("YYYY", str(year))
    rid = report["id"]
    yr = year or YEAR
    log.info("Loading %s %s...", rid, yr)
    tmp = os.path.join(DATA_DIR, f"_tmp_cot_{rid}_{yr}")
    os.makedirs(tmp, exist_ok=True)
    csv_file = download_and_extract(url, tmp)
    if not csv_file:
        return []
    data = parse_file(csv_file, rid, keep_all=keep_all)
    shutil.rmtree(tmp, ignore_errors=True)
    log.info("%d markets", len(data))
    return data


def main():
    """Main entry point - fetch and save COT data."""
    do_history = "--history" in sys.argv
    today = datetime.now().strftime("%Y-%m-%d")
    log.info("COT Explorer - Data Download")
    log.info("=" * 40)

    all_current = []
    for report in REPORTS:
        log.info("[%s]", report["id"].upper())
        data = process_report(report)
        if data:
            save(os.path.join(DATA_DIR, "cot", report["id"], "latest.json"), data)
            save(os.path.join(DATA_DIR, "cot", report["id"], f"{today}.json"), data)
            all_current.extend(data)

    # Build deduplicated combined file
    seen = set()
    combined = []
    for d in all_current:
        key = d["symbol"] + d["report"]
        if key not in seen:
            seen.add(key)
            combined.append(d)
    combined.sort(key=lambda x: (x["kategori"], x["navn_no"]))
    save(os.path.join(DATA_DIR, "cot", "combined", "latest.json"), combined)
    save(os.path.join(DATA_DIR, "cot", "combined", f"{today}.json"), combined)
    log.info("Combined: %d markets -> data/cot/combined/latest.json", len(combined))

    if do_history:
        log.info("[HISTORICAL DATA]")
        for report in REPORTS:
            for yr in range(report["hist_from"], YEAR):
                data = process_report(report, yr, keep_all=True)
                if data:
                    save(os.path.join(DATA_DIR, "cot", "history", report["id"], f"{yr}.json"), data)
        log.info("Historical data saved to data/cot/history/")

    log.info("Done!")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    main()
