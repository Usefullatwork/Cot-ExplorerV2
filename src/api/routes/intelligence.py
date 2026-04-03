"""Intelligence routes — sentiment, propagation, attribution, microstructure."""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(prefix="/api/v1/intelligence", tags=["intelligence"])


# ── Endpoints ────────────────────────────────────────────────────────────────


@router.get(
    "/sentiment",
    summary="Per-instrument sentiment scores",
    description=(
        "Returns NLP sentiment scores per instrument ranging from -1 (bearish) "
        "to +1 (bullish). Currently returns placeholder data."
    ),
)
async def get_sentiment() -> dict:
    """Per-instrument sentiment scores from NLP pipeline."""
    return {
        "scores": [
            {"instrument": "EURUSD", "score": 0.32, "label": "bullish", "sources": 14},
            {"instrument": "GBPUSD", "score": -0.18, "label": "bearish", "sources": 11},
            {"instrument": "USDJPY", "score": 0.45, "label": "bullish", "sources": 18},
            {"instrument": "AUDUSD", "score": -0.05, "label": "neutral", "sources": 8},
            {"instrument": "USDCHF", "score": -0.22, "label": "bearish", "sources": 9},
            {"instrument": "USDNOK", "score": 0.12, "label": "neutral", "sources": 6},
            {"instrument": "Gold", "score": 0.68, "label": "bullish", "sources": 22},
            {"instrument": "Silver", "score": 0.55, "label": "bullish", "sources": 15},
            {"instrument": "Brent", "score": -0.35, "label": "bearish", "sources": 19},
            {"instrument": "WTI", "score": -0.28, "label": "bearish", "sources": 17},
            {"instrument": "SPX", "score": 0.15, "label": "neutral", "sources": 25},
            {"instrument": "NAS100", "score": 0.22, "label": "bullish", "sources": 23},
            {"instrument": "VIX", "score": -0.42, "label": "bearish", "sources": 12},
            {"instrument": "DXY", "score": -0.10, "label": "neutral", "sources": 20},
        ],
        "model": "nlp_sentiment_v1",
        "timestamp": "2026-03-31T08:00:00Z",
    }


@router.get(
    "/propagation",
    summary="Signal propagation edges",
    description="Returns signal propagation graph edges showing how signals flow between instruments.",
)
async def get_propagation() -> dict:
    """Signal propagation edges with lag and strength."""
    return {
        "edges": [
            {"source": "DXY", "target": "EURUSD", "lag_hours": 2, "strength": 0.85, "direction": "inverse"},
            {"source": "DXY", "target": "Gold", "lag_hours": 1, "strength": 0.72, "direction": "inverse"},
            {"source": "VIX", "target": "SPX", "lag_hours": 0, "strength": 0.91, "direction": "inverse"},
            {"source": "VIX", "target": "USDJPY", "lag_hours": 1, "strength": 0.65, "direction": "inverse"},
            {"source": "Gold", "target": "Silver", "lag_hours": 0, "strength": 0.88, "direction": "direct"},
            {"source": "Brent", "target": "WTI", "lag_hours": 0, "strength": 0.95, "direction": "direct"},
            {"source": "SPX", "target": "NAS100", "lag_hours": 0, "strength": 0.92, "direction": "direct"},
            {"source": "EURUSD", "target": "GBPUSD", "lag_hours": 1, "strength": 0.78, "direction": "direct"},
            {"source": "Gold", "target": "USDCHF", "lag_hours": 3, "strength": 0.58, "direction": "inverse"},
            {"source": "Brent", "target": "USDNOK", "lag_hours": 4, "strength": 0.62, "direction": "direct"},
            {"source": "VIX", "target": "Gold", "lag_hours": 2, "strength": 0.55, "direction": "direct"},
            {"source": "DXY", "target": "AUDUSD", "lag_hours": 1, "strength": 0.70, "direction": "inverse"},
        ],
        "total_nodes": 14,
        "total_edges": 12,
    }


