"""Price level detection and merging — pure functions, no side effects.

Extracted from v1 fetch_all.py lines 267-368.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

# ---------------------------------------------------------------------------
# Type alias — rows are plain (h,l,c) tuples as used throughout v1.
# ---------------------------------------------------------------------------
Row = tuple[float, float, float]


def get_pdh_pdl_pdc(
    daily: list[Row],
) -> tuple[Optional[float], Optional[float], Optional[float]]:
    """Previous day high, low, close from daily bars."""
    if len(daily) < 2:
        return None, None, None
    return daily[-2][0], daily[-2][1], daily[-2][2]


def get_pwh_pwl(
    daily: list[Row],
) -> tuple[Optional[float], Optional[float]]:
    """Previous week high and low (approximated from last 7 trading days)."""
    if len(daily) < 10:
        return None, None
    week = daily[-8:-1]
    return max(r[0] for r in week), min(r[1] for r in week)


def get_session_status() -> dict:
    """Return current trading session status based on CET time.

    Returns dict with keys: active (bool), label (str), cet_hour (int).
    """
    h = datetime.now(timezone.utc).hour
    m = datetime.now(timezone.utc).minute
    cet = (h * 60 + m + 60) % (24 * 60)  # UTC+1
    ch = cet // 60
    sessions: list[str] = []
    if 7 * 60 <= cet < 12 * 60:
        sessions.append("London")
    if 13 * 60 <= cet < 17 * 60:
        sessions.append("NY Overlap")
    if 8 * 60 <= cet < 12 * 60:
        sessions.append("London Fix")
    if not sessions:
        sessions.append("Off-session")
    return {
        "active": any(s != "Off-session" for s in sessions),
        "label": " / ".join(sessions),
        "cet_hour": ch,
    }


def find_intraday_levels(rows_15m: list[Row], n: int = 3) -> tuple[list[float], list[float]]:
    """Find intraday support/resistance from 15m candles.

    Uses last ~200 candles (~2 days).  n = minimum candles on each side to
    confirm a pivot.  Returns (resistances, supports) sorted by proximity
    to current price, max 4 each.
    """
    rows = rows_15m[-200:] if len(rows_15m) > 200 else rows_15m
    curr = rows[-1][2]
    res: list[float] = []
    sup: list[float] = []
    for i in range(n, len(rows) - n):
        if rows[i][0] == max(r[0] for r in rows[i - n : i + n + 1]):
            res.append(rows[i][0])
        if rows[i][1] == min(r[1] for r in rows[i - n : i + n + 1]):
            sup.append(rows[i][1])
    r_filt = sorted(
        list(dict.fromkeys([round(r, 5) for r in res if r > curr])),
        key=lambda x: abs(x - curr),
    )[:4]
    s_filt = sorted(
        list(dict.fromkeys([round(s, 5) for s in sup if s < curr])),
        key=lambda x: abs(x - curr),
    )[:4]
    return r_filt, s_filt


def find_swing_levels(rows: list[Row], n: int = 5) -> tuple[list[float], list[float]]:
    """Daily / 4H swing levels for context.

    Returns (resistances, supports) sorted by proximity, max 3 each.
    """
    curr = rows[-1][2]
    res: list[float] = []
    sup: list[float] = []
    for i in range(n, len(rows) - n):
        if rows[i][0] == max(r[0] for r in rows[i - n : i + n + 1]):
            res.append(rows[i][0])
        if rows[i][1] == min(r[1] for r in rows[i - n : i + n + 1]):
            sup.append(rows[i][1])
    r_filt = sorted(
        list(dict.fromkeys([round(r, 5) for r in res if r > curr])),
        key=lambda x: abs(x - curr),
    )[:3]
    s_filt = sorted(
        list(dict.fromkeys([round(s, 5) for s in sup if s < curr])),
        key=lambda x: abs(x - curr),
    )[:3]
    return r_filt, s_filt


def is_at_level(curr: float, level: float, atr_15m: float, weight: int = 1) -> bool:
    """Check if price is within tolerance of a level.

    Tolerances by weight:
      weight <= 1 (15m):           0.30 x ATR
      weight == 2 (4H / SMC):     0.35 x ATR
      weight >= 3 (D1 / Weekly):  0.45 x ATR
    """
    tight = 0.30 if weight <= 1 else (0.35 if weight == 2 else 0.45)
    return abs(curr - level) <= atr_15m * tight


def merge_tagged_levels(
    tagged: list[dict],
    curr: float,
    atr: float | None,
    max_n: int = 6,
) -> list[dict]:
    """Merge levels within 0.5 x ATR of each other, keeping highest weight.

    Weight scale:
      1 = 15m pivot (weakest)
      2 = 4H swing / SMC zone
      3 = Daily swing / PDC
      4 = PDH / PDL
      5 = PWH / PWL (strongest)

    Returns list sorted by proximity to current price, max *max_n* entries.
    """
    if not tagged:
        return []
    atr_buf = (atr or 0) * 0.5
    merged: list[dict] = []
    for lvl in sorted(tagged, key=lambda x: abs(x["price"] - curr)):
        absorbed = False
        for m in merged:
            if atr_buf > 0 and abs(lvl["price"] - m["price"]) < atr_buf:
                # Keep highest weight; update source and price if stronger
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
