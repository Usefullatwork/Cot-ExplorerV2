"""Risk management routes — VaR, stress tests, correlation, regime limits.

Reads live data from pipeline_state.  If no Layer 2 run has occurred,
triggers on-demand computation.  Correlation matrix is computed from
real daily returns.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter

from src.db.engine import session_ctx
from src.db.models import PipelineState, PriceDaily

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/risk", tags=["risk"])

_INSTRUMENTS = [
    "EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCHF", "USDNOK",
    "Gold", "Silver", "Brent", "WTI", "SPX", "NAS100", "VIX", "DXY",
]


# ── Helpers ──────────────────────────────────────────────────────────────────


def _ensure_layer2() -> PipelineState | None:
    """Return PipelineState, running Layer 2 on-demand if needed."""
    with session_ctx() as session:
        state = session.query(PipelineState).first()
        if state and state.var_95_pct is not None:
            return state

    try:
        from src.pipeline.layer2_runner import run_layer2

        logger.info("risk: triggering on-demand Layer 2")
        with session_ctx() as session:
            run_layer2(session)
            return session.query(PipelineState).first()
    except Exception:
        logger.warning("On-demand Layer 2 failed", exc_info=True)
        return None


def _compute_correlation_matrix() -> tuple[list[str], list[list[float]]]:
    """Compute Pearson correlation matrix from 90 days of daily returns."""
    cutoff = (
        datetime.now(timezone.utc) - timedelta(days=90)
    ).strftime("%Y-%m-%d")

    with session_ctx() as session:
        rows = (
            session.query(PriceDaily)
            .filter(
                PriceDaily.instrument.in_(_INSTRUMENTS),
                PriceDaily.date >= cutoff,
            )
            .order_by(PriceDaily.instrument, PriceDaily.date.asc())
            .all()
        )

    # Group closes by instrument
    closes: dict[str, list[float]] = {}
    for row in rows:
        closes.setdefault(row.instrument, []).append(row.close)

    # Compute returns
    returns: dict[str, list[float]] = {}
    for inst, prices in closes.items():
        if len(prices) >= 10:
            returns[inst] = [
                (prices[i] / prices[i - 1]) - 1.0
                for i in range(1, len(prices))
            ]

    # Use only instruments with enough data, preserving order
    present = [i for i in _INSTRUMENTS if i in returns]
    if len(present) < 2:
        return present, [[1.0] * len(present) for _ in present]

    from src.analysis.signal_propagation import _pearson

    n = len(present)
    matrix: list[list[float]] = []
    for i in range(n):
        row: list[float] = []
        for j in range(n):
            if i == j:
                row.append(1.0)
            else:
                a = returns[present[i]]
                b = returns[present[j]]
                min_len = min(len(a), len(b))
                corr = _pearson(a[:min_len], b[:min_len])
                row.append(round(corr, 2))
        matrix.append(row)

    return present, matrix


# ── Endpoints ────────────────────────────────────────────────────────────────


@router.get("/var", summary="Portfolio Value-at-Risk")
async def get_portfolio_var() -> dict:
    """Portfolio VaR and CVaR — live from pipeline_state."""
    state = _ensure_layer2()

    if state and state.var_95_pct is not None:
        return {
            "var_95": round(state.var_95_pct * 100, 2),
            "var_99": (
                round(state.var_99_pct * 100, 2)
                if state.var_99_pct else None
            ),
            "cvar_95": (
                round(state.cvar_95_pct * 100, 2)
                if state.cvar_95_pct else None
            ),
            "confidence_levels": [0.95, 0.99],
            "horizon_days": 1,
            "method": "historical_simulation",
            "positions_count": state.open_position_count or 0,
            "is_live": True,
            "updated_at": (
                state.updated_at.isoformat() if state.updated_at else None
            ),
        }

    return {
        "var_95": None,
        "var_99": None,
        "cvar_95": None,
        "confidence_levels": [0.95, 0.99],
        "horizon_days": 1,
        "method": "historical_simulation",
        "positions_count": 0,
        "is_live": False,
        "message": "No price data available — run the pipeline first",
    }


@router.get("/stress-test", summary="Stress test results")
async def get_stress_test() -> dict:
    """Stress test results — live from pipeline_state."""
    state = _ensure_layer2()

    if state and state.stress_worst_pct is not None:
        return {
            "worst_scenario_loss_pct": round(state.stress_worst_pct, 2),
            "survives_all": state.stress_survives,
            "positions_count": state.open_position_count or 0,
            "is_live": True,
            "updated_at": (
                state.updated_at.isoformat() if state.updated_at else None
            ),
        }

    return {
        "worst_scenario_loss_pct": None,
        "survives_all": None,
        "positions_count": 0,
        "is_live": False,
        "message": "No positions to stress test",
    }


@router.get("/correlation-matrix", summary="Correlation matrix")
async def get_correlation_matrix() -> dict:
    """NxN Pearson correlation matrix from 90 days of daily returns."""
    instruments, matrix = _compute_correlation_matrix()
    return {
        "instruments": instruments,
        "matrix": matrix,
        "period_days": 90,
        "method": "pearson",
        "is_live": len(instruments) > 0,
    }


@router.get("/regime-limits", summary="Regime position limits")
async def get_regime_limits() -> dict:
    """Current regime and position limits — live."""
    state = _ensure_layer2()

    if state and state.regime:
        from src.analysis.portfolio_risk import _DEFAULT_REGIME_LIMITS

        max_pos = _DEFAULT_REGIME_LIMITS.get(state.regime, 5)
        return {
            "current_regime": state.regime.upper(),
            "max_positions": max_pos,
            "current_positions": state.open_position_count or 0,
            "is_live": True,
            "updated_at": (
                state.updated_at.isoformat() if state.updated_at else None
            ),
        }

    return {
        "current_regime": "NORMAL",
        "max_positions": 5,
        "current_positions": 0,
        "is_live": False,
        "message": "No regime data — run the pipeline first",
    }


@router.post("/run-stress-test", summary="Run on-demand stress test")
async def run_stress_test() -> dict:
    """Run stress tests on demand against open positions."""
    from src.analysis.stress_test import Position, run_all_stress_tests
    from src.db.models import BotPosition

    with session_ctx() as session:
        positions = (
            session.query(BotPosition)
            .filter(BotPosition.status.in_(["open", "partial"]))
            .all()
        )
        if not positions:
            return {
                "message": "No open positions to stress test",
                "scenarios": [],
            }

        stress_positions = [
            Position(
                instrument=p.instrument,
                direction="long" if p.direction == "bull" else "short",
                value_usd=abs(p.entry_price * p.lot_size),
            )
            for p in positions
        ]
        results, survives, msg = run_all_stress_tests(
            stress_positions, 10_000.0,
        )

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
