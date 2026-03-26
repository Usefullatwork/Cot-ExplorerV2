#!/usr/bin/env python3
"""
smc.py - Smart Money Concepts (SMC) analysis engine.

Python port of FluidTrades SMC Lite (Pine Script -> Python).
Calculates: Swing H/L, HH/LH/HL/LL, Supply/Demand zones, POI, BOS.

All functions are pure stdlib Python - zero external dependencies.

Usage:
    from smc import run_smc
    result = run_smc(rows, swing_length=5)
    # rows = list of (high, low, close) tuples
"""

import logging

log = logging.getLogger(__name__)


def calc_atr(rows: list[tuple[float, float, float]], n: int = 50) -> float | None:
    """Calculate Average True Range over n periods."""
    if len(rows) < n + 1:
        return None
    trs = [
        max(
            rows[i][0] - rows[i][1],
            abs(rows[i][0] - rows[i - 1][2]),
            abs(rows[i][1] - rows[i - 1][2]),
        )
        for i in range(1, len(rows))
    ]
    return sum(trs[-n:]) / n


def find_pivot_highs(rows: list[tuple[float, float, float]], length: int = 10) -> list[tuple[int, float]]:
    """
    Find pivot highs: high[i] is the highest of all highs in window [i-length : i+length].
    Returns list of (index, value).
    """
    pivots = []
    for i in range(length, len(rows) - length):
        window = [rows[j][0] for j in range(i - length, i + length + 1)]
        if rows[i][0] == max(window):
            pivots.append((i, rows[i][0]))
    return pivots


def find_pivot_lows(rows: list[tuple[float, float, float]], length: int = 10) -> list[tuple[int, float]]:
    """
    Find pivot lows: low[i] is the lowest of all lows in window [i-length : i+length].
    Returns list of (index, value).
    """
    pivots = []
    for i in range(length, len(rows) - length):
        window = [rows[j][1] for j in range(i - length, i + length + 1)]
        if rows[i][1] == min(window):
            pivots.append((i, rows[i][1]))
    return pivots


def classify_swings(pivots: list[tuple[int, float]], swing_type: str) -> list[tuple[int, float, str]]:
    """
    Classify swing points as HH/LH (for highs) or HL/LL (for lows).
    swing_type: 'high' or 'low'
    Returns list of (index, value, label).
    """
    result = []
    for i, (idx, val) in enumerate(pivots):
        if i == 0:
            result.append((idx, val, "HH" if swing_type == "high" else "HL"))
            continue
        prev_val = pivots[i - 1][1]
        if swing_type == "high":
            label = "HH" if val >= prev_val else "LH"
        else:
            label = "HL" if val >= prev_val else "LL"
        result.append((idx, val, label))
    return result


def build_supply_demand_zones(
    pivot_highs: list[tuple[int, float]],
    pivot_lows: list[tuple[int, float]],
    rows: list[tuple[float, float, float]],
    atr: float,
    box_width: float = 2.5,
    history: int = 20,
) -> tuple[list[dict], list[dict]]:
    """
    Build supply/demand zones from pivot highs/lows.
    Supply: at pivot high - top = high, bottom = high - atr_buffer
    Demand: at pivot low  - bottom = low, top = low + atr_buffer
    Non-overlapping: skip if new POI is within 2xATR of existing zone.
    Returns (supply_zones, demand_zones).
    """
    atr_buffer = atr * (box_width / 10)
    atr_overlap = atr * 2

    supply_zones = []
    demand_zones = []

    def overlapping(new_poi: float, zones: list[dict]) -> bool:
        for z in zones:
            if abs(new_poi - z["poi"]) <= atr_overlap:
                return True
        return False

    for idx, val in pivot_highs[-history:]:
        top = val
        bottom = val - atr_buffer
        poi = (top + bottom) / 2
        if not overlapping(poi, supply_zones):
            supply_zones.append(
                {
                    "top": round(top, 5),
                    "bottom": round(bottom, 5),
                    "poi": round(poi, 5),
                    "idx": idx,
                    "type": "supply",
                    "status": "intakt",
                }
            )

    for idx, val in pivot_lows[-history:]:
        bottom = val
        top = val + atr_buffer
        poi = (top + bottom) / 2
        if not overlapping(poi, demand_zones):
            demand_zones.append(
                {
                    "top": round(top, 5),
                    "bottom": round(bottom, 5),
                    "poi": round(poi, 5),
                    "idx": idx,
                    "type": "demand",
                    "status": "intakt",
                }
            )

    return supply_zones, demand_zones


def detect_bos(
    supply_zones: list[dict],
    demand_zones: list[dict],
    rows: list[tuple[float, float, float]],
) -> tuple[list[dict], list[dict], list[dict]]:
    """
    Break of Structure: when close breaks through a zone, it becomes a BOS line.
    Supply BOS: close >= top (broken upward)
    Demand BOS: close <= bottom (broken downward)
    Returns (supply_zones, demand_zones, bos_levels).
    """
    bos_levels = []

    for z in supply_zones:
        for i in range(z["idx"] + 1, len(rows)):
            if rows[i][2] >= z["top"]:
                z["status"] = "bos_brutt"
                bos_levels.append(
                    {
                        "level": z["poi"],
                        "type": "BOS_opp",
                        "idx": i,
                        "zone_top": z["top"],
                        "zone_bot": z["bottom"],
                    }
                )
                break

    for z in demand_zones:
        for i in range(z["idx"] + 1, len(rows)):
            if rows[i][2] <= z["bottom"]:
                z["status"] = "bos_brutt"
                bos_levels.append(
                    {
                        "level": z["poi"],
                        "type": "BOS_ned",
                        "idx": i,
                        "zone_top": z["top"],
                        "zone_bot": z["bottom"],
                    }
                )
                break

    return supply_zones, demand_zones, bos_levels


