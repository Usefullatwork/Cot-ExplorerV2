"""Signal health monitoring routes — ensemble quality and decay alerts.

Reads live data from pipeline_state when available, falls back to
placeholder data when no Layer 2 run has occurred yet.
"""

from __future__ import annotations

import json

from fastapi import APIRouter

from src.db.engine import session_scope
from src.db.models import PipelineState

router = APIRouter(prefix="/api/v1/signal-health", tags=["signal-health"])

# ── Placeholder data (used when no Layer 2 run has occurred) ─────────────────

_PLACEHOLDER_SIGNALS = [
    {"id": "sma200", "win_rate": 0.62, "p_value": 0.001, "weight": 1.24, "status": "active"},
    {"id": "momentum_20d", "win_rate": 0.59, "p_value": 0.003, "weight": 1.18, "status": "active"},
    {"id": "cot_confirms", "win_rate": 0.65, "p_value": 0.0001, "weight": 1.30, "status": "active"},
    {"id": "cot_strong", "win_rate": 0.55, "p_value": 0.02, "weight": 1.10, "status": "active"},
    {"id": "at_level_now", "win_rate": 0.61, "p_value": 0.002, "weight": 1.22, "status": "active"},
    {"id": "htf_level_nearby", "win_rate": 0.57, "p_value": 0.008, "weight": 1.14, "status": "active"},
    {"id": "trend_congruent", "win_rate": 0.60, "p_value": 0.002, "weight": 1.20, "status": "active"},
    {"id": "no_event_risk", "win_rate": 0.53, "p_value": 0.15, "weight": 0.0, "status": "excluded"},
    {"id": "news_confirms", "win_rate": 0.52, "p_value": 0.22, "weight": 0.0, "status": "excluded"},
    {"id": "fund_confirms", "win_rate": 0.63, "p_value": 0.0005, "weight": 1.26, "status": "active"},
    {"id": "bos_confirms", "win_rate": 0.58, "p_value": 0.005, "weight": 1.16, "status": "active"},
    {"id": "smc_struct_confirms", "win_rate": 0.56, "p_value": 0.01, "weight": 1.12, "status": "active"},
    {"id": "order_block", "win_rate": 0.64, "p_value": 0.0003, "weight": 1.28, "status": "active"},
    {"id": "fvg", "win_rate": 0.59, "p_value": 0.004, "weight": 1.18, "status": "active"},
    {"id": "session_alignment", "win_rate": 0.54, "p_value": 0.06, "weight": 0.0, "status": "excluded"},
    {"id": "correlation_clear", "win_rate": 0.57, "p_value": 0.009, "weight": 1.14, "status": "active"},
    {"id": "comex_stress", "win_rate": 0.48, "p_value": 0.35, "weight": 0.0, "status": "excluded"},
    {"id": "seismic_risk", "win_rate": 0.56, "p_value": 0.012, "weight": 1.12, "status": "active"},
    {"id": "chokepoint_clear", "win_rate": 0.55, "p_value": 0.018, "weight": 1.10, "status": "active"},
]

_PLACEHOLDER_WEIGHTS = {s["id"]: s["weight"] for s in _PLACEHOLDER_SIGNALS}


# ── Endpoints ────────────────────────────────────────────────────────────────


@router.get("", summary="Full ensemble health report")
async def get_signal_health() -> dict:
    """Full ensemble health report with per-signal stats."""
    with session_scope() as session:
        state = session.query(PipelineState).first()

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
            "updated_at": state.updated_at.isoformat() if state.updated_at else None,
        }

    # Placeholder fallback
    return {
        "ensemble_quality": "healthy",
        "active_signals": 15,
        "excluded_signals": 4,
        "total_signals": 19,
        "mean_win_rate": 0.58,
        "signals": _PLACEHOLDER_SIGNALS,
        "is_placeholder": True,
    }


@router.get("/weights", summary="Current signal weights")
async def get_signal_weights() -> dict:
    """Current signal weights from the ensemble."""
    with session_scope() as session:
        state = session.query(PipelineState).first()

    if state and state.signal_weights_json:
        return {
            "weights": json.loads(state.signal_weights_json),
            "is_live": True,
        }

    return {"weights": _PLACEHOLDER_WEIGHTS, "is_placeholder": True}


@router.get("/decay-alerts", summary="Decay alerts")
async def get_decay_alerts() -> dict:
    """Signals with decay warnings."""
    with session_scope() as session:
        state = session.query(PipelineState).first()

    if state and state.signal_weights_json:
        weights = json.loads(state.signal_weights_json)
        decayed = [k for k, v in weights.items() if 0 < v < 0.5]
        if decayed:
            return {
                "decayed_signals": decayed,
                "message": f"{len(decayed)} signal(s) showing decay",
            }

    return {"decayed_signals": [], "message": "No signals currently decayed"}
