"""Risk management routes — VaR, stress tests, correlation, regime limits.

Reads live data from pipeline_state when available, falls back to
placeholder data when no Layer 2 run has occurred yet.
"""

from __future__ import annotations

from fastapi import APIRouter

from src.db.engine import session_scope
from src.db.models import PipelineState

router = APIRouter(prefix="/api/v1/risk", tags=["risk"])

# ── Instrument universe for correlation matrix ───────────────────────────────

_INSTRUMENTS = [
    "EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCHF", "USDNOK",
    "Gold", "Silver", "Brent", "WTI", "SPX", "NAS100", "VIX", "DXY",
]

# Pre-computed placeholder correlation matrix (14x14, symmetric, diag=1.0)
_CORR_MATRIX = [
    [1.00,  0.82, -0.31,  0.67, -0.85, -0.48,  0.42,  0.38, -0.12, -0.15,  0.18,  0.22, -0.25, -0.91],
    [0.82,  1.00, -0.24,  0.55, -0.72, -0.39,  0.35,  0.30, -0.08, -0.10,  0.14,  0.18, -0.20, -0.78],
    [-0.31, -0.24,  1.00, -0.18,  0.45,  0.22, -0.15, -0.12,  0.05,  0.07, -0.08, -0.10,  0.12,  0.35],
    [0.67,  0.55, -0.18,  1.00, -0.58, -0.32,  0.28,  0.25,  0.15,  0.12,  0.20,  0.25, -0.18, -0.62],
    [-0.85, -0.72,  0.45, -0.58,  1.00,  0.52, -0.38, -0.33,  0.10,  0.12, -0.15, -0.18,  0.22,  0.88],
    [-0.48, -0.39,  0.22, -0.32,  0.52,  1.00, -0.20, -0.18,  0.25,  0.22, -0.10, -0.12,  0.15,  0.50],
    [0.42,  0.35, -0.15,  0.28, -0.38, -0.20,  1.00,  0.88, -0.05, -0.08,  0.10,  0.08, -0.12, -0.45],
    [0.38,  0.30, -0.12,  0.25, -0.33, -0.18,  0.88,  1.00, -0.03, -0.05,  0.08,  0.06, -0.10, -0.40],
    [-0.12, -0.08,  0.05,  0.15,  0.10,  0.25, -0.05, -0.03,  1.00,  0.95, -0.05, -0.03,  0.08,  0.10],
    [-0.15, -0.10,  0.07,  0.12,  0.12,  0.22, -0.08, -0.05,  0.95,  1.00, -0.03, -0.02,  0.06,  0.12],
    [0.18,  0.14, -0.08,  0.20, -0.15, -0.10,  0.10,  0.08, -0.05, -0.03,  1.00,  0.92, -0.75, -0.22],
    [0.22,  0.18, -0.10,  0.25, -0.18, -0.12,  0.08,  0.06, -0.03, -0.02,  0.92,  1.00, -0.70, -0.25],
    [-0.25, -0.20,  0.12, -0.18,  0.22,  0.15, -0.12, -0.10,  0.08,  0.06, -0.75, -0.70,  1.00,  0.28],
    [-0.91, -0.78,  0.35, -0.62,  0.88,  0.50, -0.45, -0.40,  0.10,  0.12, -0.22, -0.25,  0.28,  1.00],
]


def _load_state():
    """Load pipeline state, return None if no row exists."""
    with session_scope() as session:
        return session.query(PipelineState).first()


# ── Endpoints ────────────────────────────────────────────────────────────────


