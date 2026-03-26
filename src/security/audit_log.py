"""Audit logging for security-sensitive operations."""

import logging
from datetime import datetime, timezone
from typing import Any

log = logging.getLogger(__name__)


def log_event(
    event_type: str,
    details: dict[str, Any] | None = None,
    severity: str = "INFO",
) -> None:
    """Log a security-relevant event with structured metadata.

    Args:
        event_type: Category of event (e.g., 'api_access', 'data_fetch', 'auth_failure')
        details: Optional dict with event-specific data
        severity: Log level string (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    """
    level = getattr(logging, severity.upper(), logging.INFO)
    timestamp = datetime.now(timezone.utc).isoformat()
    message = f"[AUDIT] {event_type} at {timestamp}"
    if details:
        message += f" | {details}"
    log.log(level, message)