@router.get(
    "/attribution",
    summary="Performance attribution",
    description="Returns performance attribution breakdown by signal, regime, and sizing.",
)
async def get_attribution() -> dict:
    """Performance attribution — per-signal PnL, regime breakdown, sizing alpha."""
    return {
        "signal_pnl": [
            {"signal": "sma200", "pnl_r": 4.2, "trades": 28, "win_rate": 0.62},
            {"signal": "momentum_20d", "pnl_r": 3.1, "trades": 35, "win_rate": 0.59},
            {"signal": "cot_confirms", "pnl_r": 6.8, "trades": 22, "win_rate": 0.65},
            {"signal": "cot_strong", "pnl_r": 1.5, "trades": 18, "win_rate": 0.55},
            {"signal": "at_level_now", "pnl_r": 5.2, "trades": 30, "win_rate": 0.61},
            {"signal": "htf_level_nearby", "pnl_r": 2.8, "trades": 25, "win_rate": 0.57},
            {"signal": "trend_congruent", "pnl_r": 4.5, "trades": 32, "win_rate": 0.60},
            {"signal": "no_event_risk", "pnl_r": -0.8, "trades": 15, "win_rate": 0.53},
            {"signal": "news_confirms", "pnl_r": -1.2, "trades": 12, "win_rate": 0.52},
            {"signal": "fund_confirms", "pnl_r": 5.9, "trades": 20, "win_rate": 0.63},
            {"signal": "bos_confirms", "pnl_r": 3.4, "trades": 26, "win_rate": 0.58},
            {"signal": "smc_struct_confirms", "pnl_r": 2.2, "trades": 24, "win_rate": 0.56},
            {"signal": "order_block", "pnl_r": 6.1, "trades": 19, "win_rate": 0.64},
            {"signal": "fvg", "pnl_r": 3.3, "trades": 27, "win_rate": 0.59},
            {"signal": "session_alignment", "pnl_r": -0.5, "trades": 14, "win_rate": 0.54},
            {"signal": "correlation_clear", "pnl_r": 2.6, "trades": 23, "win_rate": 0.57},
            {"signal": "comex_stress", "pnl_r": -2.1, "trades": 10, "win_rate": 0.48},
            {"signal": "seismic_risk", "pnl_r": 1.9, "trades": 16, "win_rate": 0.56},
            {"signal": "chokepoint_clear", "pnl_r": 1.4, "trades": 17, "win_rate": 0.55},
        ],
        "regime_performance": [
            {"regime": "NORMAL", "pnl_r": 38.2, "trades": 180, "win_rate": 0.61, "avg_rr": 1.45},
            {"regime": "RISK_OFF", "pnl_r": 5.8, "trades": 45, "win_rate": 0.54, "avg_rr": 1.12},
            {"regime": "CRISIS", "pnl_r": -3.2, "trades": 15, "win_rate": 0.40, "avg_rr": 0.85},
            {"regime": "WAR_FOOTING", "pnl_r": 2.1, "trades": 12, "win_rate": 0.50, "avg_rr": 1.05},
            {"regime": "ENERGY_SHOCK", "pnl_r": 4.5, "trades": 20, "win_rate": 0.58, "avg_rr": 1.30},
            {"regime": "SANCTIONS", "pnl_r": 1.8, "trades": 8, "win_rate": 0.52, "avg_rr": 1.10},
        ],
        "sizing_alpha": {
            "full_size_pnl_r": 32.5,
            "half_size_pnl_r": 12.8,
            "quarter_size_pnl_r": 3.9,
            "sizing_contribution_pct": 18.4,
            "description": "Position sizing added 18.4% to total PnL vs equal sizing",
        },
        "total_pnl_r": 49.2,
        "total_trades": 280,
    }


@router.get(
    "/microstructure",
    summary="Microstructure liquidity scores",
    description="Returns liquidity scores and optimal execution windows per instrument.",
)
async def get_microstructure() -> dict:
    """Liquidity scores and execution windows per instrument."""
    return {
        "instruments": [
            {"instrument": "EURUSD", "liquidity_score": 0.95, "spread_bps": 0.8, "optimal_window": "London-NY overlap", "depth_rank": 1},
            {"instrument": "GBPUSD", "liquidity_score": 0.88, "spread_bps": 1.2, "optimal_window": "London session", "depth_rank": 3},
            {"instrument": "USDJPY", "liquidity_score": 0.92, "spread_bps": 0.9, "optimal_window": "Tokyo-London overlap", "depth_rank": 2},
            {"instrument": "AUDUSD", "liquidity_score": 0.78, "spread_bps": 1.5, "optimal_window": "Sydney-Tokyo overlap", "depth_rank": 5},
            {"instrument": "USDCHF", "liquidity_score": 0.82, "spread_bps": 1.3, "optimal_window": "London session", "depth_rank": 4},
            {"instrument": "USDNOK", "liquidity_score": 0.55, "spread_bps": 4.2, "optimal_window": "London 08-12 UTC", "depth_rank": 12},
            {"instrument": "Gold", "liquidity_score": 0.85, "spread_bps": 2.0, "optimal_window": "London-NY overlap", "depth_rank": 6},
            {"instrument": "Silver", "liquidity_score": 0.72, "spread_bps": 3.5, "optimal_window": "London-NY overlap", "depth_rank": 8},
            {"instrument": "Brent", "liquidity_score": 0.80, "spread_bps": 2.5, "optimal_window": "London session", "depth_rank": 7},
            {"instrument": "WTI", "liquidity_score": 0.78, "spread_bps": 2.8, "optimal_window": "NY session", "depth_rank": 9},
            {"instrument": "SPX", "liquidity_score": 0.90, "spread_bps": 1.0, "optimal_window": "NY 14:30-21:00 UTC", "depth_rank": 3},
            {"instrument": "NAS100", "liquidity_score": 0.88, "spread_bps": 1.2, "optimal_window": "NY 14:30-21:00 UTC", "depth_rank": 4},
            {"instrument": "VIX", "liquidity_score": 0.65, "spread_bps": 5.0, "optimal_window": "NY session", "depth_rank": 10},
            {"instrument": "DXY", "liquidity_score": 0.60, "spread_bps": 4.5, "optimal_window": "London-NY overlap", "depth_rank": 11},
        ],
        "timestamp": "2026-03-31T08:00:00Z",
    }
