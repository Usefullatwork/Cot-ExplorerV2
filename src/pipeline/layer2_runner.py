"""Layer 2 runner — reads DB, calls pure analysis functions, caches results.

This is the ONLY pipeline file that performs I/O (database reads/writes).
All computation is delegated to pure functions in ``src/analysis/``.
Results are written to the ``pipeline_state`` singleton row so the gate
orchestrator can read them without re-computing.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from typing import Sequence

from sqlalchemy.orm import Session

from src.analysis.portfolio_risk import (
    compute_portfolio_var,
)
from src.analysis.regime_detector import detect_regime
from src.analysis.risk_parity import inverse_vol_weights
from src.analysis.signal_monitor import get_ensemble_health
from src.analysis.stress_test import Position as StressPosition
from src.analysis.stress_test import run_all_stress_tests
from src.db.models import (
    BotConfig,
    BotPosition,
    PipelineRun,
    PipelineState,
    PriceDaily,
    SignalPerformance,
)

logger = logging.getLogger(__name__)

LOOKBACK_DAYS = 60


@dataclass
class Layer2Result:
    """Summary of a Layer 2 computation run."""

    regime: str
    var_95_pct: float | None
    var_99_pct: float | None
    cvar_95_pct: float | None
    stress_worst_pct: float | None
    stress_survives: bool | None
    ensemble_quality: str | None
    drift_detected: bool
    duration_sec: float


# ---------------------------------------------------------------------------
# Helpers — convert DB rows to analysis-module input formats
# ---------------------------------------------------------------------------


def _compute_daily_returns(closes: Sequence[float]) -> list[float]:
    """Compute simple daily returns from a sequence of close prices."""
    if len(closes) < 2:
        return []
    return [(closes[i] / closes[i - 1]) - 1.0 for i in range(1, len(closes))]


def _positions_to_stress_format(
    positions: list[BotPosition],
) -> list[StressPosition]:
    """Convert open BotPosition rows into stress_test.Position format."""
    result = []
    for pos in positions:
        value = abs(pos.entry_price * pos.lot_size)
        direction = "long" if pos.direction == "bull" else "short"
        result.append(
            StressPosition(
                instrument=pos.instrument,
                direction=direction,
                value_usd=value,
            )
        )
    return result


def _load_vix_data(session: Session) -> tuple[float, float]:
    """Load latest VIX price and 5-day change from PriceDaily.

    Returns (vix_price, vix_5d_change_pct).  Falls back to (20.0, 0.0)
    if no VIX data exists.
    """
    rows = (
        session.query(PriceDaily)
        .filter(PriceDaily.instrument == "VIX")
        .order_by(PriceDaily.date.desc())
        .limit(10)
        .all()
    )
    if not rows:
        return 20.0, 0.0

    latest = rows[0].close
    if len(rows) >= 6:
        older = rows[5].close
        change_pct = ((latest - older) / older) * 100.0 if older else 0.0
    else:
        change_pct = 0.0
    return latest, change_pct


def _load_instrument_5d_change(
    session: Session, instrument: str,
) -> float:
    """Load 5-day price change for an instrument."""
    rows = (
        session.query(PriceDaily)
        .filter(PriceDaily.instrument == instrument)
        .order_by(PriceDaily.date.desc())
        .limit(10)
        .all()
    )
    if len(rows) < 6:
        return 0.0
    latest, older = rows[0].close, rows[5].close
    return ((latest - older) / older) * 100.0 if older else 0.0


def _load_portfolio_returns(
    session: Session, instruments: list[str],
) -> list[float]:
    """Load combined daily returns across all open position instruments."""
    cutoff = (datetime.now(timezone.utc) - timedelta(days=LOOKBACK_DAYS)).strftime(
        "%Y-%m-%d"
    )
    all_returns: list[float] = []
    for inst in instruments:
        closes = [
            r.close
            for r in session.query(PriceDaily)
            .filter(PriceDaily.instrument == inst, PriceDaily.date >= cutoff)
            .order_by(PriceDaily.date.asc())
            .all()
        ]
        all_returns.extend(_compute_daily_returns(closes))
    return all_returns


def _load_signal_outcomes(session: Session) -> dict[str, list[bool]]:
    """Aggregate signal outcomes from SignalPerformance for ensemble health."""
    rows = session.query(SignalPerformance).all()
    outcomes: dict[str, list[bool]] = {}
    for row in rows:
        key = row.signal_type if hasattr(row, "signal_type") else str(row.signal_id)
        if key not in outcomes:
            outcomes[key] = []
        hit = getattr(row, "hit_target", None)
        if hit is not None:
            outcomes[key].append(bool(hit))
    return outcomes


def _load_volatilities(
    session: Session, instruments: list[str],
) -> dict[str, float]:
    """Compute annualised volatility for each instrument from daily returns."""
    cutoff = (datetime.now(timezone.utc) - timedelta(days=LOOKBACK_DAYS)).strftime(
        "%Y-%m-%d"
    )
    vols: dict[str, float] = {}
    for inst in instruments:
        closes = [
            r.close
            for r in session.query(PriceDaily)
            .filter(PriceDaily.instrument == inst, PriceDaily.date >= cutoff)
            .order_by(PriceDaily.date.asc())
            .all()
        ]
        rets = _compute_daily_returns(closes)
        if len(rets) >= 5:
            mean = sum(rets) / len(rets)
            var = sum((r - mean) ** 2 for r in rets) / len(rets)
            vols[inst] = (var ** 0.5) * (252 ** 0.5)  # annualise
        else:
            vols[inst] = 0.15  # default 15% annual vol
    return vols


def _get_or_create_state(session: Session) -> PipelineState:
    """Read or create the singleton pipeline_state row."""
    state = session.query(PipelineState).first()
    if state is None:
        state = PipelineState(updated_at=datetime.now(timezone.utc))
        session.add(state)
        session.flush()
    return state


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def run_layer2(session: Session) -> Layer2Result:
    """Execute Layer 2: read DB, compute portfolio metrics, cache results.

    This function is called by the scheduler (daily) or on-demand via the
    ``/api/v1/pipeline/force-layer2`` endpoint.
    """
    t0 = time.time()

    # Audit row
    run = PipelineRun(
        started_at=datetime.now(timezone.utc),
        layer="layer2",
        status="running",
    )
    session.add(run)
    session.flush()

    try:
        result = _execute_layer2(session)

        run.status = "ok"
        run.finished_at = datetime.now(timezone.utc)
        run.duration_sec = round(time.time() - t0, 2)
        run.details_json = json.dumps(asdict(result), default=str)
        session.commit()

        logger.info(
            "Layer 2 complete in %.1fs: regime=%s var95=%.4f stress_survives=%s",
            result.duration_sec,
            result.regime,
            result.var_95_pct or 0,
            result.stress_survives,
        )
        return result

    except Exception as exc:
        run.status = "error"
        run.finished_at = datetime.now(timezone.utc)
        run.duration_sec = round(time.time() - t0, 2)
        run.details_json = json.dumps({"error": str(exc)})
        session.commit()
        logger.error("Layer 2 failed: %s", exc)
        raise


def _execute_layer2(session: Session) -> Layer2Result:
    """Core computation — separated for testability."""
    state = _get_or_create_state(session)

    # 1. Load open positions
    positions = (
        session.query(BotPosition).filter(BotPosition.status == "open").all()
    )
    instruments = list({p.instrument for p in positions})
    state.open_position_count = len(positions)

    # 2. Regime detection
    vix_price, vix_5d = _load_vix_data(session)
    oil_5d = _load_instrument_5d_change(session, "Brent")
    dxy_5d = _load_instrument_5d_change(session, "DXY")
    regime = detect_regime(vix_price, vix_5d, oil_5d, [], dxy_5d)
    state.regime = regime.value
    state.vix_price = vix_price

    # 3. Portfolio VaR
    returns = _load_portfolio_returns(session, instruments)
    if len(returns) >= 10:
        var_result = compute_portfolio_var(returns)
        state.var_95_pct = var_result.var_95
        state.var_99_pct = var_result.var_99
        state.cvar_95_pct = var_result.cvar_95
    else:
        state.var_95_pct = None
        state.var_99_pct = None
        state.cvar_95_pct = None

    # 4. Stress testing
    if positions:
        config = session.query(BotConfig).first()
        equity = config.risk_pct * 100_000 if config else 10_000.0
        stress_positions = _positions_to_stress_format(positions)
        stress_results, survives, _msg = run_all_stress_tests(
            stress_positions, equity,
        )
        worst = max((r.total_loss_pct for r in stress_results), default=0.0)
        state.stress_worst_pct = worst
        state.stress_survives = survives
    else:
        state.stress_worst_pct = None
        state.stress_survives = True

    # 5. Signal ensemble health
    outcomes = _load_signal_outcomes(session)
    if outcomes:
        health = get_ensemble_health(outcomes)
        state.ensemble_quality = health.quality
        weights_dict = {w.signal_id: w.weight for w in health.weights}
        state.signal_weights_json = json.dumps(weights_dict)
    else:
        state.ensemble_quality = "healthy"
        state.signal_weights_json = None

    # 6. Risk parity
    if instruments:
        vols = _load_volatilities(session, instruments)
        if vols:
            rp = inverse_vol_weights(vols)
            state.risk_parity_json = json.dumps(rp.weights)
    else:
        state.risk_parity_json = None

    # 7. Correlation max
    if len(instruments) >= 2:
        # Use portfolio_risk correlation for the first two instruments
        all_returns_map: dict[str, list[float]] = {}
        cutoff = (
            datetime.now(timezone.utc) - timedelta(days=LOOKBACK_DAYS)
        ).strftime("%Y-%m-%d")
        for inst in instruments:
            closes = [
                r.close
                for r in session.query(PriceDaily)
                .filter(PriceDaily.instrument == inst, PriceDaily.date >= cutoff)
                .order_by(PriceDaily.date.asc())
                .all()
            ]
            all_returns_map[inst] = _compute_daily_returns(closes)

        max_corr = 0.0
        inst_list = list(all_returns_map.keys())
        for i in range(len(inst_list)):
            for j in range(i + 1, len(inst_list)):
                a, b = all_returns_map[inst_list[i]], all_returns_map[inst_list[j]]
                min_len = min(len(a), len(b))
                if min_len >= 10:
                    from src.analysis.portfolio_risk import pearson_correlation

                    corr = abs(pearson_correlation(a[:min_len], b[:min_len]))
                    max_corr = max(max_corr, corr)
        state.correlation_max = max_corr
    else:
        state.correlation_max = 0.0

    # 8. Drift detection
    drift_detected = False
    if outcomes:
        for sig_id, results in outcomes.items():
            mid = len(results) // 2
            if mid >= 10:
                from src.analysis.drift_detector import detect_signal_accuracy_drift

                drift = detect_signal_accuracy_drift(results[mid:], results[:mid])
                if drift.drift_detected:
                    drift_detected = True
                    break
    state.drift_detected = drift_detected

    # 9. Account equity from config
    config = session.query(BotConfig).first()
    if config:
        state.account_equity = config.risk_pct * 100_000
        state.peak_equity = state.account_equity

    state.layer2_last_run_at = datetime.now(timezone.utc)
    state.updated_at = datetime.now(timezone.utc)

    return Layer2Result(
        regime=state.regime or "normal",
        var_95_pct=state.var_95_pct,
        var_99_pct=state.var_99_pct,
        cvar_95_pct=state.cvar_95_pct,
        stress_worst_pct=state.stress_worst_pct,
        stress_survives=state.stress_survives,
        ensemble_quality=state.ensemble_quality,
        drift_detected=drift_detected,
        duration_sec=0.0,  # filled by caller
    )
