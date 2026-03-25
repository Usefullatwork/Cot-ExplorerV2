"""Webhook endpoints for v1 compatibility (push-alert)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request

from src.db import repository as repo

router = APIRouter(prefix="/api/v1", tags=["webhook"])


@router.post("/webhook/push-alert")
async def push_alert(request: Request) -> dict:
    """Receive push-alert payloads (v1 compatibility).

    Accepts the same JSON shape that push_signals.py sends to the Flask
    server:  ``{ "signals": [...], "generated": "..." }``
    """
    body: dict[str, Any] = await request.json()
    signals = body.get("signals", [])
    generated = body.get("generated", "")

    repo.save_audit_log(
        event_type="push_alert_received",
        details={"signals_count": len(signals), "generated": generated},
    )

    return {"status": "ok", "received": len(signals)}
