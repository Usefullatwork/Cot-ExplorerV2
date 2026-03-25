"""Discord signal publishing — mirrors v1 push_signals.py Discord logic."""

from __future__ import annotations

import json
import logging
import os
import urllib.error
import urllib.request

logger = logging.getLogger(__name__)


def send_discord(
    message: str,
    webhook_url: str | None = None,
) -> bool:
    """Send a message to a Discord webhook.

    Parameters
    ----------
    message : str
        Text to send.  Will be wrapped in a code block.
    webhook_url : str, optional
        Discord webhook URL.  Falls back to ``DISCORD_WEBHOOK`` env var.

    Returns
    -------
    bool
        True if the message was sent successfully.
    """
    webhook_url = webhook_url or os.environ.get("DISCORD_WEBHOOK", "")
    if not webhook_url:
        logger.debug("Discord not configured (missing webhook URL)")
        return False

    payload = json.dumps({"content": f"```\n{message}\n```"}).encode()
    req = urllib.request.Request(
        webhook_url,
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            logger.info("Discord OK (%s)", resp.status)
            return True
    except urllib.error.URLError as exc:
        logger.error("Discord error: %s", exc)
        return False
