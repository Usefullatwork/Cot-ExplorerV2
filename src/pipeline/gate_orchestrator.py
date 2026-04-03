"""Gate orchestrator — 8-gate chain-of-responsibility for signal validation.

For each pending BotSignal, the gate chain reads cached Layer 2 state
from ``pipeline_state`` and runs 8 sequential gates.  The chain stops
on the first blocking gate.  Passing signals receive a lot size and
automation level (A+/A/B).

All heavy computation (VaR, stress, Kelly) is done by Layer 2; the gates
here are lightweight threshold checks against cached values.
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field

from sqlalchemy.orm import Session

from src.analysis.kelly import kelly_position_size
from src.analysis.portfolio_risk import (
    check_var_gate,
    compute_regime_position_limit,
)
from src.db.models import BotConfig, BotPosition, BotSignal, PipelineState
from src.trading.bot.config import CORRELATED_PAIRS, LOT_PARAMS
from src.trading.bot.lot_sizing import calculate_lot_size

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class GateResult:
    """Result of a single gate evaluation."""

    gate_name: str
    passed: bool
    reason: str
    size_multiplier: float = 1.0


@dataclass(frozen=True)
class GateDecision:
    """Final decision after running all gates on a signal."""

    signal_id: int
    passed: bool
    automation_level: str  # "A+"/"A"/"B"/"blocked"
    final_lot_size: float
    gate_results: list[GateResult] = field(default_factory=list)
    blocking_gate: str | None = None


# ---------------------------------------------------------------------------
# Individual gates
# ---------------------------------------------------------------------------


def _gate_kill_switch(config: BotConfig) -> GateResult:
    """Gate 1: Master kill switch."""
    if config and config.kill_switch_active:
        reason = config.kill_switch_reason or "Kill switch active"
        return GateResult("kill_switch", False, reason, 0.0)
    return GateResult("kill_switch", True, "Kill switch off")


def _gate_signal_health(
    signal: BotSignal, state: PipelineState | None,
) -> GateResult:
    """Gate 2: Is the signal's underlying strategy still healthy?"""
    if state is None or not state.signal_weights_json:
        return GateResult("signal_health", True, "No weight data — pass conservatively")

    weights = json.loads(state.signal_weights_json)
    # Look up by instrument or signal source
    weight = weights.get(signal.instrument, 1.0)

    if weight <= 0.0:
        return GateResult("signal_health", False, f"Signal weight 0 for {signal.instrument}", 0.0)
    if weight < 0.5:
        return GateResult("signal_health", True, f"Degraded weight {weight:.2f}", 0.7)
    return GateResult("signal_health", True, f"Healthy weight {weight:.2f}")


def _gate_var(state: PipelineState | None) -> GateResult:
    """Gate 3: Portfolio VaR must be below 2%."""
    if state is None or state.var_95_pct is None:
        return GateResult("var_gate", True, "No VaR data — pass conservatively")

    passed, reason = check_var_gate(state.var_95_pct)
    return GateResult("var_gate", passed, reason, 1.0 if passed else 0.0)


def _gate_stress(state: PipelineState | None) -> GateResult:
    """Gate 4: Portfolio must survive all stress scenarios."""
    if state is None or state.stress_survives is None:
        return GateResult("stress_gate", True, "No stress data — pass conservatively")

    if not state.stress_survives:
        return GateResult(
            "stress_gate", False,
            f"Worst scenario loss {state.stress_worst_pct:.1f}% exceeds 15%", 0.0,
        )
    return GateResult("stress_gate", True, f"Stress OK (worst {state.stress_worst_pct:.1f}%)")


def _gate_regime(state: PipelineState | None) -> GateResult:
    """Gate 5: Regime-based position limit."""
    if state is None or state.regime is None:
        return GateResult("regime_gate", True, "No regime data — pass conservatively")

    limits = compute_regime_position_limit(
        state.regime, state.open_position_count or 0,
    )
    if not limits.can_open:
        return GateResult("regime_gate", False, limits.reason, 0.0)
    return GateResult("regime_gate", True, limits.reason)


