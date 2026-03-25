"""Audit logging convenience wrapper."""

from __future__ import annotations

import logging
from typing import Any

from src.db.repository import save_audit_log

logger = logging.getLogger(__name__)


def log_event(event_type: str, details: dict[str, Any] | None = None) -> None:
    """Write an event to the audit_log table.

    Parameters
    ----------
    event_type : str
        Short identifier such as ``"pipeline_start"``, ``"signal_generated"``,
        ``"api_error"``.
    details : dict, optional
        Arbitrary JSON-serialisable metadata.
    """
    try:
        save_audit_log(event_type=event_type, details=details)
        logger.info("Audit: %s", event_type)
    except Exception as exc:
        # Never let audit logging crash the caller
        logger.error("Audit log write failed: %s — %s", event_type, exc)
