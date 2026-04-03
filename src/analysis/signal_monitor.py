"""Real-time ensemble health monitoring with weighted scoring.

Uses signal_statistics.py functions (binomial_p_value, bonferroni_alpha,
signal_decay_check) to compute per-signal weights, ensemble health
reports, regime-adjusted weights, and CUSUM change detection.

All functions are pure -- no I/O, no DB, no side effects.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from src.analysis.signal_statistics import (
    binomial_p_value,
    bonferroni_alpha,
    signal_decay_check,
)

# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class SignalWeight:
    """Computed weight for a single signal."""

    signal_id: str
    weight: float          # 0.0-2.0 (0 = excluded, 1 = normal, >1 = above average)
    p_value: float
    is_significant: bool
    is_decayed: bool
    win_rate: float
    n_trades: int


@dataclass(frozen=True)
class EnsembleHealthReport:
    """Dashboard-ready ensemble health report."""

    signal_weights: list[SignalWeight]
    active_count: int           # signals passing significance + not decayed
    excluded_count: int         # signals failing tests
    total_signals: int
    mean_win_rate: float
    ensemble_quality: str       # "healthy", "degraded", "critical"
    alerts: list[str]           # human-readable alert messages


# ---------------------------------------------------------------------------
# Default regime multipliers
# ---------------------------------------------------------------------------

_DEFAULT_REGIME_MULTIPLIERS: dict[str, dict[str, float]] = {
    "NORMAL": {"default": 1.0},
    "RISK_OFF": {
        "cot_confirms": 1.5,
        "fund_confirms": 1.5,
        "bos_confirms": 0.5,
        "default": 1.0,
    },
    "CRISIS": {
        "cot_confirms": 1.0,
        "fund_confirms": 1.0,
        "default": 0.3,
    },
}


# ---------------------------------------------------------------------------
# Core functions
# ---------------------------------------------------------------------------

def compute_signal_weights(
    signal_outcomes: dict[str, Sequence[bool]],
    min_trades: int = 30,
    base_alpha: float = 0.05,
    n_signals: int = 19,
    decay_window: int = 20,
    decay_threshold: float = 0.45,
) -> list[SignalWeight]:
    """Compute per-signal weights based on statistical significance.

    For each signal:
    1. If n_trades < min_trades: weight=1.0 (insufficient data, keep default)
    2. Compute p-value via binomial_p_value(wins, total)
    3. Check decay via signal_decay_check(outcomes, decay_window, decay_threshold)
    4. If significant AND not decayed: weight = win_rate / 0.5 (normalize around 50%)
    5. If not significant: weight = 0.0 (excluded)
    6. If decayed: weight = 0.5 (reduced, not excluded)
    7. Clamp weights to [0.0, 2.0]

    Uses bonferroni_alpha(base_alpha, n_signals) as significance threshold.

    Args:
        signal_outcomes: {signal_id: [bool outcomes per trade]}.
        min_trades: Minimum trades before weighting kicks in.
        base_alpha: Family-wise error rate for Bonferroni correction.
        n_signals: Number of signals for Bonferroni denominator.
        decay_window: Recent window size for decay check.
        decay_threshold: Win rate below this = decayed.

    Returns:
        List of SignalWeight, sorted by signal_id.
    """
    adj_alpha = bonferroni_alpha(base_alpha, n_signals)
    weights: list[SignalWeight] = []

    for sig_id in sorted(signal_outcomes.keys()):
        outcomes = signal_outcomes[sig_id]
        n_trades = len(outcomes)
        wins = sum(1 for o in outcomes if o)
        win_rate = wins / n_trades if n_trades > 0 else 0.0

        # Insufficient data -- keep default weight
        if n_trades < min_trades:
            weights.append(SignalWeight(
                signal_id=sig_id,
                weight=1.0,
                p_value=1.0,
                is_significant=False,
                is_decayed=False,
                win_rate=win_rate,
                n_trades=n_trades,
            ))
            continue

        p_val = binomial_p_value(wins, n_trades)
        is_significant = p_val < adj_alpha
        is_decayed, _ = signal_decay_check(outcomes, decay_window, decay_threshold)

        # Determine weight
        if is_decayed:
            weight = 0.5
        elif is_significant:
            weight = win_rate / 0.5
        else:
            weight = 0.0

        # Clamp to [0.0, 2.0]
        weight = max(0.0, min(2.0, weight))

        weights.append(SignalWeight(
            signal_id=sig_id,
            weight=weight,
            p_value=p_val,
            is_significant=is_significant,
            is_decayed=is_decayed,
            win_rate=win_rate,
            n_trades=n_trades,
        ))

    return weights


def get_ensemble_health(
    signal_outcomes: dict[str, Sequence[bool]],
    min_trades: int = 30,
    base_alpha: float = 0.05,
    decay_window: int = 20,
    decay_threshold: float = 0.45,
) -> EnsembleHealthReport:
    """Full dashboard-ready health report.

    ensemble_quality:
    - "healthy": active_count >= 12
    - "degraded": 6 <= active_count < 12
    - "critical": active_count < 6

    Generates alerts for:
    - Each decayed signal: "Signal {id} has decayed (win rate {rate:.1%})"
    - Each excluded signal: "Signal {id} not significant (p={p:.4f})"
    - Critical ensemble: "CRITICAL: Only {n} signals active, minimum 6 recommended"

    Args:
        signal_outcomes: {signal_id: [bool outcomes per trade]}.
        min_trades: Minimum trades before weighting kicks in.
        base_alpha: Family-wise error rate for Bonferroni correction.
        decay_window: Recent window size for decay check.
        decay_threshold: Win rate below this = decayed.

    Returns:
        EnsembleHealthReport with weights, counts, quality, and alerts.
    """
    n_signals = len(signal_outcomes)
    weights = compute_signal_weights(
        signal_outcomes,
        min_trades=min_trades,
        base_alpha=base_alpha,
        n_signals=n_signals,
        decay_window=decay_window,
        decay_threshold=decay_threshold,
    )

    active_count = sum(
        1 for w in weights
        if w.is_significant and not w.is_decayed
    )
    excluded_count = sum(
        1 for w in weights
        if w.weight == 0.0 and w.n_trades >= min_trades
    )

    win_rates = [w.win_rate for w in weights if w.n_trades > 0]
    mean_win_rate = sum(win_rates) / len(win_rates) if win_rates else 0.0

    if active_count >= 12:
        quality = "healthy"
    elif active_count >= 6:
        quality = "degraded"
    else:
        quality = "critical"

    alerts: list[str] = []
    for w in weights:
        if w.is_decayed:
            alerts.append(
                f"Signal {w.signal_id} has decayed (win rate {w.win_rate:.1%})"
            )
        elif w.weight == 0.0 and w.n_trades >= min_trades:
            alerts.append(
                f"Signal {w.signal_id} not significant (p={w.p_value:.4f})"
            )

    if quality == "critical":
        alerts.append(
            f"CRITICAL: Only {active_count} signals active, "
            f"minimum 6 recommended"
        )

    return EnsembleHealthReport(
        signal_weights=weights,
        active_count=active_count,
        excluded_count=excluded_count,
        total_signals=n_signals,
        mean_win_rate=mean_win_rate,
        ensemble_quality=quality,
        alerts=alerts,
    )


def compute_regime_weights(
    base_weights: list[SignalWeight],
    regime: str,
    regime_multipliers: dict[str, dict[str, float]] | None = None,
) -> list[SignalWeight]:
    """Apply regime-specific weight multipliers.

    Default multipliers:
    - NORMAL: all signals x1.0
    - RISK_OFF: cot_confirms x1.5, fund_confirms x1.5, bos_confirms x0.5
    - CRISIS: all x0.3 except cot_confirms x1.0, fund_confirms x1.0

    For unknown regimes, all signals keep their base weight (x1.0).

    Args:
        base_weights: Pre-computed signal weights.
        regime: Market regime string (e.g. "NORMAL", "RISK_OFF", "CRISIS").
        regime_multipliers: Optional override for default multipliers.

    Returns:
        New list with adjusted weights (re-clamped to [0.0, 2.0]).
    """
    multipliers = regime_multipliers or _DEFAULT_REGIME_MULTIPLIERS
    regime_map = multipliers.get(regime.upper(), {"default": 1.0})
    default_mult = regime_map.get("default", 1.0)

    adjusted: list[SignalWeight] = []
    for sw in base_weights:
        mult = regime_map.get(sw.signal_id, default_mult)
        new_weight = max(0.0, min(2.0, sw.weight * mult))
        adjusted.append(SignalWeight(
            signal_id=sw.signal_id,
            weight=new_weight,
            p_value=sw.p_value,
            is_significant=sw.is_significant,
            is_decayed=sw.is_decayed,
            win_rate=sw.win_rate,
            n_trades=sw.n_trades,
        ))

    return adjusted


def cusum_change_detection(
    values: Sequence[float],
    delta: float = 0.05,
    threshold: float = 5.0,
) -> tuple[bool, int | None]:
    """CUSUM (cumulative sum) change detection.

    Detects abrupt shift in a sequence of values using a two-sided
    CUSUM algorithm.  Computes running mean, then tracks positive and
    negative cumulative sums of deviations beyond delta.

    Args:
        values: Sequence of float values (e.g. rolling win rates).
        delta: Minimum detectable shift (default 5% = 0.05).
        threshold: Alarm threshold (default 5.0).

    Returns:
        (change_detected, change_point_index or None).
        change_point_index is the first index where CUSUM exceeds threshold.
    """
    n = len(values)
    if n < 2:
        return False, None

    mean_val = sum(values) / n
    s_pos = 0.0
    s_neg = 0.0

    for i, val in enumerate(values):
        deviation = val - mean_val
        s_pos = max(0.0, s_pos + deviation - delta)
        s_neg = max(0.0, s_neg - deviation - delta)

        if s_pos > threshold or s_neg > threshold:
            return True, i

    return False, None
