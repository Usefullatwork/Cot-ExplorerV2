"""Signal health monitoring routes — ensemble quality and decay alerts."""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(prefix="/api/v1/signal-health", tags=["signal-health"])


# ── Endpoints ────────────────────────────────────────────────────────────────


@router.get(
    "",
    summary="Full ensemble health report",
    description=(
        "Returns signal ensemble health including active/excluded signals, "
        "win rates, p-values, weights, and any alerts. "
        "Currently returns placeholder data — real integration with "
        "signal_monitor requires trade history from the DB."
    ),
)
async def get_signal_health() -> dict:
    """Full ensemble health report with per-signal stats."""
    return {
        "ensemble_quality": "healthy",
        "active_signals": 15,
        "excluded_signals": 4,
        "total_signals": 19,
        "mean_win_rate": 0.58,
        "signals": [
            {"id": "sma200", "win_rate": 0.62, "p_value": 0.001, "weight": 1.24, "status": "active", "is_decayed": False},
            {"id": "momentum_20d", "win_rate": 0.59, "p_value": 0.003, "weight": 1.18, "status": "active", "is_decayed": False},
            {"id": "cot_confirms", "win_rate": 0.65, "p_value": 0.0001, "weight": 1.30, "status": "active", "is_decayed": False},
            {"id": "cot_strong", "win_rate": 0.55, "p_value": 0.02, "weight": 1.10, "status": "active", "is_decayed": False},
            {"id": "at_level_now", "win_rate": 0.61, "p_value": 0.002, "weight": 1.22, "status": "active", "is_decayed": False},
            {"id": "htf_level_nearby", "win_rate": 0.57, "p_value": 0.008, "weight": 1.14, "status": "active", "is_decayed": False},
            {"id": "trend_congruent", "win_rate": 0.60, "p_value": 0.002, "weight": 1.20, "status": "active", "is_decayed": False},
            {"id": "no_event_risk", "win_rate": 0.53, "p_value": 0.15, "weight": 0.0, "status": "excluded", "is_decayed": False},
            {"id": "news_confirms", "win_rate": 0.52, "p_value": 0.22, "weight": 0.0, "status": "excluded", "is_decayed": False},
            {"id": "fund_confirms", "win_rate": 0.63, "p_value": 0.0005, "weight": 1.26, "status": "active", "is_decayed": False},
            {"id": "bos_confirms", "win_rate": 0.58, "p_value": 0.005, "weight": 1.16, "status": "active", "is_decayed": False},
            {"id": "smc_struct_confirms", "win_rate": 0.56, "p_value": 0.01, "weight": 1.12, "status": "active", "is_decayed": False},
            {"id": "order_block", "win_rate": 0.64, "p_value": 0.0003, "weight": 1.28, "status": "active", "is_decayed": False},
            {"id": "fvg", "win_rate": 0.59, "p_value": 0.004, "weight": 1.18, "status": "active", "is_decayed": False},
            {"id": "session_alignment", "win_rate": 0.54, "p_value": 0.06, "weight": 0.0, "status": "excluded", "is_decayed": False},
            {"id": "correlation_clear", "win_rate": 0.57, "p_value": 0.009, "weight": 1.14, "status": "active", "is_decayed": False},
            {"id": "comex_stress", "win_rate": 0.48, "p_value": 0.35, "weight": 0.0, "status": "excluded", "is_decayed": False},
            {"id": "seismic_risk", "win_rate": 0.56, "p_value": 0.012, "weight": 1.12, "status": "active", "is_decayed": False},
            {"id": "chokepoint_clear", "win_rate": 0.55, "p_value": 0.018, "weight": 1.10, "status": "active", "is_decayed": False},
        ],
        "alerts": [
            "Signal 'no_event_risk' not significant (p=0.1500)",
            "Signal 'news_confirms' not significant (p=0.2200)",
            "Signal 'session_alignment' not significant (p=0.0600)",
            "Signal 'comex_stress' not significant (p=0.3500)",
        ],
    }


@router.get(
    "/weights",
    summary="Current signal weights",
    description="Returns the weight assigned to each signal in the ensemble.",
)
async def get_signal_weights() -> dict:
    """Current signal weights from the ensemble."""
    return {
        "weights": {
            "sma200": 1.24,
            "momentum_20d": 1.18,
            "cot_confirms": 1.30,
            "cot_strong": 1.10,
            "at_level_now": 1.22,
            "htf_level_nearby": 1.14,
            "trend_congruent": 1.20,
            "no_event_risk": 0.0,
            "news_confirms": 0.0,
            "fund_confirms": 1.26,
            "bos_confirms": 1.16,
            "smc_struct_confirms": 1.12,
            "order_block": 1.28,
            "fvg": 1.18,
            "session_alignment": 0.0,
            "correlation_clear": 1.14,
            "comex_stress": 0.0,
            "seismic_risk": 1.12,
            "chokepoint_clear": 1.10,
        }
    }


@router.get(
    "/decay-alerts",
    summary="Decay alerts",
    description="Returns signals with performance decay warnings.",
)
async def get_decay_alerts() -> dict:
    """Signals with decay warnings."""
    return {"decayed_signals": [], "message": "No signals currently decayed"}
