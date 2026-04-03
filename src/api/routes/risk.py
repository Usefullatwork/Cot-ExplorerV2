"""Risk management routes — VaR, stress tests, correlation, regime limits."""

from __future__ import annotations

from fastapi import APIRouter

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


# ── Endpoints ────────────────────────────────────────────────────────────────


@router.get(
    "/var",
    summary="Portfolio Value-at-Risk",
    description=(
        "Returns VaR and CVaR metrics for the current portfolio. "
        "Currently returns placeholder data — real integration with "
        "portfolio_risk module requires live position data."
    ),
)
async def get_portfolio_var() -> dict:
    """Portfolio VaR and CVaR metrics."""
    return {
        "var_95": 1.52,
        "var_99": 2.34,
        "cvar_95": 2.08,
        "cvar_99": 3.15,
        "confidence_levels": [0.95, 0.99],
        "horizon_days": 1,
        "method": "historical_simulation",
        "positions_count": 6,
        "portfolio_notional_usd": 485000,
        "timestamp": "2026-03-31T08:00:00Z",
    }


@router.get(
    "/stress-test",
    summary="Stress test results",
    description="Returns results for 4 pre-defined stress scenarios.",
)
async def get_stress_test() -> dict:
    """Pre-computed stress test results across 4 scenarios."""
    return {
        "scenarios": [
            {
                "name": "2008 GFC Replay",
                "description": "Global financial crisis conditions with extreme VIX",
                "portfolio_impact_pct": -8.4,
                "max_drawdown_pct": -12.1,
                "var_breach": True,
                "surviving_positions": 2,
                "total_positions": 6,
                "status": "fail",
            },
            {
                "name": "USD Flash Crash",
                "description": "Sudden 3% USD depreciation across all pairs",
                "portfolio_impact_pct": -3.2,
                "max_drawdown_pct": -4.8,
                "var_breach": True,
                "surviving_positions": 4,
                "total_positions": 6,
                "status": "fail",
            },
            {
                "name": "Gold Shock +5%",
                "description": "Safe-haven surge with gold rallying 5% intraday",
                "portfolio_impact_pct": 1.8,
                "max_drawdown_pct": -0.9,
                "var_breach": False,
                "surviving_positions": 6,
                "total_positions": 6,
                "status": "pass",
            },
            {
                "name": "Oil Supply Cut",
                "description": "OPEC emergency cut with Brent +12%",
                "portfolio_impact_pct": -1.5,
                "max_drawdown_pct": -2.3,
                "var_breach": False,
                "surviving_positions": 5,
                "total_positions": 6,
                "status": "pass",
            },
        ],
        "run_timestamp": "2026-03-31T08:00:00Z",
    }


@router.get(
    "/correlation-matrix",
    summary="Correlation matrix",
    description="Returns the 14x14 instrument correlation matrix.",
)
async def get_correlation_matrix() -> dict:
    """14x14 correlation matrix across all instruments."""
    return {
        "instruments": _INSTRUMENTS,
        "matrix": _CORR_MATRIX,
        "period_days": 90,
        "method": "pearson",
    }


@router.get(
    "/regime-limits",
    summary="Regime position limits",
    description="Returns current market regime and position sizing limits.",
)
async def get_regime_limits() -> dict:
    """Current regime and position limits."""
    return {
        "current_regime": "NORMAL",
        "max_positions": 8,
        "max_correlated_positions": 3,
        "max_sector_exposure_pct": 40.0,
        "current_positions": 6,
        "current_correlated": 2,
        "current_sector_exposure_pct": 28.5,
        "regime_history": [
            {"regime": "NORMAL", "started": "2026-03-20T00:00:00Z", "duration_days": 11},
            {"regime": "RISK_OFF", "started": "2026-03-15T00:00:00Z", "duration_days": 5},
            {"regime": "NORMAL", "started": "2026-03-01T00:00:00Z", "duration_days": 14},
        ],
    }


@router.post(
    "/run-stress-test",
    summary="Run on-demand stress test",
    description="Execute stress tests on demand. Returns same format as GET.",
)
async def run_stress_test() -> dict:
    """Run stress tests on demand — returns same structure as the GET endpoint."""
    # Delegate to the same data for now
    return await get_stress_test()
