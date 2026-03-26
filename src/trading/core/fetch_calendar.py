#!/usr/bin/env python3
"""
fetch_calendar.py - Economic calendar fetcher.

Fetches this week's High and Medium impact economic events from
ForexFactory's public JSON feed. Events are tagged with affected
instruments for binary risk filtering.

Output: data/prices/calendar_latest.json

Zero external dependencies - stdlib only.
"""

import logging
import urllib.request
import json
import os
from datetime import datetime, timezone, timedelta

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(_DIR, "..", "..", ".."))
DATA_DIR = os.path.join(PROJECT_ROOT, "data")
OUT = os.path.join(DATA_DIR, "prices", "calendar_latest.json")
os.makedirs(os.path.join(DATA_DIR, "prices"), exist_ok=True)

# ---------------------------------------------------------------------------
# Instrument mapping per currency
# ---------------------------------------------------------------------------
AFFECTED_INSTRUMENTS = {
    "USD": ["EURUSD", "USDJPY", "GBPUSD", "AUDUSD", "DXY", "SPX", "NAS100", "Gold", "WTI", "Brent"],
    "EUR": ["EURUSD"],
    "GBP": ["GBPUSD"],
    "JPY": ["USDJPY"],
    "AUD": ["AUDUSD"],
    "CAD": ["USDCAD"],
    "CHF": ["USDCHF"],
    "NZD": ["NZDUSD"],
}


def fetch_calendar():
    """Fetch and parse ForexFactory calendar data."""
    url = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            raw = json.loads(r.read())
    except Exception as e:
        log.error("Calendar fetch error: %s", e)
        return None

    now = datetime.now(timezone.utc)
    events = []
    for ev in raw:
        impact = ev.get("impact", "")
        if impact not in ("High", "Medium"):
            continue
        country = ev.get("country", "")
        title = ev.get("title", "")
        date_str = ev.get("date", "")
        try:
            dt = datetime.fromisoformat(date_str)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            dt_utc = dt.astimezone(timezone.utc)
        except (ValueError, TypeError):
            continue
        cet = dt_utc + timedelta(hours=1)
        events.append({
            "date": dt_utc.isoformat(),
            "cet": cet.strftime("%a %d.%m %H:%M"),
            "title": title,
            "country": country,
            "impact": impact,
            "forecast": ev.get("forecast", ""),
            "previous": ev.get("previous", ""),
            "actual": ev.get("actual", ""),
            "berorte": AFFECTED_INSTRUMENTS.get(country, []),
            "hours_away": round((dt_utc - now).total_seconds() / 3600, 1),
        })

    events.sort(key=lambda x: x["date"])
    return {"updated": now.isoformat(), "events": events}


def main():
    """Fetch calendar and save to disk."""
    result = fetch_calendar()
    if result is None:
        return

    events = result["events"]
    with open(OUT, "w") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    high_count = sum(1 for e in events if e["impact"] == "High")
    log.info("Saved %d events (%d High)", len(events), high_count)
    for e in events[:8]:
        log.info("  %-18s %-4s [%-6s] %s", e["cet"], e["country"], e["impact"], e["title"][:40])


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    main()
