"""Integration tests for /api/v1/signal-health/* endpoints.

Verifies endpoint behavior with and without Layer 2 data in
pipeline_state.
"""

from __future__ import annotations

import json

from src.db.models import PipelineState


def _seed_pipeline_state(session, with_weights: bool = True):
    """Insert a pipeline_state row with optional signal weights."""
    weights = {
        "sma200": 1.2,
        "cot_confirms": 1.3,
        "at_level_now": 1.1,
        "no_event_risk": 0.0,
        "comex_stress": 0.3,
    }
    state = PipelineState(
        regime="NORMAL",
        vix_price=18.5,
        var_95_pct=0.015,
        signal_weights_json=json.dumps(weights) if with_weights else None,
        ensemble_quality="healthy",
        drift_detected=False,
    )
    session.add(state)
    session.commit()
    return state


async def test_signal_health_with_data(app_client, db_session):
    """GET /signal-health returns live data when pipeline_state exists."""
    _seed_pipeline_state(db_session)
    r = await app_client.get("/api/v1/signal-health")
    assert r.status_code == 200
    body = r.json()
    assert body["is_live"] is True
    assert body["ensemble_quality"] == "healthy"
    # sma200=1.2, cot_confirms=1.3, at_level_now=1.1, comex_stress=0.3 → active
    # no_event_risk=0.0 → excluded
    assert body["active_signals"] == 4
    assert body["excluded_signals"] == 1
    assert body["total_signals"] == 5
    assert "weights" in body
    await app_client.aclose()


async def test_signal_health_empty_db(app_client):
    """GET /signal-health handles empty DB (lazy init may fail gracefully)."""
    r = await app_client.get("/api/v1/signal-health")
    assert r.status_code == 200
    body = r.json()
    assert "ensemble_quality" in body
    await app_client.aclose()


async def test_signal_weights_with_data(app_client, db_session):
    """GET /signal-health/weights returns weight dict when available."""
    _seed_pipeline_state(db_session)
    r = await app_client.get("/api/v1/signal-health/weights")
    assert r.status_code == 200
    body = r.json()
    assert body["is_live"] is True
    assert isinstance(body["weights"], dict)
    assert body["weights"]["sma200"] == 1.2
    await app_client.aclose()


async def test_decay_alerts_with_decayed(app_client, db_session):
    """GET /signal-health/decay-alerts detects decayed signals."""
    _seed_pipeline_state(db_session)
    r = await app_client.get("/api/v1/signal-health/decay-alerts")
    assert r.status_code == 200
    body = r.json()
    # comex_stress has weight=0.3 (0 < 0.3 < 0.5 → decayed)
    assert "comex_stress" in body["decayed_signals"]
    await app_client.aclose()


async def test_decay_alerts_empty(app_client, db_session):
    """GET /signal-health/decay-alerts returns empty when all weights are 0 or >=0.5."""
    weights = {"sma200": 1.2, "no_event_risk": 0.0}
    state = PipelineState(
        signal_weights_json=json.dumps(weights),
        ensemble_quality="healthy",
    )
    db_session.add(state)
    db_session.commit()

    r = await app_client.get("/api/v1/signal-health/decay-alerts")
    assert r.status_code == 200
    body = r.json()
    assert body["decayed_signals"] == []
    await app_client.aclose()
