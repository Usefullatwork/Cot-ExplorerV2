"""
pmi_calendar.py - Extract PMI data from ForexFactory calendar JSON.

Extracted from src/trading/core/fetch_fundamentals.py.
"""

import json
import os

from src.analysis.fundamental_scoring import score_indicator


def try_calendar_pmi(data_dir: str) -> dict:
    """Try to load PMI data from ForexFactory calendar."""
    cal_path = os.path.join(data_dir, "prices", "calendar_latest.json")
    if not os.path.exists(cal_path):
        return {}
    try:
        with open(cal_path) as f:
            cal = json.load(f)
    except Exception:
        return {}

    pmi_map = {}
    for ev in cal.get("events", []):
        if ev.get("country") != "USD":
            continue
        title = ev.get("title", "").lower()
        actual = ev.get("actual", "")
        if not actual:
            continue
        try:
            act_val = float(str(actual).replace("%", "").strip())
        except (ValueError, AttributeError):
            continue
        try:
            fore_val = float(str(ev.get("forecast", "")).replace("%", "").strip()) \
                       if ev.get("forecast") else None
        except (ValueError, AttributeError):
            fore_val = None
        try:
            prev_val = float(str(ev.get("previous", "")).replace("%", "").strip()) \
                       if ev.get("previous") else None
        except (ValueError, AttributeError):
            prev_val = None

        base_score = score_indicator("mPMI", act_val, prev_val)
        if fore_val is not None:
            diff = act_val - fore_val
            surprise = 2 if diff > 1 else 1 if diff > 0 else -2 if diff < -1 else -1 if diff < 0 else 0
        else:
            surprise = 0
        final_score = max(-2, min(2, base_score + surprise))

        entry = {"actual": act_val, "forecast": fore_val, "previous": prev_val,
                 "surprise": surprise, "score": final_score}
        if "ism manufacturing" in title or ("manufacturing pmi" in title and "flash" not in title):
            pmi_map["mPMI"] = entry
        elif ("ism services" in title or ("services pmi" in title and "flash" not in title)
              or "non-manufacturing" in title):
            pmi_map["sPMI"] = entry

    return pmi_map
