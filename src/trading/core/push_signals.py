#!/usr/bin/env python3
"""
push_signals.py - Signal notification dispatcher.

Reads macro.json and pushes top trading setups to configured channels:
  - Telegram bot
  - Discord webhook
  - Flask signal server (/push-alert)

Environment variables:
  TELEGRAM_TOKEN   + TELEGRAM_CHAT_ID  -> Telegram bot
  DISCORD_WEBHOOK                      -> Discord webhook
  PUSH_MIN_SCORE   = 5                 -> minimum score to push (default 5)
  PUSH_MAX_SIGNALS = 5                 -> max signals per run
  FLASK_URL        = http://localhost:5000  -> signal_server.py
  SCALP_API_KEY                        -> API key for Flask server

Zero external dependencies - stdlib only.
"""

import logging
import os
import json
import sys
import urllib.request
import urllib.error
from pathlib import Path
from datetime import datetime, timezone

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(_DIR, "..", "..", ".."))
DATA_FILE = os.path.join(PROJECT_ROOT, "data", "prices", "macro_latest.json")

# ---------------------------------------------------------------------------
# Configuration from environment
# ---------------------------------------------------------------------------
MIN_SCORE = int(os.environ.get("PUSH_MIN_SCORE", "5"))
MAX_SIGNALS = int(os.environ.get("PUSH_MAX_SIGNALS", "5"))
TG_TOKEN = os.environ.get("TELEGRAM_TOKEN", "")
TG_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")
DC_WEBHOOK = os.environ.get("DISCORD_WEBHOOK", "")
FLASK_URL = os.environ.get("FLASK_URL", "http://localhost:5000")
SCALP_API_KEY = os.environ.get("SCALP_API_KEY", "")


def load_data() -> dict:
    """Load macro data from disk."""
    if not os.path.exists(DATA_FILE):
        log.error("ERROR: %s not found - run fetch_all.py first", DATA_FILE)
        sys.exit(1)
    with open(DATA_FILE) as f:
        return json.load(f)


def score_key(item: tuple[str, dict]) -> tuple[int, int]:
    """Sort key for signal prioritization: MAKRO > SWING > SCALP, then score."""
    _, d = item
    tf_rank = {"MAKRO": 3, "SWING": 2, "SCALP": 1, "WATCHLIST": 0}
    return (tf_rank.get(d.get("timeframe_bias", "WATCHLIST"), 0), d.get("score", 0))


def get_top_signals(macro: dict) -> list[tuple[str, dict]]:
    """Filter and sort signals by score threshold."""
    levels = macro.get("trading_levels", {})
    candidates = [
        (key, d) for key, d in levels.items()
        if d.get("score", 0) >= MIN_SCORE
    ]
    candidates.sort(key=score_key, reverse=True)
    return candidates[:MAX_SIGNALS]