def determine_structure(
    swing_highs_classified: list[tuple[int, float, str]],
    swing_lows_classified: list[tuple[int, float, str]],
) -> str:
    """
    Overall structure based on last swing labels:
    - Bullish: HH + HL
    - Bearish: LL + LH
    - Mixed: anything else
    """
    last_high_label = swing_highs_classified[-1][2] if swing_highs_classified else None
    last_low_label = swing_lows_classified[-1][2] if swing_lows_classified else None

    if last_high_label == "HH" and last_low_label == "HL":
        return "BULLISH"
    elif last_high_label == "LH" and last_low_label == "LL":
        return "BEARISH"
    elif last_high_label == "HH":
        return "BULLISH_SVAK"
    elif last_low_label == "LL":
        return "BEARISH_SVAK"
    else:
        return "MIXED"


def filter_relevant_zones(
    supply_zones: list[dict],
    demand_zones: list[dict],
    bos_levels: list[dict],
    curr: float,
    atr: float,
    max_dist: int = 8,
) -> tuple[list[dict], list[dict], list[dict]]:
    """
    Filter to relevant zones:
    - Only intact zones (not broken)
    - Within max_dist x ATR from current price
    - Nearest supply above price, nearest demand below price
    """
    relevant_supply = [
        z
        for z in supply_zones
        if z["status"] == "intakt" and z["bottom"] > curr and abs(z["poi"] - curr) <= atr * max_dist
    ]

    relevant_demand = [
        z
        for z in demand_zones
        if z["status"] == "intakt" and z["top"] < curr and abs(z["poi"] - curr) <= atr * max_dist
    ]

    relevant_supply.sort(key=lambda z: abs(z["poi"] - curr))
    relevant_demand.sort(key=lambda z: abs(z["poi"] - curr))

    recent_bos = sorted(bos_levels, key=lambda b: b["idx"], reverse=True)[:3]

    return relevant_supply[:4], relevant_demand[:4], recent_bos


def run_smc(rows: list[tuple[float, float, float]], swing_length: int = 10, box_width: float = 2.5) -> dict | None:
    """
    Main function - run full SMC analysis on a list of (high, low, close) rows.
    Returns dict with all SMC data, or None if insufficient data.
    """
    if len(rows) < swing_length * 2 + 5:
        return None

    curr = rows[-1][2]
    atr = calc_atr(rows, 50) or calc_atr(rows, 20)
    if not atr:
        return None

    ph = find_pivot_highs(rows, swing_length)
    pl = find_pivot_lows(rows, swing_length)

    if not ph or not pl:
        return None

    swing_highs = classify_swings(ph, "high")
    swing_lows = classify_swings(pl, "low")

    supply, demand = build_supply_demand_zones(ph, pl, rows, atr, box_width)
    supply, demand, bos = detect_bos(supply, demand, rows)
    structure = determine_structure(swing_highs, swing_lows)

    rel_supply, rel_demand, recent_bos = filter_relevant_zones(supply, demand, bos, curr, atr, max_dist=15)

    return {
        "structure": structure,
        "atr": round(atr, 5),
        "supply_zones": rel_supply,
        "demand_zones": rel_demand,
        "bos_levels": recent_bos,
        "last_swing_high": {
            "value": round(swing_highs[-1][1], 5),
            "label": swing_highs[-1][2],
        }
        if swing_highs
        else None,
        "last_swing_low": {
            "value": round(swing_lows[-1][1], 5),
            "label": swing_lows[-1][2],
        }
        if swing_lows
        else None,
    }


if __name__ == "__main__":
    import json
    import urllib.parse
    import urllib.request

    def fetch(symbol: str, interval: str = "15m", range_: str = "5d") -> list[tuple[float, float, float]]:
        url = (
            f"https://query1.finance.yahoo.com/v8/finance/chart/"
            f"{urllib.parse.quote(symbol)}?interval={interval}&range={range_}"
        )
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as r:
            d = json.loads(r.read())
        q = d["chart"]["result"][0]["indicators"]["quote"][0]
        return [(h, lo, c) for h, lo, c in zip(q["high"], q["low"], q["close"]) if h and lo and c]

    logging.basicConfig(level=logging.DEBUG, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    for sym, name in [("EURUSD=X", "EUR/USD"), ("GC=F", "Gold"), ("CL=F", "WTI")]:
        log.debug("\n%s", "=" * 50)
        log.debug("%s - 15m SMC", name)
        rows = fetch(sym)
        if not rows:
            log.debug("  No data")
            continue
        result = run_smc(rows, swing_length=5)
        if not result:
            log.debug("  Insufficient data")
            continue
        curr = rows[-1][2]
        log.debug("  Price:     %.5f", curr)
        log.debug("  Structure: %s", result["structure"])
        log.debug("  Last HH/LH: %s", result["last_swing_high"])
        log.debug("  Last HL/LL: %s", result["last_swing_low"])
        log.debug("  Supply zones (%d):", len(result["supply_zones"]))
        for z in result["supply_zones"]:
            dist = abs(z["poi"] - curr) / result["atr"]
            log.debug("    %.5f - %.5f  POI:%.5f  %.1fxATR", z["top"], z["bottom"], z["poi"], dist)
        log.debug("  Demand zones (%d):", len(result["demand_zones"]))
        for z in result["demand_zones"]:
            dist = abs(z["poi"] - curr) / result["atr"]
            log.debug("    %.5f - %.5f  POI:%.5f  %.1fxATR", z["top"], z["bottom"], z["poi"], dist)
        log.debug("  BOS (%d):", len(result["bos_levels"]))
        for b in result["bos_levels"]:
            log.debug("    %s  level:%.5f", b["type"], b["level"])