def _gate_correlation(
    signal: BotSignal, session: Session,
) -> GateResult:
    """Gate 6: No overexposure to correlated instruments."""
    correlated = CORRELATED_PAIRS.get(signal.instrument, [])
    if not correlated:
        return GateResult("correlation_gate", True, "No correlated pairs")

    open_positions = (
        session.query(BotPosition)
        .filter(BotPosition.status.in_(["open", "partial"]))
        .all()
    )
    open_instruments = {p.instrument for p in open_positions}
    overlap = open_instruments & set(correlated)

    if overlap:
        return GateResult(
            "correlation_gate", True,
            f"Correlated with {overlap} — size reduced",
            0.5,
        )
    return GateResult("correlation_gate", True, "No correlation conflict")


def _gate_kelly(
    signal: BotSignal,
    state: PipelineState | None,
    equity: float,
) -> tuple[GateResult, float]:
    """Gate 7: Kelly criterion position sizing.

    Returns (gate_result, raw_lot_size).
    """
    params = LOT_PARAMS.get(signal.instrument)
    if params is None:
        return GateResult("kelly_sizing", True, "Unknown instrument — use fallback"), 0.0

    # Try Kelly from cached trade stats
    kelly_cache = {}
    if state and state.kelly_cache_json:
        kelly_cache = json.loads(state.kelly_cache_json)

    if signal.instrument in kelly_cache:
        kf = kelly_cache[signal.instrument]
        lot = kelly_position_size(
            account_equity=equity,
            win_rate=kf.get("win_rate", 0.5),
            avg_win=kf.get("avg_win", 1.0),
            avg_loss=kf.get("avg_loss", 1.0),
            entry_price=signal.entry_price,
            stop_loss=signal.stop_loss,
            pip_size=params.pip_size,
            pip_value_per_lot=params.pip_value_per_lot,
        )
        if lot > 0:
            return GateResult("kelly_sizing", True, f"Kelly lot={lot:.2f}"), lot

    # Fallback to VIX×grade matrix
    vix = state.vix_price if state and state.vix_price else 20.0
    lot = calculate_lot_size(
        account_balance=equity,
        risk_pct=0.01,
        entry=signal.entry_price,
        stop_loss=signal.stop_loss,
        vix=vix,
        grade=signal.grade,
        instrument=signal.instrument,
    )
    reason = f"Fallback lot={lot:.2f}" if lot > 0 else "Blocked by VIX×grade"
    return GateResult("kelly_sizing", lot > 0, reason, 1.0 if lot > 0 else 0.0), lot


def _gate_risk_parity(
    signal: BotSignal,
    state: PipelineState | None,
    lot_size: float,
) -> GateResult:
    """Gate 8: Clamp lot so no position exceeds 30% allocation."""
    if state is None or not state.risk_parity_json:
        return GateResult("risk_parity_clamp", True, "No parity data — pass")

    weights = json.loads(state.risk_parity_json)
    max_weight = weights.get(signal.instrument, 0.30)

    if max_weight < 0.30:
        clamp = max_weight / 0.30
        return GateResult(
            "risk_parity_clamp", True,
            f"Clamped to {clamp:.0%} of full size (weight={max_weight:.2f})",
            clamp,
        )
    return GateResult("risk_parity_clamp", True, "Within parity bounds")


# ---------------------------------------------------------------------------
# Automation level assignment
# ---------------------------------------------------------------------------


def _assign_automation_level(
    signal: BotSignal,
    gate_results: list[GateResult],
    has_pipeline_state: bool,
) -> str:
    """Determine automation tier from signal quality and gate outcomes."""
    if not has_pipeline_state:
        return "B"  # Manual approval when no Layer 2 data exists

    min_mult = min(g.size_multiplier for g in gate_results)

    if (
        signal.grade == "A+"
        and signal.score >= 9
        and min_mult >= 0.9
    ):
        return "A+"
    if signal.score >= 7 and min_mult >= 0.7:
        return "A"
    return "B"