def fmt_signal(key: str, d: dict, vix_price: float) -> str:
    """Format a single signal as a text card."""
    direction = "LONG  ^" if d.get("dir_color") == "bull" else "SHORT v"
    tf = d.get("timeframe_bias", "SWING")
    grade = d.get("grade", "?")
    score = d.get("score", 0)
    curr = d.get("current", 0)
    p = 5 if curr < 100 else 2
    cot = d.get("cot", {})
    cot_str = f"{cot.get('bias', '?')} {cot.get('momentum', '')} ({cot.get('pct', 0):.1f}%)"
    sma_pos = d.get("sma200_pos", "?")
    pos_size = d.get("pos_size", "?")

    active_setup = d.get("setup_long") if d.get("dir_color") == "bull" else d.get("setup_short")

    lines = [
        f"-- {d.get('name', key)} [{tf}] --",
        f"{direction}  {grade}({score}/8)  VIX:{vix_price:.1f} -> {pos_size}",
    ]

    if active_setup:
        risk_desc = f"{active_setup.get('risk_atr_d', '?')}xATRd ({active_setup.get('sl_type', '?')} SL)"
        lines += [
            f"Entry: {round(active_setup['entry'], p)}  [{active_setup.get('t1_source', '?')}]",
            f"SL:    {round(active_setup['sl'], p)}  ({risk_desc})",
            f"T1:    {round(active_setup['t1'], p)}  R:R {active_setup.get('rr_t1', '?')}",
        ]
        if active_setup.get("t2"):
            lines.append(f"T2:    {round(active_setup['t2'], p)}  R:R {active_setup.get('rr_t2', '?')}")
    else:
        nearest = d.get("supports" if d.get("dir_color") == "bull" else "resistances", [])
        if nearest:
            n = nearest[0]
            lines.append(f"Nearest: {n['level']} [{n['name']}]  ({n['dist_atr']:.1f}xATR away)")
        lines.append("No active setup - watchlist")

    lines += [
        f"COT:   {cot_str}",
        f"SMA200: {sma_pos}  | Chg20d: {d.get('chg20d', 0):+.1f}%",
    ]

    events = d.get("binary_risk", [])
    for ev in events[:2]:
        lines.append(f"  EVENT: {ev.get('title', '')} at {ev.get('cet', '?')}")

    return "\n".join(lines)


def build_message(top_signals: list[tuple[str, dict]], macro: dict) -> str:
    """Build the full notification message."""
    generated = macro.get("date", "unknown")
    vix_price = (macro.get("prices") or {}).get("VIX", {}).get("price", 20)
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines = [f"COT Explorer  |  {ts}", f"Data: {generated}", ""]
    for key, d in top_signals:
        lines.append(fmt_signal(key, d, vix_price))
        lines.append("")
    return "\n".join(lines).strip()


def push_telegram(text: str) -> None:
    """Push message to Telegram bot."""
    if not TG_TOKEN or not TG_CHAT_ID:
        return
    url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
    payload = json.dumps({
        "chat_id": TG_CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
    }).encode()
    req = urllib.request.Request(url, data=payload,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            log.info("Telegram OK (%s)", resp.status)
    except urllib.error.URLError as e:
        log.error("Telegram: %s", e)


def push_discord(text: str) -> None:
    """Push message to Discord webhook."""
    if not DC_WEBHOOK:
        return
    payload = json.dumps({"content": f"```\n{text}\n```"}).encode()
    req = urllib.request.Request(DC_WEBHOOK, data=payload,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            log.info("Discord OK (%s)", resp.status)
    except urllib.error.URLError as e:
        log.error("Discord: %s", e)


def push_flask(signals: list[dict], generated: str) -> None:
    """Push signals to Flask signal server."""
    if not SCALP_API_KEY:
        return
    url = f"{FLASK_URL}/push-alert"
    payload = json.dumps({"signals": signals, "generated": generated}).encode()
    req = urllib.request.Request(
        url, data=payload,
        headers={"Content-Type": "application/json", "X-API-Key": SCALP_API_KEY},
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            log.info("Flask /push-alert OK (%s)", resp.status)
    except urllib.error.URLError as e:
        log.error("Flask: %s", e)


def main() -> None:
    """Main entry point - load data, filter signals, push notifications."""
    macro = load_data()
    top = get_top_signals(macro)

    if not top:
        log.info("No signals with score >= %d", MIN_SCORE)
        sys.exit(0)

    message = build_message(top, macro)
    log.info("%s", message)

    push_telegram(message)
    push_discord(message)

    generated = macro.get("date", "unknown")
    push_flask([{
        "key": key,
        "name": d.get("name", key),
        "timeframe_bias": d.get("timeframe_bias", "SWING"),
        "direction": d.get("dir_color", "?"),
        "grade": d.get("grade", "?"),
        "score": d.get("score", 0),
        "setup": d.get("setup_long") if d.get("dir_color") == "bull" else d.get("setup_short"),
        "cot": d.get("cot", {}),
    } for key, d in top], generated)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    main()
