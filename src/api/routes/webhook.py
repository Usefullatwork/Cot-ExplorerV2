"""Webhook endpoints for v1 compatibility (push-alert)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from src.db import repository as repo

router = APIRouter(prefix="/api/v1", tags=["webhook"])


# ── Request / Response models ────────────────────────────────────────────────


class PushAlertRequest(BaseModel):
    """Request body for the push-alert webhook."""

    signals: list[dict[str, Any]] = Field(
        default_factory=list,
        description="List of signal dicts produced by the analysis pipeline",
        examples=[[{"instrument": "EURUSD", "direction": "bull", "grade": "A", "score": 10}]],
    )
    generated: str = Field(
        "",
        description="ISO timestamp when the signal batch was generated",
        examples=["2026-03-26T08:00:00+00:00"],
    )


class PushAlertResponse(BaseModel):
    """Response for the push-alert webhook."""

    status: str = Field(..., description="Processing status", examples=["ok"])
    received: int = Field(..., description="Number of signals received in this batch", examples=[5])


# ── Endpoint ─────────────────────────────────────────────────────────────────


@router.post(
    "/webhook/push-alert",
    response_model=PushAlertResponse,
    summary="Receive push-alert signals",
    description=(
        'Accepts the same JSON payload that ``push_signals.py`` sends: ``{"signals": [...], "generated": "..."}``.'
    ),
)
async def push_alert(body: PushAlertRequest) -> PushAlertResponse:
    """Receive push-alert payloads (v1 compatibility).

    Accepts the same JSON shape that push_signals.py sends to the Flask
    server:  ``{ "signals": [...], "generated": "..." }``
    """
    repo.save_audit_log(
        event_type="push_alert_received",
        details={"signals_count": len(body.signals), "generated": body.generated},
    )

    return PushAlertResponse(status="ok", received=len(body.signals))
