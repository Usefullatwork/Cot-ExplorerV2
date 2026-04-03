"""Signal health monitoring routes — ensemble quality and decay alerts.

Reads live data from pipeline_state.  If no Layer 2 run has occurred,
triggers an on-demand computation so the frontend never sees stale
placeholder data.
"""

from __future__ import annotations

import json
import logging

from fastapi import APIRouter

from src.db.engine import session_ctx
from src.db.models import PipelineState

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/signal-health", tags=["signal-health"])


# ── Helpers ──────────────────────────────────────────────────────────────────


def _ensure_layer2() -> PipelineState | None:
    """Return PipelineState, running Layer 2 on-demand if needed."""
    with session_ctx() as session:
        state = session.query(PipelineState).first()
        if state and state.signal_weights_json:
            return state

    # No cached data — trigger Layer 2
    try:
        from src.pipeline.layer2_runner import run_layer2

        logger.info("signal-health: triggering on-demand Layer 2")
        with session_ctx() as session:
            run_layer2(session)
            return session.query(PipelineState).first()
    except Exception:
        logger.warning("On-demand Layer 2 failed", exc_info=True)
        return None


# ── Endpoints ────────────────────────────────────────────────────────────────


@router.get("", summary="Full ensemble health report")
async def get_signal_health() -> dict:
    """Full ensemble health report with per-signal stats."""
    state = _ensure_layer2()

    if state and state.signal_weights_json:
        weights = json.loads(state.signal_weights_json)
        active = sum(1 for w in weights.values() if w > 0)
        excluded = len(weights) - active
        return {
            "ensemble_quality": state.ensemble_quality or "healthy",
            "active_signals": active,
            "excluded_signals": excluded,
            "total_signals": len(weights),
            "weights": weights,
            "drift_detected": state.drift_detected,
            "is_live": True,
            "updated_at": (
                state.updated_at.isoformat() if state.updated_at else None
            ),
        }

    return {
        "ensemble_quality": "unknown",
        "active_signals": 0,
        "excluded_signals": 0,
        "total_signals": 0,
        "weights": {},
        "drift_detected": False,
        "is_live": False,
        "message": "No signal data available — run the pipeline first",
    }


@router.get("/weights", summary="Current signal weights")
async def get_signal_weights() -> dict:
    """Current signal weights from the ensemble."""
    state = _ensure_layer2()

    if state and state.signal_weights_json:
        return {
            "weights": json.loads(state.signal_weights_json),
            "is_live": True,
        }

    return {"weights": {}, "is_live": False}


@router.get("/decay-alerts", summary="Decay alerts")
async def get_decay_alerts() -> dict:
    """Signals with decay warnings."""
    state = _ensure_layer2()

    if state and state.signal_weights_json:
        weights = json.loads(state.signal_weights_json)
        decayed = [k for k, v in weights.items() if 0 < v < 0.5]
        if decayed:
            return {
                "decayed_signals": decayed,
                "message": f"{len(decayed)} signal(s) showing decay",
            }

    return {"decayed_signals": [], "message": "No signals currently decayed"}