@router.get("/var", summary="Portfolio Value-at-Risk")
async def get_portfolio_var() -> dict:
    """Portfolio VaR and CVaR — live from pipeline_state or placeholder."""
    with session_scope() as session:
        state = session.query(PipelineState).first()

    if state and state.var_95_pct is not None:
        return {
            "var_95": round(state.var_95_pct * 100, 2),
            "var_99": round(state.var_99_pct * 100, 2) if state.var_99_pct else None,
            "cvar_95": round(state.cvar_95_pct * 100, 2) if state.cvar_95_pct else None,
            "confidence_levels": [0.95, 0.99],
            "horizon_days": 1,
            "method": "historical_simulation",
            "positions_count": state.open_position_count or 0,
            "is_live": True,
            "updated_at": state.updated_at.isoformat() if state.updated_at else None,
        }

    return {
        "var_95": 1.52,
        "var_99": 2.34,
        "cvar_95": 2.08,
        "cvar_99": 3.15,
        "confidence_levels": [0.95, 0.99],
        "horizon_days": 1,
        "method": "historical_simulation",
        "positions_count": 0,
        "is_placeholder": True,
    }


@router.get("/stress-test", summary="Stress test results")
async def get_stress_test() -> dict:
    """Stress test results — live from pipeline_state or placeholder."""
    with session_scope() as session:
        state = session.query(PipelineState).first()

    if state and state.stress_worst_pct is not None:
        return {
            "worst_scenario_loss_pct": round(state.stress_worst_pct, 2),
            "survives_all": state.stress_survives,
            "positions_count": state.open_position_count or 0,
            "is_live": True,
            "updated_at": state.updated_at.isoformat() if state.updated_at else None,
        }

    return {
        "scenarios": [
            {
                "name": "2008 GFC Replay",
                "portfolio_impact_pct": -8.4,
                "status": "fail",
            },
            {
                "name": "USD Flash Crash",
                "portfolio_impact_pct": -3.2,
                "status": "fail",
            },
            {
                "name": "Gold Shock +5%",
                "portfolio_impact_pct": 1.8,
                "status": "pass",
            },
            {
                "name": "Oil Supply Cut",
                "portfolio_impact_pct": -1.5,
                "status": "pass",
            },
        ],
        "is_placeholder": True,
    }


@router.get("/correlation-matrix", summary="Correlation matrix")
async def get_correlation_matrix() -> dict:
    """14x14 correlation matrix across all instruments."""
    return {
        "instruments": _INSTRUMENTS,
        "matrix": _CORR_MATRIX,
        "period_days": 90,
        "method": "pearson",
    }


@router.get("/regime-limits", summary="Regime position limits")
async def get_regime_limits() -> dict:
    """Current regime and position limits — live or placeholder."""
    with session_scope() as session:
        state = session.query(PipelineState).first()

    if state and state.regime:
        from src.analysis.portfolio_risk import _DEFAULT_REGIME_LIMITS

        max_pos = _DEFAULT_REGIME_LIMITS.get(state.regime, 5)
        return {
            "current_regime": state.regime.upper(),
            "max_positions": max_pos,
            "current_positions": state.open_position_count or 0,
            "is_live": True,
            "updated_at": state.updated_at.isoformat() if state.updated_at else None,
        }

    return {
        "current_regime": "NORMAL",
        "max_positions": 5,
        "current_positions": 0,
        "is_placeholder": True,
    }


@router.post("/run-stress-test", summary="Run on-demand stress test")
async def run_stress_test() -> dict:
    """Run stress tests on demand — delegates to Layer 2 if available."""
    from src.analysis.stress_test import Position, run_all_stress_tests
    from src.db.models import BotPosition

    with session_scope() as session:
        positions = (
            session.query(BotPosition)
            .filter(BotPosition.status.in_(["open", "partial"]))
            .all()
        )
        if not positions:
            return {"message": "No open positions to stress test", "scenarios": []}

        stress_positions = [
            Position(
                instrument=p.instrument,
                direction="long" if p.direction == "bull" else "short",
                value_usd=abs(p.entry_price * p.lot_size),
            )
            for p in positions
        ]
        results, survives, msg = run_all_stress_tests(stress_positions, 10_000.0)

        return {
            "scenarios": [
                {
                    "name": r.scenario_name,
                    "description": r.description,
                    "total_loss_pct": round(r.total_loss_pct, 2),
                    "worst_instrument": r.worst_instrument,
                    "survives": r.survives,
                }
                for r in results
            ],
            "survives_all": survives,
            "message": msg,
            "is_live": True,
        }
