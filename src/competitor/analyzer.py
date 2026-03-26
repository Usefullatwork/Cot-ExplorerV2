"""Competitor signal logging and accuracy analysis."""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_LOG_DIR = Path(os.environ.get("SIGNAL_LOG_DIR", "data/competitor"))
_LOG_FILE = _LOG_DIR / "signal_log.json"


def _load_log() -> list[dict[str, Any]]:
    """Load the signal log from disk."""
    if not _LOG_FILE.exists():
        return []
    try:
        with open(_LOG_FILE, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return []


def _save_log(entries: list[dict[str, Any]]) -> None:
    """Persist the signal log to disk."""
    _LOG_DIR.mkdir(parents=True, exist_ok=True)
    with open(_LOG_FILE, "w", encoding="utf-8") as f:
        json.dump(entries, f, indent=2, ensure_ascii=False)


def log_signal(signal: dict[str, Any], timestamp: str | None = None) -> None:
    """Append a signal entry to signal_log.json.

    Parameters
    ----------
    signal : dict
        Signal dict with at least ``instrument``, ``direction``, ``entry_price``,
        ``stop_loss``, ``target_1``, optionally ``target_2``.
    timestamp : str, optional
        ISO timestamp.  Defaults to now (UTC).
    """
    entry = {
        "timestamp": timestamp or datetime.now(timezone.utc).isoformat(),
        "outcome": "pending",
        **signal,
    }
    log = _load_log()
    log.append(entry)
    _save_log(log)
    logger.info("Logged signal: %s %s", signal.get("instrument"), signal.get("direction"))


def check_signal_outcome(
    signal: dict[str, Any],
    price_data: list[tuple[float, float, float]],
) -> str:
    """Evaluate a signal against subsequent price bars.

    Parameters
    ----------
    signal : dict
        Must contain ``direction``, ``entry_price``, ``stop_loss``, ``target_1``,
        and optionally ``target_2``.
    price_data : list[tuple[float, float, float]]
        Post-signal bars as (high, low, close).

    Returns
    -------
    str
        One of ``"t1_hit"``, ``"t2_hit"``, ``"stopped_out"``, ``"expired"``,
        or ``"pending"`` if no bars provided.
    """
    if not price_data:
        return "pending"

    direction = signal.get("direction", "bull")
    sl = signal["stop_loss"]
    t1 = signal["target_1"]
    t2 = signal.get("target_2")

    for h, lo, c in price_data:
        if direction == "bull":
            if lo <= sl:
                return "stopped_out"
            if t2 and h >= t2:
                return "t2_hit"
            if h >= t1:
                return "t1_hit"
        else:
            if h >= sl:
                return "stopped_out"
            if t2 and lo <= t2:
                return "t2_hit"
            if lo <= t1:
                return "t1_hit"

    return "expired"


def compute_accuracy(days: int = 90) -> dict[str, Any]:
    """Compute rolling accuracy stats over the last *days*.

    Returns a dict with ``total``, ``wins``, ``losses``, ``pending``,
    ``win_rate``, ``avg_rr``.
    """
    from datetime import timedelta

    log = _load_log()
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()

    recent = [e for e in log if e.get("timestamp", "") >= cutoff]
    total = len(recent)
    wins = sum(1 for e in recent if e.get("outcome") in ("t1_hit", "t2_hit"))
    losses = sum(1 for e in recent if e.get("outcome") == "stopped_out")
    pending = sum(1 for e in recent if e.get("outcome") == "pending")
    expired = sum(1 for e in recent if e.get("outcome") == "expired")

    resolved = wins + losses
    win_rate = round(wins / resolved * 100, 1) if resolved > 0 else 0.0

    rr_values = [e.get("rr_t1", 0) for e in recent if e.get("outcome") in ("t1_hit", "t2_hit") and e.get("rr_t1")]
    avg_rr = round(sum(rr_values) / len(rr_values), 2) if rr_values else 0.0

    return {
        "days": days,
        "total": total,
        "wins": wins,
        "losses": losses,
        "pending": pending,
        "expired": expired,
        "win_rate": win_rate,
        "avg_rr": avg_rr,
    }
