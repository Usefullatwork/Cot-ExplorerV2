#!/usr/bin/env python3
"""
comex.py - COMEX warehouse inventory scraper from CME Group.

Fetches registered/eligible inventory for Gold, Silver, and Copper
from CME's Warehouse Reports Service API.  Calculates a stress index
(0-100) based on registered-to-total ratio and trend.

No API key required.
Zero external dependencies - stdlib only.
"""

import json
import logging
import urllib.request
from datetime import datetime, timezone
from typing import Optional

log = logging.getLogger(__name__)

# CME WRS report IDs
REPORT_IDS: dict[str, int] = {
    "gold": 165,
    "silver": 166,
    "copper": 168,
}

BASE_URL = "https://www.cmegroup.com/CmeWS/mvc/WR/detail"


def _fetch_metal(metal: str, report_id: int, trade_date: str) -> Optional[dict]:
    """Fetch inventory for a single metal on a given trade date."""
    url = f"{BASE_URL}?reportId={report_id}&tradeDate={trade_date}"
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/120.0",
            "Accept": "application/json, text/plain, */*",
            "Referer": "https://www.cmegroup.com/",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            data = json.loads(r.read())
    except Exception as e:
        log.error(f"COMEX {metal} fetch ERROR: {e}")
        return None

    registered = 0
    eligible = 0

    # Parse rows: CME returns a list of facility rows with totals
    rows = data if isinstance(data, list) else data.get("facilityDetails", [])
    for row in rows:
        reg = row.get("registered", row.get("Registered", 0))
        elig = row.get("eligible", row.get("Eligible", 0))
        if isinstance(reg, str):
            reg = int(reg.replace(",", "") or "0")
        if isinstance(elig, str):
            elig = int(elig.replace(",", "") or "0")
        registered += int(reg)
        eligible += int(elig)

    total = registered + eligible
    coverage_pct = round((registered / total * 100) if total > 0 else 0.0, 2)

    return {
        "metal": metal,
        "registered": registered,
        "eligible": eligible,
        "total": total,
        "coverage_pct": coverage_pct,
    }


def _calc_stress_index(registered: int, total: int) -> float:
    """
    Calculate stress index 0-100.

    Base = (1.0 - registered/total) * 80
    Capped at 0-100 range.
    """
    if total <= 0:
        return 50.0
    ratio = registered / total
    base = (1.0 - ratio) * 80.0
    return round(min(max(base, 0.0), 100.0), 1)


def fetch() -> dict:
    """
    Fetch COMEX warehouse inventory for gold, silver, copper.

    Returns:
        Dict with keys: gold, silver, copper (each a metal dict),
        stress_index (float 0-100), and fetched_at (ISO string).
        Returns empty metals on error.
    """
    now = datetime.now(timezone.utc)
    trade_date = now.strftime("%Y%m%d")

    result: dict = {
        "gold": None,
        "silver": None,
        "copper": None,
        "stress_index": 0.0,
        "fetched_at": now.isoformat(),
    }

    total_registered = 0
    total_all = 0

    for metal, report_id in REPORT_IDS.items():
        metal_data = _fetch_metal(metal, report_id, trade_date)
        if metal_data:
            result[metal] = metal_data
            total_registered += metal_data["registered"]
            total_all += metal_data["total"]

    result["stress_index"] = _calc_stress_index(total_registered, total_all)
    log.info(f"COMEX: stress_index={result['stress_index']}")
    return result


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    data = fetch()
    for metal in ("gold", "silver", "copper"):
        m = data.get(metal)
        if m:
            log.info(f"  {metal}: reg={m['registered']:,} elig={m['eligible']:,} cov={m['coverage_pct']}%")
    log.info(f"  Stress index: {data['stress_index']}")
