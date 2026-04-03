"""Execution bridge — routes gate decisions to broker actions.

Handles three automation tiers:
  A+  → auto-execute immediately via broker adapter
  A   → notify + delayed execution (15-minute re-check window)
  B   → notify only, wait for manual POST /approve/{id}
  blocked → reject the signal
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from src.db.models import BotPosition, BotSignal, BotTradeLog, PipelineState
from src.pipeline.gate_orchestrator import GateDecision
from src.trading.bot.lot_sizing import classify_vix

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ExecutionResult:
    """Outcome of routing a single gate decision."""

    signal_id: int
    action: str  # "executed"/"scheduled"/"notified"/"blocked"
    lot_size: float
    broker_order_id: str | None = None
    error: str | None = None


def execute_decisions(
    decisions: list[GateDecision],
    session: Session,
) -> list[ExecutionResult]:
    """Route each gate decision to the appropriate execution path."""
    results: list[ExecutionResult] = []
    for decision in decisions:
        if decision.automation_level == "A+":
            result = _auto_execute(decision, session)
        elif decision.automation_level == "A":
            result = _delayed_execute(decision, session)
        elif decision.automation_level == "B":
            result = _notify_and_wait(decision, session)
        else:
            result = _log_blocked(decision, session)
        results.append(result)

    logger.info(
        "Executed %d decisions: %d auto, %d scheduled, %d notified, %d blocked",
        len(results),
        sum(1 for r in results if r.action == "executed"),
        sum(1 for r in results if r.action == "scheduled"),
        sum(1 for r in results if r.action == "notified"),
        sum(1 for r in results if r.action == "blocked"),
    )
    return results


def _auto_execute(
    decision: GateDecision,
    session: Session,
) -> ExecutionResult:
    """A+ tier: execute immediately via broker adapter."""
    signal = session.get(BotSignal, decision.signal_id)
    if signal is None:
        return ExecutionResult(decision.signal_id, "blocked", 0.0, error="Signal not found")

    try:
        state = session.query(PipelineState).first()
        vix = state.vix_price if state else 20.0
        vix_regime = classify_vix(vix).value

        # Create position record
        position = BotPosition(
            bot_signal_id=signal.id,
            instrument=signal.instrument,
            direction=signal.direction,
            entry_price=signal.entry_price,
            stop_loss=signal.stop_loss,
            target_1=signal.target_1,
            target_2=signal.target_2,
            lot_size=decision.final_lot_size,
            lot_tier="full",
            vix_regime=vix_regime,
            status="open",
        )
        session.add(position)

        # Update signal status
        signal.status = "confirmed"
        signal.confirmed_at = datetime.now(timezone.utc)

        # Audit log
        session.add(BotTradeLog(
            event_type="order_sent",
            details=json.dumps({
                "signal_id": signal.id,
                "instrument": signal.instrument,
                "direction": signal.direction,
                "lot_size": decision.final_lot_size,
                "automation": "A+",
                "gate_count": len(decision.gate_results),
            }),
        ))
        session.flush()

        logger.info(
            "A+ auto-executed: %s %s %.2f lots @ %.5f",
            signal.instrument,
            signal.direction,
            decision.final_lot_size,
            signal.entry_price,
        )
        return ExecutionResult(
            decision.signal_id, "executed", decision.final_lot_size,
            broker_order_id=f"paper_{position.id}",
        )

    except Exception as exc:
        logger.error("A+ execution failed for signal %d: %s", decision.signal_id, exc)
        return ExecutionResult(decision.signal_id, "blocked", 0.0, error=str(exc))


def _delayed_execute(
    decision: GateDecision,
    session: Session,
) -> ExecutionResult:
    """A tier: schedule execution after 15-minute re-check window.

    For now, marks the signal as confirmed with a 15-min note.
    Full APScheduler one-shot integration requires the scheduler instance.
    """
    signal = session.get(BotSignal, decision.signal_id)
    if signal is None:
        return ExecutionResult(decision.signal_id, "blocked", 0.0, error="Signal not found")

    session.add(BotTradeLog(
        event_type="order_scheduled",
        details=json.dumps({
            "signal_id": signal.id,
            "instrument": signal.instrument,
            "lot_size": decision.final_lot_size,
            "automation": "A",
            "delay_minutes": 15,
        }),
    ))
    session.flush()

    logger.info(
        "A scheduled: %s %s %.2f lots (15min delay)",
        signal.instrument,
        signal.direction,
        decision.final_lot_size,
    )
    return ExecutionResult(decision.signal_id, "scheduled", decision.final_lot_size)


def _notify_and_wait(
    decision: GateDecision,
    session: Session,
) -> ExecutionResult:
    """B tier: send notification, wait for manual approval via API."""
    signal = session.get(BotSignal, decision.signal_id)
    if signal is None:
        return ExecutionResult(decision.signal_id, "blocked", 0.0, error="Signal not found")

    session.add(BotTradeLog(
        event_type="signal_notified",
        details=json.dumps({
            "signal_id": signal.id,
            "instrument": signal.instrument,
            "lot_size": decision.final_lot_size,
            "automation": "B",
            "message": "Awaiting manual approval via POST /api/v1/pipeline/approve",
        }),
    ))
    session.flush()

    logger.info(
        "B notified: %s %s %.2f lots (awaiting approval)",
        signal.instrument,
        signal.direction,
        decision.final_lot_size,
    )
    return ExecutionResult(decision.signal_id, "notified", decision.final_lot_size)


def _log_blocked(
    decision: GateDecision,
    session: Session,
) -> ExecutionResult:
    """Blocked: log rejection, no execution."""
    session.add(BotTradeLog(
        event_type="signal_blocked",
        details=json.dumps({
            "signal_id": decision.signal_id,
            "blocking_gate": decision.blocking_gate,
            "automation": "blocked",
        }),
    ))
    session.flush()

    logger.info("Blocked signal %d by gate: %s", decision.signal_id, decision.blocking_gate)
    return ExecutionResult(decision.signal_id, "blocked", 0.0)


def approve_signal(signal_id: int, session: Session) -> ExecutionResult:
    """Manually approve a B-tier signal for execution.

    Called by POST /api/v1/pipeline/approve/{signal_id}.
    """
    signal = session.get(BotSignal, signal_id)
    if signal is None:
        return ExecutionResult(signal_id, "blocked", 0.0, error="Signal not found")
    if signal.status != "pending":
        return ExecutionResult(
            signal_id, "blocked", 0.0,
            error=f"Signal status is '{signal.status}', not pending",
        )
    if signal.automation_level != "B":
        return ExecutionResult(
            signal_id, "blocked", 0.0,
            error=f"Signal automation is '{signal.automation_level}', not B",
        )

    # Parse the gate log to recover the lot size
    lot_size = 0.01
    if signal.gate_log:
        gates = json.loads(signal.gate_log)
        kelly_gate = next((g for g in gates if g["gate_name"] == "kelly_sizing"), None)
        if kelly_gate and "lot=" in kelly_gate.get("reason", ""):
            try:
                lot_str = kelly_gate["reason"].split("lot=")[1].split()[0]
                lot_size = float(lot_str)
            except (IndexError, ValueError):
                pass

    # Execute as if it were A+
    fake_decision = GateDecision(
        signal_id=signal.id,
        passed=True,
        automation_level="A+",
        final_lot_size=lot_size,
    )
    return _auto_execute(fake_decision, session)
