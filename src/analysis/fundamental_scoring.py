"""
fundamental_scoring.py - Pure scoring functions for fundamental macro data.

No I/O or HTTP calls. Extracted from src/trading/core/fetch_fundamentals.py.
"""

from src.config.fundamentals import INDICATOR_WEIGHTS


def score_indicator(key: str, current: float | None, previous: float | None) -> int:
    """Score an indicator -2..+2 for USD bullish/bearish bias."""
    if current is None:
        return 0

    if key in ("mPMI", "sPMI"):
        if current > 56:     s = 2
        elif current > 52:   s = 1
        elif current > 50:   s = 0
        elif current > 47:   s = -1
        else:                s = -2
        if previous is not None:
            delta = current - previous
            if delta > 2 and s < 2:      s += 1
            elif delta < -2 and s > -2:  s -= 1
        return max(-2, min(2, s))

    if key in ("CPI", "PPI", "PCE"):
        if current > 4.5:     level_s = 2
        elif current > 2.5:   level_s = 1
        elif current > 1.5:   level_s = 0
        elif current > 0.5:   level_s = -1
        else:                  level_s = -2
        trend_s = 0
        if previous is not None:
            if current > previous + 0.2:     trend_s = 1
            elif current < previous - 0.2:   trend_s = -1
        return max(-2, min(2, level_s + trend_s))

    if key == "IntRate":
        if previous is None:
            return 1 if current >= 3.5 else 0
        delta = round(current - previous, 3)
        if delta > 0.1:      return 2
        elif delta > 0:      return 1
        elif delta == 0:     return 1 if current >= 4.0 else 0
        elif delta > -0.1:   return -1
        else:                return -2

    if key == "NFP":
        if current > 250:     s = 2
        elif current > 150:   s = 1
        elif current > 50:    s = 0
        elif current > 0:     s = -1
        else:                  s = -2
        if previous is not None and previous != 0:
            if current > 0 and previous > 0 and current > previous * 1.5 and s < 2:
                s += 1
            elif current < 0 and previous < 0 and s > -2:
                s -= 1
        return max(-2, min(2, s))

    if key == "ADP":
        val = current / 1000 if abs(current) > 5000 else current
        if val > 250:     return 2
        elif val > 150:   return 1
        elif val > 50:    return 0
        elif val > 0:     return -1
        else:             return -2

    if key == "Unemp":
        if current < 3.5:     s = 2
        elif current < 4.0:   s = 1
        elif current < 4.5:   s = 0
        elif current < 5.0:   s = -1
        else:                  s = -2
        if previous is not None:
            if current < previous:     s = min(2, s + 1)
            elif current > previous:   s = max(-2, s - 1)
        return s

    if key == "Claims":
        k = current / 1000
        if k < 200:       s = 2
        elif k < 225:     s = 1
        elif k < 260:     s = 0
        elif k < 300:     s = -1
        else:              s = -2
        if previous is not None:
            pk = previous / 1000
            if k < pk:     s = min(2, s + 1)
            elif k > pk:   s = max(-2, s - 1)
        return s

    if key == "JOLTS":
        if current > 9000:     return 2
        elif current > 7500:   return 1
        elif current > 6000:   return 0
        elif current > 4500:   return -1
        else:                   return -2

    if key == "GDP":
        if current > 3.0:     return 2
        elif current > 1.5:   return 1
        elif current > 0:     return 0
        elif current > -1:    return -1
        else:                  return -2

    if key == "Retail":
        if current > 1.0:      return 2
        elif current > 0.3:    return 1
        elif current > -0.3:   return 0
        elif current > -0.8:   return -1
        else:                   return -2

    if key == "ConConf":
        if current > 90:     s = 2
        elif current > 75:   s = 1
        elif current > 65:   s = 0
        elif current > 55:   s = -1
        else:                 s = -2
        if previous is not None:
            if current > previous:     s = min(2, s + 1)
            elif current < previous:   s = max(-2, s - 1)
        return max(-2, min(2, s))

    return 0


def compute_indicator(key: str, cfg: dict, obs: list[tuple[str, float]]) -> dict | None:
    """Compute current/previous values and score for an indicator."""
    if not obs:
        return None
    t = cfg["type"]
    date = obs[-1][0]
    raw_cur = obs[-1][1]
    raw_prev = obs[-2][1] if len(obs) >= 2 else None

    if t == "level":
        current = round(raw_cur, 3)
        previous = round(raw_prev, 3) if raw_prev is not None else None
    elif t == "yoy":
        if len(obs) < 13:
            return None
        current = round((obs[-1][1] / obs[-13][1] - 1) * 100, 2)
        previous = round((obs[-2][1] / obs[-14][1] - 1) * 100, 2) if len(obs) >= 14 else None
    elif t == "mom":
        if len(obs) < 2:
            return None
        current = round((obs[-1][1] / obs[-2][1] - 1) * 100, 2)
        previous = round((obs[-2][1] / obs[-3][1] - 1) * 100, 2) if len(obs) >= 3 else None
    elif t == "mom_abs":
        if len(obs) < 2:
            return None
        current = round(obs[-1][1] - obs[-2][1], 1)
        previous = round(obs[-2][1] - obs[-3][1], 1) if len(obs) >= 3 else None
    else:
        current, previous = raw_cur, raw_prev

    score = score_indicator(key, current, previous)
    trend = ("opp" if current > previous else "ned" if current < previous else "flat") \
            if previous is not None else "ukjent"

    display_cur = round(current / 1000, 1) if key == "Claims" else current
    display_prev = round(previous / 1000, 1) if (key == "Claims" and previous is not None) else previous

    if key == "ADP" and abs(current) > 5000:
        display_cur = round(current / 1000, 1)
        display_prev = round(previous / 1000, 1) if previous is not None else None

    return {
        "key": key, "label": cfg["label"],
        "current": display_cur, "previous": display_prev,
        "date": date, "score": score, "trend": trend,
    }


def weighted_cat_avg(cat_keys: list[str], indicators: dict) -> float:
    """Weighted average of indicator scores within a category."""
    total_score = 0.0
    total_w = 0.0
    for k in cat_keys:
        if k in indicators:
            w = INDICATOR_WEIGHTS.get(k, 1.0)
            total_score += indicators[k]["score"] * w
            total_w += w
    return round(total_score / total_w, 3) if total_w > 0 else 0.0


def consensus_multiplier(cat_scores: dict) -> float:
    """Calculate multiplier based on category agreement/disagreement."""
    THRESHOLD = 0.35
    infl_dir = 1 if cat_scores.get("inflation", 0) > THRESHOLD else \
              -1 if cat_scores.get("inflation", 0) < -THRESHOLD else 0
    jobs_dir = 1 if cat_scores.get("jobs", 0) > THRESHOLD else \
              -1 if cat_scores.get("jobs", 0) < -THRESHOLD else 0
    growth_dir = 1 if cat_scores.get("econ_growth", 0) > THRESHOLD else \
                -1 if cat_scores.get("econ_growth", 0) < -THRESHOLD else 0

    dirs = [d for d in [infl_dir, jobs_dir, growth_dir] if d != 0]

    if len(dirs) >= 2 and all(d == dirs[0] for d in dirs):
        return 1.5
    elif len(dirs) == 2 and dirs[0] != dirs[1]:
        return 0.65
    elif len(dirs) == 1:
        return 1.0
    else:
        return 0.5
