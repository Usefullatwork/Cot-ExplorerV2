"""Friday portfolio rebalancing logic.

Computes signal decay, closing decisions, target allocations, and
generates concrete rebalance recommendations for weekly review.

All functions are pure -- no I/O, no DB, no side effects.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum

# ---------------------------------------------------------------------------
# Enums and data classes
# ---------------------------------------------------------------------------


class RebalanceAction(str, Enum):
    """Types of rebalance actions."""

    HOLD = "hold"
    REDUCE = "reduce"
    CLOSE = "close"
    OPEN = "open"
    INCREASE = "increase"


@dataclass(frozen=True)
class PositionState:
    """Current state of a held position."""

    instrument: str
    direction: str          # "long" or "short"
    entry_score: int        # score at entry time
    current_score: int      # current score
    entry_date: str         # when opened
    days_held: int
    current_pnl_pips: float
    lot_size: float


@dataclass(frozen=True)
class RebalanceRecommendation:
    """A single rebalance action recommendation."""

    instrument: str
    action: RebalanceAction
    reason: str
    current_lots: float
    target_lots: float
    urgency: str            # "immediate", "next_session", "optional"


@dataclass(frozen=True)
class RebalanceReport:
    """Complete weekly rebalance report."""

    recommendations: list[RebalanceRecommendation]
    n_close: int
    n_reduce: int
    n_hold: int
    n_open: int
    total_positions: int


# ---------------------------------------------------------------------------
# Signal decay
# ---------------------------------------------------------------------------


def compute_signal_decay(
    current_score: int,
    entry_score: int,
    days_held: int,
    half_life_days: float = 14.0,
) -> float:
    """Compute signal decay factor (0.0-1.0).

    Combines score deterioration and time decay:
    score_factor = current_score / max(entry_score, 1)
    time_factor = 2^(-days_held / half_life_days)
    decay = score_factor * time_factor
    Clamped to [0.0, 1.0].

    Args:
        current_score: Current confluence score.
        entry_score: Score at time of entry.
        days_held: Number of days the position has been held.
        half_life_days: Half-life for time decay (default 14 days).

    Returns:
        Decay factor between 0.0 (fully decayed) and 1.0 (no decay).
    """
    score_factor = current_score / max(entry_score, 1)
    time_factor = math.pow(2.0, -days_held / half_life_days)
    decay = score_factor * time_factor
    return max(0.0, min(1.0, decay))


# ---------------------------------------------------------------------------
# Close decision
# ---------------------------------------------------------------------------


def should_close_position(
    position: PositionState,
    decay_threshold: float = 0.3,
    max_holding_days: int = 30,
) -> tuple[bool, str]:
    """Determine if a position should be closed.

    Close if:
    1. Signal reversed (current_score < 3 for original direction)
    2. Signal decayed below threshold
    3. Held longer than max_holding_days
    4. Position deeply underwater (pnl < -100 pips) AND score < 5

    Args:
        position: Current position state.
        decay_threshold: Close if decay factor drops below this.
        max_holding_days: Maximum days to hold a position.

    Returns:
        (should_close, reason) tuple.
    """
    # 1. Signal reversal
    if position.current_score < 3:
        return True, (
            f"Signal reversed: current_score={position.current_score} < 3"
        )

    # 2. Signal decay
    decay = compute_signal_decay(
        position.current_score,
        position.entry_score,
        position.days_held,
    )
    if decay < decay_threshold:
        return True, (
            f"Signal decayed: factor={decay:.3f} < threshold={decay_threshold}"
        )

    # 3. Max holding period
    if position.days_held > max_holding_days:
        return True, (
            f"Max hold exceeded: {position.days_held} days > {max_holding_days}"
        )

    # 4. Underwater + weak score
    if position.current_pnl_pips < -100.0 and position.current_score < 5:
        return True, (
            f"Underwater ({position.current_pnl_pips:.0f} pips) "
            f"with weak score ({position.current_score})"
        )

    return False, "Position healthy"


# ---------------------------------------------------------------------------
# Target allocation
# ---------------------------------------------------------------------------


def compute_target_allocations(
    signals: dict[str, dict],
    regime: str,
    kelly_fractions: dict[str, float] | None = None,
    max_positions: int = 5,
) -> dict[str, float]:
    """Compute target allocation weights for instruments with active signals.

    Args:
        signals: {instrument: {"score": int, "direction": str, "grade": str}}.
        regime: Market regime string (affects minimum score threshold).
        kelly_fractions: Optional {instrument: kelly_fraction} for weighting.
        max_positions: Maximum number of positions to hold.

    Steps:
    1. Filter to instruments with score >= 6 (minimum B grade)
    2. Rank by score descending
    3. Take top max_positions
    4. If kelly_fractions provided: weight by kelly; else weight by score
    5. Normalize weights to sum to 1.0

    Returns:
        {instrument: weight} normalized to sum to 1.0.
        Empty dict if no signals qualify.
    """
    # Filter to instruments above threshold
    qualified = {
        inst: info
        for inst, info in signals.items()
        if info.get("score", 0) >= 6
    }

    if not qualified:
        return {}

    # Rank by score descending, take top N
    ranked = sorted(
        qualified.items(),
        key=lambda x: x[1].get("score", 0),
        reverse=True,
    )[:max_positions]

    # Compute raw weights
    if kelly_fractions:
        raw: dict[str, float] = {}
        for inst, info in ranked:
            kf = kelly_fractions.get(inst, 0.0)
            # Fall back to score-based if no kelly fraction
            raw[inst] = kf if kf > 0.0 else info.get("score", 0)
    else:
        raw = {inst: info.get("score", 0) for inst, info in ranked}

    total = sum(raw.values())
    if total <= 0.0:
        return {}

    return {inst: w / total for inst, w in raw.items()}


# ---------------------------------------------------------------------------
# Rebalance action generation
# ---------------------------------------------------------------------------


def generate_rebalance_actions(
    current_positions: list[PositionState],
    target_allocations: dict[str, float],
    equity: float,
    regime: str,
    decay_threshold: float = 0.3,
    max_holding_days: int = 30,
) -> RebalanceReport:
    """Generate rebalance recommendations.

    For each current position:
    1. Check if should close (signal decay, max hold, reversal)
    2. If instrument in target: compare current vs target allocation
    3. If instrument NOT in target: recommend close

    For instruments in target but not currently held:
    4. Recommend open with target lot size

    Urgency:
    - "immediate": close/reduce for risk reasons
    - "next_session": open/increase
    - "optional": small adjustments

    Args:
        current_positions: List of currently held positions.
        target_allocations: {instrument: weight} from compute_target_allocations.
        equity: Account equity for sizing.
        regime: Market regime string.
        decay_threshold: Close threshold for signal decay.
        max_holding_days: Maximum hold period.

    Returns:
        RebalanceReport with all recommendations.
    """
    recommendations: list[RebalanceRecommendation] = []
    held_instruments: set[str] = set()

    # Process current positions
    for pos in current_positions:
        held_instruments.add(pos.instrument)
        close, reason = should_close_position(
            pos, decay_threshold, max_holding_days,
        )

        if close:
            recommendations.append(RebalanceRecommendation(
                instrument=pos.instrument,
                action=RebalanceAction.CLOSE,
                reason=reason,
                current_lots=pos.lot_size,
                target_lots=0.0,
                urgency="immediate",
            ))
            continue

        if pos.instrument not in target_allocations:
            recommendations.append(RebalanceRecommendation(
                instrument=pos.instrument,
                action=RebalanceAction.CLOSE,
                reason="Instrument no longer in target allocation",
                current_lots=pos.lot_size,
                target_lots=0.0,
                urgency="immediate",
            ))
            continue

        # Instrument still in target -- compare allocation
        target_weight = target_allocations[pos.instrument]
        # Approximate target lots from weight and equity
        target_lots = round(target_weight * equity / 10_000.0, 2)

        if pos.lot_size > target_lots * 1.2:
            recommendations.append(RebalanceRecommendation(
                instrument=pos.instrument,
                action=RebalanceAction.REDUCE,
                reason=(
                    f"Over-allocated: {pos.lot_size:.2f} lots "
                    f"> target {target_lots:.2f}"
                ),
                current_lots=pos.lot_size,
                target_lots=target_lots,
                urgency="optional",
            ))
        elif pos.lot_size < target_lots * 0.8:
            recommendations.append(RebalanceRecommendation(
                instrument=pos.instrument,
                action=RebalanceAction.INCREASE,
                reason=(
                    f"Under-allocated: {pos.lot_size:.2f} lots "
                    f"< target {target_lots:.2f}"
                ),
                current_lots=pos.lot_size,
                target_lots=target_lots,
                urgency="next_session",
            ))
        else:
            recommendations.append(RebalanceRecommendation(
                instrument=pos.instrument,
                action=RebalanceAction.HOLD,
                reason="Within target allocation range",
                current_lots=pos.lot_size,
                target_lots=target_lots,
                urgency="optional",
            ))

    # New positions to open
    for inst, weight in target_allocations.items():
        if inst in held_instruments:
            continue
        target_lots = round(weight * equity / 10_000.0, 2)
        recommendations.append(RebalanceRecommendation(
            instrument=inst,
            action=RebalanceAction.OPEN,
            reason=f"New target allocation: weight={weight:.4f}",
            current_lots=0.0,
            target_lots=target_lots,
            urgency="next_session",
        ))

    # Count by action type
    n_close = sum(1 for r in recommendations if r.action == RebalanceAction.CLOSE)
    n_reduce = sum(
        1 for r in recommendations if r.action == RebalanceAction.REDUCE
    )
    n_hold = sum(1 for r in recommendations if r.action == RebalanceAction.HOLD)
    n_open = sum(1 for r in recommendations if r.action == RebalanceAction.OPEN)

    return RebalanceReport(
        recommendations=recommendations,
        n_close=n_close,
        n_reduce=n_reduce,
        n_hold=n_hold,
        n_open=n_open,
        total_positions=len(current_positions) + n_open,
    )
