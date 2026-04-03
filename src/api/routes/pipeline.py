"""Pipeline management API routes.

Provides endpoints for monitoring pipeline state, viewing run history,
inspecting gate logs, and manually approving or triggering pipeline runs.
"""

from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException, Query

from src.db.engine import session_scope
from src.db.models import BotSignal, PipelineRun, PipelineState

router = APIRouter(prefix="/api/v1/pipeline", tags=["pipeline"])


@router.get("/status")
async def get_pipeline_status() -> dict:
    """Current pipeline state (Layer 2 cache)."""
    with session_scope() as session:
        state = session.query(PipelineState).first()
        if state is None:
            return {
                "is_placeholder": True,
                "message": "No Layer 2 run yet — run POST /force-layer2",
            }
        return {
            "updated_at": state.updated_at.isoformat() if state.updated_at else None,
            "regime": state.regime,
            "vix_price": state.vix_price,
            "var_95_pct": state.var_95_pct,
            "var_99_pct": state.var_99_pct,
            "cvar_95_pct": state.cvar_95_pct,
            "stress_worst_pct": state.stress_worst_pct,
            "stress_survives": state.stress_survives,
            "correlation_max": state.correlation_max,
            "open_position_count": state.open_position_count,
            "ensemble_quality": state.ensemble_quality,
            "drift_detected": state.drift_detected,
            "account_equity": state.account_equity,
            "layer1_last_run_at": (
                state.layer1_last_run_at.isoformat() if state.layer1_last_run_at else None
            ),
            "layer2_last_run_at": (
                state.layer2_last_run_at.isoformat() if state.layer2_last_run_at else None
            ),
            "heartbeat_at": (
                state.heartbeat_at.isoformat() if state.heartbeat_at else None
            ),
        }


@router.get("/runs")
async def get_pipeline_runs(
    layer: str | None = Query(None, pattern="^(layer1|layer2|retrain)$"),
    limit: int = Query(20, ge=1, le=100),
) -> dict:
    """Recent pipeline run history with optional layer filter."""
    with session_scope() as session:
        query = session.query(PipelineRun).order_by(PipelineRun.started_at.desc())
        if layer:
            query = query.filter(PipelineRun.layer == layer)
        runs = query.limit(limit).all()

        return {
            "count": len(runs),
            "runs": [
                {
                    "id": r.id,
                    "started_at": r.started_at.isoformat() if r.started_at else None,
                    "finished_at": r.finished_at.isoformat() if r.finished_at else None,
                    "layer": r.layer,
                    "status": r.status,
                    "duration_sec": r.duration_sec,
                    "signals_processed": r.signals_processed,
                }
                for r in runs
            ],
        }


@router.get("/gate-log/{signal_id}")
async def get_gate_log(signal_id: int) -> dict:
    """Gate evaluation log for a specific signal."""
    with session_scope() as session:
        signal = session.get(BotSignal, signal_id)
        if signal is None:
            raise HTTPException(404, f"Signal {signal_id} not found")

        gate_log = json.loads(signal.gate_log) if signal.gate_log else []
        return {
            "signal_id": signal.id,
            "instrument": signal.instrument,
            "direction": signal.direction,
            "grade": signal.grade,
            "score": signal.score,
            "status": signal.status,
            "automation_level": signal.automation_level,
            "gate_count": len(gate_log),
            "gates": gate_log,
        }


@router.post("/approve/{signal_id}")
async def approve_signal(signal_id: int) -> dict:
    """Manually approve a B-tier signal for execution."""
    from src.pipeline.execution_bridge import approve_signal as do_approve

    with session_scope() as session:
        result = do_approve(signal_id, session)
        return {
            "signal_id": result.signal_id,
            "action": result.action,
            "lot_size": result.lot_size,
            "broker_order_id": result.broker_order_id,
            "error": result.error,
        }


@router.post("/force-layer2")
async def force_layer2() -> dict:
    """Trigger an immediate Layer 2 run."""
    from src.pipeline.execution_bridge import execute_decisions
    from src.pipeline.gate_orchestrator import process_pending_signals
    from src.pipeline.layer2_runner import run_layer2

    with session_scope() as session:
        layer2_result = run_layer2(session)
        decisions = process_pending_signals(session)
        exec_results = execute_decisions(decisions, session) if decisions else []

        return {
            "layer2": {
                "regime": layer2_result.regime,
                "var_95_pct": layer2_result.var_95_pct,
                "stress_survives": layer2_result.stress_survives,
                "ensemble_quality": layer2_result.ensemble_quality,
            },
            "signals_processed": len(decisions),
            "signals_passed": sum(1 for d in decisions if d.passed),
            "executions": [
                {"signal_id": r.signal_id, "action": r.action, "lot_size": r.lot_size}
                for r in exec_results
            ],
        }
