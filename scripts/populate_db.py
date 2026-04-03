#!/usr/bin/env python3
"""Populate DB tables from external data sources.

Bridges the gap between JSON-file fetchers and DB-backed consumers
(backtesting DbDataLoader, Layer 2 VaR, correlation matrix).

Usage:
    python scripts/populate_db.py                # All: prices + COT + geointel
    python scripts/populate_db.py --prices       # PriceDaily only
    python scripts/populate_db.py --cot          # CotPosition only
    python scripts/populate_db.py --geointel     # Seismic + COMEX + Intel only
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Ensure project root is on sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.db.engine import init_db, session_ctx
from src.db.models import (
    ComexInventory,
    CotPosition,
    GeoIntelArticle,
    Instrument,
    PriceDaily,
    SeismicEvent,
)
from src.db import repository as repo

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

# ── Instrument definitions for seeding ────────────────────────────────────
# Combines keys from price_fetcher (frontend) and DbDataLoader (backtesting).
# Some instruments have two keys (e.g., Gold/XAUUSD, SPX/SPX500).
INSTRUMENT_DEFS: list[dict] = [
    # From price_fetcher.py INSTRUMENTS (frontend keys)
    {"key": "EURUSD", "name": "EUR/USD", "symbol": "EURUSD=X", "label": "Valuta", "category": "valuta", "class_": "A", "session": "London 08:00-12:00 CET"},
    {"key": "USDJPY", "name": "USD/JPY", "symbol": "JPY=X", "label": "Valuta", "category": "valuta", "class_": "A", "session": "London 08:00-12:00 CET"},
    {"key": "GBPUSD", "name": "GBP/USD", "symbol": "GBPUSD=X", "label": "Valuta", "category": "valuta", "class_": "A", "session": "London 08:00-12:00 CET"},
    {"key": "AUDUSD", "name": "AUD/USD", "symbol": "AUDUSD=X", "label": "Valuta", "category": "valuta", "class_": "A", "session": "London 08:00-12:00 CET"},
    {"key": "Gold", "name": "Gull", "symbol": "GC=F", "label": "Ravare", "category": "ravarer", "class_": "B", "session": "London Fix 10:30 / NY Fix 15:00 CET"},
    {"key": "Silver", "name": "Solv", "symbol": "SI=F", "label": "Ravare", "category": "ravarer", "class_": "B", "session": "London Fix 10:30 / NY Fix 15:00 CET"},
    {"key": "Brent", "name": "Brent", "symbol": "BZ=F", "label": "Ravare", "category": "ravarer", "class_": "B", "session": "London Fix 10:30 / NY Fix 15:00 CET"},
    {"key": "WTI", "name": "WTI", "symbol": "CL=F", "label": "Ravare", "category": "ravarer", "class_": "B", "session": "London Fix 10:30 / NY Fix 15:00 CET"},
    {"key": "SPX", "name": "S&P 500", "symbol": "^GSPC", "label": "Aksjer", "category": "aksjer", "class_": "C", "session": "NY Open 14:30-17:00 CET"},
    {"key": "NAS100", "name": "Nasdaq", "symbol": "^NDX", "label": "Aksjer", "category": "aksjer", "class_": "C", "session": "NY Open 14:30-17:00 CET"},
    {"key": "VIX", "name": "VIX", "symbol": "^VIX", "label": "Vol", "category": "aksjer", "class_": "C", "session": "NY Open 14:30-17:00 CET"},
    {"key": "DXY", "name": "DXY", "symbol": "DX-Y.NYB", "label": "Valuta", "category": "valuta", "class_": "A", "session": "London 08:00-12:00 CET"},
    # Extra frontend keys
    {"key": "HYG", "name": "High Yield", "symbol": "HYG", "label": "Rente", "category": "renter", "class_": "C", "session": "NY 14:30-21:00 CET"},
    {"key": "TIP", "name": "TIPS ETF", "symbol": "TIP", "label": "Rente", "category": "renter", "class_": "C", "session": "NY 14:30-21:00 CET"},
    # DbDataLoader broker-style aliases (for WFO backtesting)
    {"key": "XAUUSD", "name": "Gold (Broker)", "symbol": "GC=F", "label": "Ravare", "category": "ravarer", "class_": "B", "session": "London Fix 10:30 / NY Fix 15:00 CET"},
    {"key": "XAGUSD", "name": "Silver (Broker)", "symbol": "SI=F", "label": "Ravare", "category": "ravarer", "class_": "B", "session": "London Fix 10:30 / NY Fix 15:00 CET"},
    {"key": "USOIL", "name": "WTI (Broker)", "symbol": "CL=F", "label": "Ravare", "category": "ravarer", "class_": "B", "session": "London Fix 10:30 / NY Fix 15:00 CET"},
    {"key": "UKOIL", "name": "Brent (Broker)", "symbol": "BZ=F", "label": "Ravare", "category": "ravarer", "class_": "B", "session": "London Fix 10:30 / NY Fix 15:00 CET"},
    {"key": "SPX500", "name": "S&P 500 (Broker)", "symbol": "^GSPC", "label": "Aksjer", "category": "aksjer", "class_": "C", "session": "NY Open 14:30-17:00 CET"},
]


def ensure_instruments() -> int:
    """Seed the instruments table with all needed keys."""
    log.info("=== Seeding instruments table ===")
    count = 0
    with session_ctx() as session:
        for defn in INSTRUMENT_DEFS:
            existing = session.query(Instrument).filter_by(key=defn["key"]).first()
            if not existing:
                session.add(Instrument(
                    key=defn["key"],
                    name=defn["name"],
                    symbol=defn["symbol"],
                    label=defn["label"],
                    category=defn["category"],
                    class_=defn["class_"],
                    session=defn["session"],
                ))
                count += 1
    log.info("  Seeded %d new instruments (%d total defined)", count, len(INSTRUMENT_DEFS))
    return count


# ── Yahoo Finance: instrument_key -> yahoo_symbol ─────────────────────────
# Each yahoo symbol may be stored under multiple instrument keys (aliases).
# Format: (yahoo_symbol, [list of instrument keys to store under])
YAHOO_FETCHES: list[tuple[str, list[str]]] = [
    ("EURUSD=X", ["EURUSD"]),
    ("GBPUSD=X", ["GBPUSD"]),
    ("JPY=X", ["USDJPY"]),
    ("AUDUSD=X", ["AUDUSD"]),
    ("GC=F", ["Gold", "XAUUSD"]),
    ("SI=F", ["Silver", "XAGUSD"]),
    ("CL=F", ["WTI", "USOIL"]),
    ("BZ=F", ["Brent", "UKOIL"]),
    ("^GSPC", ["SPX", "SPX500"]),
    ("^NDX", ["NAS100"]),
    ("^VIX", ["VIX"]),
    ("DX-Y.NYB", ["DXY"]),
    ("HYG", ["HYG"]),
    ("TIP", ["TIP"]),
]

YAHOO_HEADERS = {"User-Agent": "Mozilla/5.0"}


def fetch_yahoo_ohlcv(yahoo_sym: str, range_: str = "1y") -> list[dict]:
    """Fetch daily OHLCV from Yahoo Finance v8 chart API."""
    url = (
        f"https://query1.finance.yahoo.com/v8/finance/chart/{yahoo_sym}"
        f"?interval=1d&range={range_}"
    )
    req = urllib.request.Request(url, headers=YAHOO_HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            data = json.loads(r.read())
    except Exception as exc:
        log.error("Yahoo fetch failed for %s: %s", yahoo_sym, exc)
        return []

    result = data.get("chart", {}).get("result", [])
    if not result:
        log.warning("Yahoo returned no data for %s", yahoo_sym)
        return []

    timestamps = result[0].get("timestamp", [])
    quote = result[0].get("indicators", {}).get("quote", [{}])[0]
    opens = quote.get("open", [])
    highs = quote.get("high", [])
    lows = quote.get("low", [])
    closes = quote.get("close", [])
    volumes = quote.get("volume", [])

    bars: list[dict] = []
    for i, ts in enumerate(timestamps):
        o = opens[i] if i < len(opens) else None
        h = highs[i] if i < len(highs) else None
        l_ = lows[i] if i < len(lows) else None
        c = closes[i] if i < len(closes) else None
        v = volumes[i] if i < len(volumes) else None

        if h is None or l_ is None or c is None:
            continue

        date_str = datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")
        bars.append({
            "date": date_str,
            "open": o,
            "high": h,
            "low": l_,
            "close": c,
            "volume": v,
            "source": "yahoo",
        })

    return bars


def populate_prices() -> dict[str, dict]:
    """Fetch OHLCV from Yahoo Finance for all instruments and write to PriceDaily."""
    log.info("=== Populating PriceDaily from Yahoo Finance ===")
    results: dict[str, dict] = {}

    for yahoo_sym, inst_keys in YAHOO_FETCHES:
        log.info("Fetching %s (keys: %s)...", yahoo_sym, ", ".join(inst_keys))
        bars = fetch_yahoo_ohlcv(yahoo_sym, range_="1y")

        if not bars:
            log.warning("  No data returned for %s", yahoo_sym)
            for k in inst_keys:
                results[k] = {"rows": 0, "error": "no data"}
            time.sleep(2)
            continue

        min_date = bars[0]["date"]
        max_date = bars[-1]["date"]

        with session_ctx() as session:
            for inst_key in inst_keys:
                count = 0
                for bar in bars:
                    repo.save_price_daily(
                        instrument=inst_key,
                        date=bar["date"],
                        ohlcv={
                            "open": bar["open"],
                            "high": bar["high"],
                            "low": bar["low"],
                            "close": bar["close"],
                            "volume": bar["volume"],
                            "source": bar["source"],
                        },
                        db=session,
                    )
                    count += 1
                log.info("  %s: %d rows (%s to %s)", inst_key, count, min_date, max_date)
                results[inst_key] = {"rows": count, "min": min_date, "max": max_date}

        # Rate limit: 2s between requests
        time.sleep(2)

    total = sum(r.get("rows", 0) for r in results.values())
    log.info("PriceDaily total: %d rows across %d keys", total, len(results))
    return results


def populate_cot() -> dict[str, int]:
    """Parse COT JSON files from data/cot/ and write to CotPosition."""
    log.info("=== Populating CotPosition from COT JSON ===")
    cot_dir = PROJECT_ROOT / "data" / "cot"

    # Try combined first, then individual report dirs
    combined_path = cot_dir / "combined" / "latest.json"
    report_dirs = ["tff", "legacy", "disaggregated", "supplemental"]

    all_records: list[dict] = []

    if combined_path.exists():
        log.info("Reading combined COT from %s", combined_path)
        with open(combined_path, encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            all_records = data
        elif isinstance(data, dict):
            # Might be keyed by market name
            for key, entries in data.items():
                if isinstance(entries, list):
                    all_records.extend(entries)
                elif isinstance(entries, dict):
                    all_records.append(entries)
    else:
        # Fall back to individual report directories
        for report_id in report_dirs:
            report_path = cot_dir / report_id / "latest.json"
            if not report_path.exists():
                continue
            log.info("Reading %s COT from %s", report_id, report_path)
            with open(report_path, encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                all_records.extend(data)

    if not all_records:
        log.warning("No COT data found. Run 'python fetch_cot.py --history' first.")
        return {}

    log.info("Parsing %d COT records...", len(all_records))
    counts: dict[str, int] = {}

    with session_ctx() as session:
        for rec in all_records:
            symbol = rec.get("symbol", "")
            market = rec.get("market", "")
            report_type = rec.get("report", "")
            date = rec.get("date", "")

            if not symbol or not date:
                continue

            # Extract speculator positions (varies by report type)
            spec = rec.get("spekulanter", {})
            comm = rec.get("kommersielle", rec.get("meglere", {}))
            nonrept = rec.get("smahandlere", {})

            cot_data = {
                "symbol": symbol,
                "market": market,
                "report_type": report_type,
                "date": date,
                "open_interest": rec.get("open_interest", 0),
                "change_oi": rec.get("change_oi", 0),
                "change_spec_net": rec.get("change_spec_net", 0),
                "spec_long": spec.get("long", 0),
                "spec_short": spec.get("short", 0),
                "spec_net": spec.get("net", 0),
                "comm_long": comm.get("long", 0),
                "comm_short": comm.get("short", 0),
                "comm_net": comm.get("net", 0),
                "nonrept_long": nonrept.get("long", 0),
                "nonrept_short": nonrept.get("short", 0),
                "nonrept_net": nonrept.get("net", 0),
                "category": rec.get("kategori", rec.get("category", "annet")),
            }

            repo.save_cot_position(cot_data, db=session)
            key = f"{report_type}:{symbol}"
            counts[key] = counts.get(key, 0) + 1

    total = sum(counts.values())
    unique_symbols = len({k.split(":")[1] for k in counts})
    log.info("CotPosition total: %d rows across %d symbols", total, unique_symbols)
    return counts


def populate_geointel() -> dict[str, int]:
    """Fetch seismic, COMEX, and intel data and write to DB."""
    log.info("=== Populating geointel tables ===")
    results: dict[str, int] = {}

    # --- Seismic events ---
    try:
        from src.trading.scrapers.seismic import fetch as fetch_seismic
        events = fetch_seismic()
        count = 0
        with session_ctx() as session:
            for ev in events:
                # Convert Unix ms timestamp to datetime
                raw_time = ev.get("time")
                if isinstance(raw_time, (int, float)):
                    event_dt = datetime.fromtimestamp(raw_time / 1000, tz=timezone.utc)
                else:
                    event_dt = datetime.now(timezone.utc)

                place = ev.get("place", "")
                existing = session.query(SeismicEvent).filter_by(
                    place=place,
                ).filter(
                    SeismicEvent.url == ev.get("url"),
                ).first()
                if not existing:
                    session.add(SeismicEvent(
                        mag=ev.get("mag"),
                        lat=ev.get("lat"),
                        lon=ev.get("lon"),
                        depth_km=ev.get("depth_km"),
                        place=place,
                        event_time=event_dt,
                        region=ev.get("region"),
                        url=ev.get("url"),
                        fetched_at=datetime.now(timezone.utc),
                    ))
                    count += 1
        results["seismic_events"] = count
        log.info("  SeismicEvent: %d new rows", count)
    except Exception as exc:
        log.error("  SeismicEvent failed: %s", exc)
        results["seismic_events"] = 0

    # --- COMEX inventory ---
    try:
        from src.trading.scrapers.comex import fetch as fetch_comex
        comex = fetch_comex()
        count = 0
        now = datetime.now(timezone.utc)
        with session_ctx() as session:
            for metal in ["gold", "silver", "copper"]:
                data = comex.get(metal)
                if not data:
                    continue
                session.add(ComexInventory(
                    metal=metal,
                    registered=data.get("registered", 0),
                    eligible=data.get("eligible", 0),
                    total=data.get("total", 0),
                    coverage_pct=data.get("coverage_pct", 0),
                    stress_index=data.get("stress_index", comex.get("stress_index", 0)),
                    fetched_at=now,
                ))
                count += 1
        results["comex_inventory"] = count
        log.info("  ComexInventory: %d rows", count)
    except Exception as exc:
        log.error("  ComexInventory failed: %s", exc)
        results["comex_inventory"] = 0

    # --- GeoIntel articles ---
    try:
        from src.trading.scrapers.intel_feed import fetch as fetch_intel
        articles = fetch_intel(max_per_category=10)
        count = 0
        now = datetime.now(timezone.utc)
        with session_ctx() as session:
            for art in articles:
                existing = session.query(GeoIntelArticle).filter_by(
                    url=art.get("url"),
                    category=art.get("category"),
                ).first()
                if not existing:
                    session.add(GeoIntelArticle(
                        title=art.get("title", ""),
                        url=art.get("url", ""),
                        source=art.get("source", ""),
                        published_at=art.get("time", ""),
                        category=art.get("category", ""),
                        fetched_at=now,
                    ))
                    count += 1
        results["geointel_articles"] = count
        log.info("  GeoIntelArticle: %d new rows", count)
    except Exception as exc:
        log.error("  GeoIntelArticle failed: %s", exc)
        results["geointel_articles"] = 0

    return results


def verify_data() -> None:
    """Print row counts for all populated tables."""
    log.info("=== Data Verification ===")
    with session_ctx() as session:
        for model in [PriceDaily, CotPosition, SeismicEvent, ComexInventory, GeoIntelArticle]:
            count = session.query(model).count()
            log.info("  %-20s %d rows", model.__tablename__ + ":", count)

        # Per-instrument price coverage
        from sqlalchemy import func, select
        stmt = (
            select(
                PriceDaily.instrument,
                func.count(PriceDaily.id),
                func.min(PriceDaily.date),
                func.max(PriceDaily.date),
            )
            .group_by(PriceDaily.instrument)
            .order_by(PriceDaily.instrument)
        )
        rows = session.execute(stmt).all()
        if rows:
            log.info("  --- PriceDaily per instrument ---")
            for inst, cnt, min_d, max_d in rows:
                log.info("    %-10s %4d rows  %s to %s", inst, cnt, min_d, max_d)


def main() -> None:
    parser = argparse.ArgumentParser(description="Populate CotV2 database tables")
    parser.add_argument("--prices", action="store_true", help="Populate PriceDaily only")
    parser.add_argument("--cot", action="store_true", help="Populate CotPosition only")
    parser.add_argument("--geointel", action="store_true", help="Populate geointel tables only")
    args = parser.parse_args()

    # Ensure DB tables exist and instruments are seeded
    init_db()
    ensure_instruments()

    run_all = not (args.prices or args.cot or args.geointel)

    if run_all or args.prices:
        populate_prices()

    if run_all or args.cot:
        populate_cot()

    if run_all or args.geointel:
        populate_geointel()

    verify_data()
    log.info("Done.")


if __name__ == "__main__":
    main()
