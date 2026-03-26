"""Telegram signal publishing — mirrors v1 push_signals.py Telegram logic."""

from __future__ import annotations

import json
import logging
import os
import urllib.error
import urllib.request
from typing import Any

logger = logging.getLogger(__name__)


def send_telegram(
    message: str,
    token: str | None = None,
    chat_id: str | None = None,
) -> bool:
    """Send a message via Telegram Bot API.

    Parameters
    ----------
    message : str
        Text to send (HTML parse mode).
    token : str, optional
        Bot token.  Falls back to ``TELEGRAM_TOKEN`` env var.
    chat_id : str, optional
        Target chat ID.  Falls back to ``TELEGRAM_CHAT_ID`` env var.

    Returns
    -------
    bool
        True if the message was sent successfully.
    """
    token = token or os.environ.get("TELEGRAM_TOKEN", "")
    chat_id = chat_id or os.environ.get("TELEGRAM_CHAT_ID", "")
    if not token or not chat_id:
        logger.debug("Telegram not configured (missing token or chat_id)")
        return False

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = json.dumps(
        {
            "chat_id": chat_id,
            "text": message,
            "parse_mode": "HTML",
        }
    ).encode()
    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            logger.info("Telegram OK (%s)", resp.status)
            return True
    except urllib.error.URLError as exc:
        logger.error("Telegram error: %s", exc)
        return False


def format_signal(signal: dict[str, Any]) -> str:
    """Format a signal dict as a Telegram-friendly message.

    Mirrors the ``fmt_signal`` function from v1 push_signals.py.
    """
    key = signal.get("instrument", signal.get("key", "?"))
    name = signal.get("name", key)
    direction = "LONG" if signal.get("direction") == "bull" else "SHORT"
    arrow = "\u25b2" if direction == "LONG" else "\u25bc"
    tf = signal.get("timeframe_bias", "SWING")
    grade = signal.get("grade", "?")
    score = signal.get("score", 0)
    vix = signal.get("vix_regime", "?")
    pos_size = signal.get("pos_size", "?")

    lines = [
        f"<b>{name}</b> [{tf}]",
        f"{direction} {arrow}  {grade}({score}/12)  VIX:{vix} -> {pos_size}",
    ]

    entry = signal.get("entry_price")
    sl = signal.get("stop_loss")
    t1 = signal.get("target_1")
    t2 = signal.get("target_2")
    rr1 = signal.get("rr_t1")

    if entry:
        lines.append(f"Entry: {entry}")
    if sl:
        lines.append(f"SL:    {sl}  ({signal.get('sl_type', '?')})")
    if t1:
        lines.append(f"T1:    {t1}  R:R {rr1}")
    if t2:
        lines.append(f"T2:    {t2}  R:R {signal.get('rr_t2', '?')}")

    return "\n".join(lines)
