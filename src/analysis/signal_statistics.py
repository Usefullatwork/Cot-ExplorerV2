"""Statistical rigor for the 19-signal scoring ensemble.

Provides binomial significance testing, Bonferroni correction, rolling
win-rate analysis, signal decay detection, phi-coefficient correlation,
and redundancy clustering via union-find.  All functions are pure —
accept data arrays, return frozen dataclasses.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Sequence

from scipy import stats

# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class SignalStat:
    """Statistical assessment of a single signal."""

    signal_id: str
    win_rate: float
    n_trades: int
    p_value: float
    is_significant: bool
    is_decayed: bool
    decay_rate: float


@dataclass(frozen=True)
class SignalCorrelation:
    """Pairwise correlation between two signals."""

    signal_a: str
    signal_b: str
    phi_coefficient: float
    is_redundant: bool


@dataclass(frozen=True)
class EnsembleReport:
    """Full ensemble health report."""

    signal_stats: list[SignalStat]
    correlations: list[SignalCorrelation]
    redundant_groups: list[list[str]]
    bonferroni_alpha: float
    active_signals: int
    total_signals: int


# ---------------------------------------------------------------------------
# Significance testing
# ---------------------------------------------------------------------------

def binomial_p_value(
    wins: int, total: int, null_rate: float = 0.5,
) -> float:
    """Two-sided binomial test: is win rate significantly different from null_rate?

    Uses scipy.stats.binomtest (replaces deprecated binom_test).

    Args:
        wins: Number of winning trades.
        total: Total number of trades.
        null_rate: Null hypothesis win rate (default 0.5 = coin flip).

    Returns:
        p-value.  Lower = more evidence against null.
        Returns 1.0 if total == 0.
    """
    if total <= 0:
        return 1.0
    result = stats.binomtest(wins, total, null_rate, alternative="two-sided")
    return float(result.pvalue)


def bonferroni_alpha(
    base_alpha: float = 0.05, n_tests: int = 19,
) -> float:
    """Bonferroni-corrected significance threshold.

    Args:
        base_alpha: Family-wise error rate (default 0.05).
        n_tests: Number of simultaneous tests (default 19 signals).

    Returns:
        Adjusted alpha = base_alpha / n_tests.
    """
    if n_tests <= 0:
        return base_alpha
    return base_alpha / n_tests


# ---------------------------------------------------------------------------
# Rolling win rate & decay
# ---------------------------------------------------------------------------

def rolling_win_rate(
    outcomes: Sequence[bool], window: int = 100,
) -> list[float]:
    """Compute rolling win rate over a sliding window.

    Args:
        outcomes: Boolean sequence (True = win, False = loss).
        window: Sliding window size.

    Returns:
        List of win rates, length = max(0, len(outcomes) - window + 1).
    """
    n = len(outcomes)
    if n < window or window <= 0:
        return []

    wins = sum(1 for o in outcomes[:window] if o)
    rates: list[float] = [wins / window]
    for i in range(window, n):
        if outcomes[i]:
            wins += 1
        if outcomes[i - window]:
            wins -= 1
        rates.append(wins / window)
    return rates


def signal_decay_check(
    outcomes: Sequence[bool],
    short_window: int = 20,
    threshold: float = 0.45,
) -> tuple[bool, float]:
    """Check if a signal has decayed (recent win rate below threshold).

    Args:
        outcomes: Boolean sequence ordered oldest-first.
        short_window: Number of most-recent trades to examine.
        threshold: Win rate below this = decayed.

    Returns:
        (is_decayed, recent_win_rate).
        If fewer than short_window outcomes, uses all available data.
    """
    n = len(outcomes)
    if n == 0:
        return False, 0.0

    actual_window = min(short_window, n)
    recent = outcomes[-actual_window:]
    recent_rate = sum(1 for o in recent if o) / actual_window

    is_decayed = recent_rate < threshold and n >= short_window
    return is_decayed, recent_rate


# ---------------------------------------------------------------------------
# Phi coefficient (Matthews correlation)
# ---------------------------------------------------------------------------

def phi_coefficient(
    signal_a: Sequence[bool], signal_b: Sequence[bool],
) -> float:
    """Compute phi coefficient (Matthews correlation) between two binary signals.

    phi = (n11*n00 - n10*n01) / sqrt((n11+n10)(n01+n00)(n11+n01)(n10+n00))

    Args:
        signal_a: Binary signal outcomes.
        signal_b: Binary signal outcomes (must be same length).

    Returns:
        Phi coefficient in range [-1, +1].
        Returns 0.0 if denominator is zero (degenerate case).

    Raises:
        ValueError: If signals have different lengths or are empty.
    """
    if len(signal_a) != len(signal_b):
        raise ValueError("signal_a and signal_b must have the same length")
    if len(signal_a) == 0:
        raise ValueError("signals must be non-empty")

    n11 = n10 = n01 = n00 = 0
    for a, b in zip(signal_a, signal_b):
        if a and b:
            n11 += 1
        elif a and not b:
            n10 += 1
        elif not a and b:
            n01 += 1
        else:
            n00 += 1

    numerator = n11 * n00 - n10 * n01
    denom_sq = (n11 + n10) * (n01 + n00) * (n11 + n01) * (n10 + n00)
    if denom_sq == 0:
        return 0.0
    return numerator / math.sqrt(denom_sq)


# ---------------------------------------------------------------------------
# Pairwise correlations
# ---------------------------------------------------------------------------

def pairwise_signal_correlations(
    signal_matrix: dict[str, Sequence[bool]],
    threshold: float = 0.7,
) -> list[SignalCorrelation]:
    """Compute phi coefficient for all unique signal pairs.

    Args:
        signal_matrix: {signal_id: [bool outcomes per trade]}.
        threshold: |phi| above this flags pair as redundant.

    Returns:
        List of SignalCorrelation for all unique pairs, sorted by
        (signal_a, signal_b) for deterministic output.
    """
    ids = sorted(signal_matrix.keys())
    results: list[SignalCorrelation] = []
    for i, id_a in enumerate(ids):
        for id_b in ids[i + 1:]:
            phi = phi_coefficient(signal_matrix[id_a], signal_matrix[id_b])
            results.append(SignalCorrelation(
                signal_a=id_a,
                signal_b=id_b,
                phi_coefficient=phi,
                is_redundant=abs(phi) > threshold,
            ))
    return results


# ---------------------------------------------------------------------------
# Redundancy clustering (union-find)
# ---------------------------------------------------------------------------

def identify_redundant_groups(
    correlations: list[SignalCorrelation],
    threshold: float = 0.7,
) -> list[list[str]]:
    """Cluster redundant signals using union-find.

    Signals with |phi| > threshold are grouped together.

    Args:
        correlations: Pairwise correlation results.
        threshold: Redundancy threshold.

    Returns:
        List of groups (each group = sorted list of signal IDs).
        Only groups with 2+ members are returned.
        Groups are sorted by their first element for determinism.
    """
    parent: dict[str, str] = {}

    def find(x: str) -> str:
        if x not in parent:
            parent[x] = x
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: str, b: str) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    for corr in correlations:
        if abs(corr.phi_coefficient) > threshold:
            union(corr.signal_a, corr.signal_b)

    groups: dict[str, list[str]] = {}
    all_signals: set[str] = set()
    for corr in correlations:
        all_signals.add(corr.signal_a)
        all_signals.add(corr.signal_b)

    for sig in all_signals:
        root = find(sig)
        groups.setdefault(root, []).append(sig)

    result = [
        sorted(members)
        for members in groups.values()
        if len(members) >= 2
    ]
    result.sort(key=lambda g: g[0])
    return result


# ---------------------------------------------------------------------------
# Ensemble report
# ---------------------------------------------------------------------------

def compute_ensemble_report(
    signal_outcomes: dict[str, Sequence[bool]],
    base_alpha: float = 0.05,
    decay_window: int = 20,
    decay_threshold: float = 0.45,
    correlation_threshold: float = 0.7,
) -> EnsembleReport:
    """Full ensemble health report.

    For each signal: computes p-value, checks decay, determines significance.
    For all pairs: computes phi coefficient, identifies redundant groups.

    Args:
        signal_outcomes: {signal_id: [bool outcomes per trade]}.
        base_alpha: Family-wise error rate for Bonferroni correction.
        decay_window: Recent window size for decay check.
        decay_threshold: Win rate below this = decayed.
        correlation_threshold: |phi| above this = redundant pair.

    Returns:
        EnsembleReport with all signal stats, correlations, and redundancy info.
    """
    n_signals = len(signal_outcomes)
    adj_alpha = bonferroni_alpha(base_alpha, n_signals)

    signal_stats: list[SignalStat] = []
    for sig_id in sorted(signal_outcomes.keys()):
        outcomes = signal_outcomes[sig_id]
        n_trades = len(outcomes)
        wins = sum(1 for o in outcomes if o)
        win_rate = wins / n_trades if n_trades > 0 else 0.0
        p_val = binomial_p_value(wins, n_trades)
        is_decayed, decay_rate = signal_decay_check(
            outcomes, decay_window, decay_threshold,
        )
        signal_stats.append(SignalStat(
            signal_id=sig_id,
            win_rate=win_rate,
            n_trades=n_trades,
            p_value=p_val,
            is_significant=p_val < adj_alpha,
            is_decayed=is_decayed,
            decay_rate=decay_rate,
        ))

    correlations = pairwise_signal_correlations(
        signal_outcomes, correlation_threshold,
    )
    redundant_groups = identify_redundant_groups(
        correlations, correlation_threshold,
    )

    active = sum(
        1 for s in signal_stats
        if s.is_significant and not s.is_decayed
    )

    return EnsembleReport(
        signal_stats=signal_stats,
        correlations=correlations,
        redundant_groups=redundant_groups,
        bonferroni_alpha=adj_alpha,
        active_signals=active,
        total_signals=n_signals,
    )
