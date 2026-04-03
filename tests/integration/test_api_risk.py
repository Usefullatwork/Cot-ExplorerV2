"""Integration tests for /api/v1/risk/* endpoints.

Verifies VaR, stress-test, correlation-matrix, and regime-limits
endpoints return computed data when pipeline_state is populated.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from src.db.models import (
    Instrument,
    PipelineState,
    PriceDaily,
)


def _seed_pipeline_state(session):
    """Insert pipeline_state with risk metrics."""
    state = PipelineState(
        regime="NORMAL",
        vix_price=18.5,
        var_95_pct=0.015,
        var_99_pct=0.023,
        cvar_95_pct=0.020,
        stress_worst_pct=-5.2,
        stress_survives=True,
        open_position_count=2,
    )
    session.add(state)
    session.commit()


def _seed_prices_for_correlation(session):
    """Seed daily prices for 3 instruments (30 days) for correlation calc."""
    import math

    instruments_data = [
        ("EURUSD", 1.10),
        ("GBPUSD", 1.30),
        ("Gold", 2000.0),
    ]
    for key, base in instruments_data:
        session.add(
            Instrument(
                key=key, name=key, symbol=f"{key}=X", label="Test",
                category="test", class_="A", session="London", active=True,
            )
        )
        price = base
        for i in range(30):
            date = (
                datetime.now(timezone.utc) - timedelta(days=30 - i)
            ).strftime("%Y-%m-%d")
            change = math.sin(i * 0.3 + hash(key) % 50) * 0.003
            price *= 1.0 + change
            session.add(
                PriceDaily(
                    instrument=key, date=date,
                    high=price * 1.003, low=price * 0.997, close=price,
                )
            )
    session.commit()


# ── VaR ──────────────────────────────────────────────────────────────────────


async def test_var_with_data(app_client, db_session):
    """GET /risk/var returns live VaR when pipeline_state has data."""
    _seed_pipeline_state(db_session)
    r = await app_client.get("/api/v1/risk/var")
    assert r.status_code == 200
    body = r.json()
    assert body["is_live"] is True
    assert body["var_95"] == 1.5  # 0.015 * 100 = 1.5
    assert body["var_99"] == 2.3
    assert body["positions_count"] == 2
    await app_client.aclose()


async def test_var_empty_db(app_client):
    """GET /risk/var handles empty DB gracefully."""
    r = await app_client.get("/api/v1/risk/var")
    assert r.status_code == 200
    body = r.json()
    assert "var_95" in body
    await app_client.aclose()


# ── Stress test ──────────────────────────────────────────────────────────────


async def test_stress_test_with_data(app_client, db_session):
    """GET /risk/stress-test returns live results when data exists."""
    _seed_pipeline_state(db_session)
    r = await app_client.get("/api/v1/risk/stress-test")
    assert r.status_code == 200
    body = r.json()
    assert body["is_live"] is True
    assert body["worst_scenario_loss_pct"] == -5.2
    assert body["survives_all"] is True
    await app_client.aclose()


async def test_stress_test_empty_db(app_client):
    """GET /risk/stress-test handles empty DB gracefully."""
    r = await app_client.get("/api/v1/risk/stress-test")
    assert r.status_code == 200
    await app_client.aclose()


# ── Correlation matrix ───────────────────────────────────────────────────────


async def test_correlation_matrix_with_prices(app_client, db_session):
    """GET /risk/correlation-matrix computes from real price data."""
    _seed_prices_for_correlation(db_session)
    r = await app_client.get("/api/v1/risk/correlation-matrix")
    assert r.status_code == 200
    body = r.json()
    assert body["is_live"] is True
    assert body["method"] == "pearson"
    assert body["period_days"] == 90
    # Should have instruments with data
    assert len(body["instruments"]) >= 3
    matrix = body["matrix"]
    n = len(body["instruments"])
    assert len(matrix) == n
    # Diagonal should be 1.0
    for i in range(n):
        assert matrix[i][i] == 1.0
    # Symmetric
    for i in range(n):
        for j in range(n):
            assert matrix[i][j] == matrix[j][i]
    await app_client.aclose()


async def test_correlation_matrix_empty_db(app_client):
    """GET /risk/correlation-matrix handles empty DB."""
    r = await app_client.get("/api/v1/risk/correlation-matrix")
    assert r.status_code == 200
    body = r.json()
    assert "instruments" in body
    assert "matrix" in body
    await app_client.aclose()


# ── Regime limits ────────────────────────────────────────────────────────────


async def test_regime_limits_with_data(app_client, db_session):
    """GET /risk/regime-limits returns live regime when data exists."""
    _seed_pipeline_state(db_session)
    r = await app_client.get("/api/v1/risk/regime-limits")
    assert r.status_code == 200
    body = r.json()
    assert body["is_live"] is True
    assert body["current_regime"] == "NORMAL"
    assert body["current_positions"] == 2
    await app_client.aclose()


async def test_regime_limits_empty_db(app_client):
    """GET /risk/regime-limits handles empty DB gracefully."""
    r = await app_client.get("/api/v1/risk/regime-limits")
    assert r.status_code == 200
    body = r.json()
    assert "current_regime" in body
    await app_client.aclose()


# ── Run stress test ──────────────────────────────────────────────────────────


async def test_run_stress_test_no_positions(app_client):
    """POST /risk/run-stress-test returns empty when no open positions."""
    r = await app_client.post("/api/v1/risk/run-stress-test")
    assert r.status_code == 200
    body = r.json()
    assert body["scenarios"] == []
    assert "No open positions" in body["message"]
    await app_client.aclose()