# ---------------------------------------------------------------------------
# Main entry points
# ---------------------------------------------------------------------------


def evaluate_signal(
    signal: BotSignal,
    state: PipelineState | None,
    config: BotConfig | None,
    session: Session,
) -> GateDecision:
    """Run 8 gates on a single signal, return GateDecision."""
    equity = 10_000.0
    if config:
        equity = config.risk_pct * 100_000

    gates: list[GateResult] = []

    # Gate 1: Kill switch
    g = _gate_kill_switch(config)
    gates.append(g)
    if not g.passed:
        return GateDecision(signal.id, False, "blocked", 0.0, gates, g.gate_name)

    # Gate 2: Signal health
    g = _gate_signal_health(signal, state)
    gates.append(g)
    if not g.passed:
        return GateDecision(signal.id, False, "blocked", 0.0, gates, g.gate_name)

    # Gate 3: VaR
    g = _gate_var(state)
    gates.append(g)
    if not g.passed:
        return GateDecision(signal.id, False, "blocked", 0.0, gates, g.gate_name)

    # Gate 4: Stress
    g = _gate_stress(state)
    gates.append(g)
    if not g.passed:
        return GateDecision(signal.id, False, "blocked", 0.0, gates, g.gate_name)

    # Gate 5: Regime
    g = _gate_regime(state)
    gates.append(g)
    if not g.passed:
        return GateDecision(signal.id, False, "blocked", 0.0, gates, g.gate_name)

    # Gate 6: Correlation
    g = _gate_correlation(signal, session)
    gates.append(g)
    if not g.passed:
        return GateDecision(signal.id, False, "blocked", 0.0, gates, g.gate_name)

    # Gate 7: Kelly sizing
    kelly_gate, raw_lot = _gate_kelly(signal, state, equity)
    gates.append(kelly_gate)
    if not kelly_gate.passed:
        return GateDecision(signal.id, False, "blocked", 0.0, gates, kelly_gate.gate_name)

    # Gate 8: Risk parity clamp
    g = _gate_risk_parity(signal, state, raw_lot)
    gates.append(g)

    # Apply all multipliers to the raw lot
    final_lot = raw_lot
    for gate in gates:
        final_lot *= gate.size_multiplier

    has_state = state is not None and state.var_95_pct is not None
    auto_level = _assign_automation_level(signal, gates, has_state)

    return GateDecision(
        signal_id=signal.id,
        passed=True,
        automation_level=auto_level,
        final_lot_size=round(final_lot, 4),
        gate_results=gates,
    )


def process_pending_signals(session: Session) -> list[GateDecision]:
    """Evaluate all pending BotSignals through the gate chain.

    Writes ``gate_log`` and ``automation_level`` back to each BotSignal row.
    """
    state = session.query(PipelineState).first()
    config = session.query(BotConfig).first()

    pending = (
        session.query(BotSignal)
        .filter(BotSignal.status == "pending")
        .order_by(BotSignal.received_at.asc())
        .all()
    )

    if not pending:
        logger.info("No pending signals to gate")
        return []

    decisions: list[GateDecision] = []
    for signal in pending:
        decision = evaluate_signal(signal, state, config, session)
        decisions.append(decision)

        # Write audit trail to BotSignal
        signal.gate_log = json.dumps(
            [asdict(g) for g in decision.gate_results], default=str,
        )
        signal.automation_level = decision.automation_level

        if not decision.passed:
            signal.status = "rejected"
            signal.rejection_reason = (
                f"Blocked by gate: {decision.blocking_gate}"
            )

    session.flush()
    logger.info(
        "Gated %d signals: %d passed, %d blocked",
        len(decisions),
        sum(1 for d in decisions if d.passed),
        sum(1 for d in decisions if not d.passed),
    )
    return decisions
