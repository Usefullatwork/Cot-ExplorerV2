"""Level-to-level setup builder — pure function, no side effects.

Extracted from v1 fetch_all.py lines 371-527.
"""

from __future__ import annotations

from typing import Optional

from src.analysis.levels import is_at_level
from src.core.models import SetupL2L


def make_setup_l2l(
    curr: float,
    atr_15m: float,
    atr_daily: float | None,
    sup_tagged: list[dict],
    res_tagged: list[dict],
    direction: str,
    klasse: str,
    min_rr: float = 1.5,
) -> SetupL2L | None:
    """Build a macro level-to-level setup with structural stop loss.

    Geometry:
      LONG:  entry = support/demand zone,  SL = below zone bottom or 0.3-0.5 x ATR(D1)
      SHORT: entry = resistance/supply zone, SL = above zone top or 0.3-0.5 x ATR(D1)

    Rules:
      - SL is placed at STRUCTURE, not mechanical ATR from current price
        . SMC demand/supply zone: SL = zone_bottom/top + 0.15 x ATR(D1) buffer
        . Line level (PDH/PDL/D1/PWH/PWL): SL = level +/- 0.3-0.5 x ATR(D1)
      - Risk = actual distance entry -> SL (not fixed ATR)
      - T1 must give R:R >= min_rr based on actual risk
      - Watchlist filter: price max 1 x ATR(D1) from entry level
    """
    if not atr_15m or atr_15m <= 0:
        return None
    if not atr_daily or atr_daily <= 0:
        atr_daily = atr_15m * 5

    def structural_sl(entry_level: float, entry_obj: dict, dir_: str) -> float:
        """SL at structural level — never mechanical ATR from current price."""
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

    def best_t1(
        levels: list[dict], entry: float, min_dist: float
    ) -> Optional[dict]:
        """Best T1: highest HTF weight -> nearest to entry, at least min_dist away."""
        cands = sorted(levels, key=lambda x: (-x["weight"], abs(x["price"] - entry)))
        for l in cands:
            p = l["price"]
            ok = (p > entry + min_dist) if direction == "long" else (p < entry - min_dist)
            if ok:
                q = (
                    "htf"
                    if l["weight"] >= 3
                    else ("4h" if l["weight"] >= 2 else "weak")
                )
                return dict(l, t1_quality=q)
        return None

    if direction == "long":
        if not sup_tagged or not res_tagged:
            return None
        entry_obj = sup_tagged[0]
        entry_level = entry_obj["price"]
        entry_w = entry_obj["weight"]

        entry_dist = curr - entry_level
        max_entry_dist = atr_daily * (
            0.3 if entry_w <= 1 else 0.7 if entry_w == 2 else 1.0
        )
        if entry_dist < 0 or entry_dist > max_entry_dist:
            return None

        sl = structural_sl(entry_level, entry_obj, "long")
        risk = entry_level - sl
        if risk <= 0:
            return None
        min_t1_dist = risk * min_rr

        t1_obj = best_t1(res_tagged, entry_level, min_t1_dist)
        if t1_obj is None:
            return None
        t1 = t1_obj["price"]

        res_after = [l for l in res_tagged if l["price"] > t1]
        t2 = res_after[0]["price"] if res_after else round(t1 + risk, 5)

        rr1 = round((t1 - entry_level) / risk, 2)
        rr2 = round((t2 - entry_level) / risk, 2)

        at_level = is_at_level(curr, entry_level, atr_15m, entry_w)
        sl_src = "zone" if entry_obj.get("zone_bottom") else "struktur"
        q = t1_obj["t1_quality"]
        return SetupL2L(
            entry=round(entry_level, 5),
            entry_curr=round(curr, 5),
            sl=sl,
            sl_type=sl_src,
            t1=round(t1, 5),
            t2=round(t2, 5),
            rr_t1=rr1,
            rr_t2=rr2,
            min_rr=min_rr,
            risk_atr_d=round(risk / atr_daily, 2),
            entry_dist_atr=round(entry_dist / atr_daily, 2),
            entry_name=f"Støtte {round(entry_level, 5)} [{entry_obj['source']}]",
            entry_level=round(entry_level, 5),
            entry_weight=entry_w,
            t1_source=t1_obj["source"],
            t1_weight=t1_obj["weight"],
            t1_quality=q,
            status="aktiv" if at_level else "watchlist",
            note=(
                f"MAKRO LONG: E={round(entry_level, 4)} [{entry_obj['source']} w{entry_w}]"
                f" SL={round(sl, 4)} ({sl_src}) → T1={round(t1, 4)}"
                f" [{t1_obj['source']} w{t1_obj['weight']} {q}]"
                f" R:R={rr1} | Risk={round(risk, 4)} ({round(risk / atr_daily, 2)}×ATRd)"
            ),
            timeframe="D1/4H",
        )
    else:
        # SHORT
        if not res_tagged or not sup_tagged:
            return None
        entry_obj = res_tagged[0]
        entry_level = entry_obj["price"]
        entry_w = entry_obj["weight"]

        entry_dist = entry_level - curr
        max_entry_dist = atr_daily * (
            0.3 if entry_w <= 1 else 0.7 if entry_w == 2 else 1.0
        )
        if entry_dist < 0 or entry_dist > max_entry_dist:
            return None

        sl = structural_sl(entry_level, entry_obj, "short")
        risk = sl - entry_level
        if risk <= 0:
            return None
        min_t1_dist = risk * min_rr

        t1_obj = best_t1(sup_tagged, entry_level, min_t1_dist)
        if t1_obj is None:
            return None
        t1 = t1_obj["price"]

        sup_after = [l for l in sup_tagged if l["price"] < t1]
        t2 = sup_after[0]["price"] if sup_after else round(t1 - risk, 5)

        rr1 = round((entry_level - t1) / risk, 2)
        rr2 = round((entry_level - t2) / risk, 2)

        at_level = is_at_level(curr, entry_level, atr_15m, entry_w)
        sl_src = "zone" if entry_obj.get("zone_top") else "struktur"
        q = t1_obj["t1_quality"]
        return SetupL2L(
            entry=round(entry_level, 5),
            entry_curr=round(curr, 5),
            sl=sl,
            sl_type=sl_src,
            t1=round(t1, 5),
            t2=round(t2, 5),
            rr_t1=rr1,
            rr_t2=rr2,
            min_rr=min_rr,
            risk_atr_d=round(risk / atr_daily, 2),
            entry_dist_atr=round(entry_dist / atr_daily, 2),
            entry_name=f"Motstand {round(entry_level, 5)} [{entry_obj['source']}]",
            entry_level=round(entry_level, 5),
            entry_weight=entry_w,
            t1_source=t1_obj["source"],
            t1_weight=t1_obj["weight"],
            t1_quality=q,
            status="aktiv" if at_level else "watchlist",
            note=(
                f"MAKRO SHORT: E={round(entry_level, 4)} [{entry_obj['source']} w{entry_w}]"
                f" SL={round(sl, 4)} ({sl_src}) → T1={round(t1, 4)}"
                f" [{t1_obj['source']} w{t1_obj['weight']} {q}]"
                f" R:R={rr1} | Risk={round(risk, 4)} ({round(risk / atr_daily, 2)}×ATRd)"
            ),
            timeframe="D1/4H",
        )
