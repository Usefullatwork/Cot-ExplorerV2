"""Cross-asset signal propagation graph.

Builds a directed graph of lagged correlations between instruments
and propagates active trading signals through it to identify
downstream impacts. Pure functions, stdlib + math only.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Sequence

# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PropagationEdge:
    """Directed edge in the signal propagation graph."""

    source: str  # source instrument
    target: str  # target instrument
    correlation: float  # strength of relationship
    lag_bars: int  # delay in bars (0 = simultaneous)
    direction: str  # "positive" or "negative" (inverse correlation)


@dataclass(frozen=True)
class PropagationImpact:
    """Downstream impact from an active signal."""

    instrument: str
    source_signal: str  # which instrument's signal propagated
    expected_direction: str  # "bullish" or "bearish"
    strength: float  # 0-1 confidence in the propagation
    lag_bars: int  # expected delay


@dataclass(frozen=True)
class PropagationGraph:
    """Complete signal propagation graph."""

    edges: list[PropagationEdge]
    n_instruments: int
    n_edges: int


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mean(xs: Sequence[float]) -> float:
    """Arithmetic mean. Returns 0.0 for empty sequence."""
    n = len(xs)
    if n == 0:
        return 0.0
    return math.fsum(xs) / n


def _pearson(x: Sequence[float], y: Sequence[float]) -> float:
    """Pearson correlation for equal-length sequences.

    Returns 0.0 for degenerate inputs (len < 2 or zero variance).
    """
    n = min(len(x), len(y))
    if n < 2:
        return 0.0

    mx = _mean(x[:n])
    my = _mean(y[:n])

    num = 0.0
    var_x = 0.0
    var_y = 0.0
    for i in range(n):
        dx = x[i] - mx
        dy = y[i] - my
        num += dx * dy
        var_x += dx * dx
        var_y += dy * dy

    if var_x == 0.0 or var_y == 0.0:
        return 0.0

    return num / math.sqrt(var_x * var_y)


# ---------------------------------------------------------------------------
# Core functions
# ---------------------------------------------------------------------------


def compute_lagged_correlation(
    series_a: Sequence[float],
    series_b: Sequence[float],
    max_lag: int = 5,
) -> tuple[int, float]:
    """Find optimal lag between two return series.

    Computes Pearson correlation at each lag from 0 to max_lag.
    series_a is the LEADER (shifted forward), series_b is the FOLLOWER.

    At lag L, we correlate series_a[:-L] with series_b[L:], meaning
    series_a leads series_b by L bars.

    Returns:
        (best_lag, best_correlation) where best_correlation has the
        highest absolute value among all tested lags.
    """
    n = min(len(series_a), len(series_b))
    if n < 3:
        return (0, 0.0)

    best_lag = 0
    best_corr = 0.0

    for lag in range(0, min(max_lag + 1, n - 1)):
        if lag == 0:
            a_slice = list(series_a[:n])
            b_slice = list(series_b[:n])
        else:
            # a leads b by `lag` bars
            a_slice = list(series_a[:n - lag])
            b_slice = list(series_b[lag:n])

        if len(a_slice) < 2:
            continue

        corr = _pearson(a_slice, b_slice)
        if abs(corr) > abs(best_corr):
            best_corr = corr
            best_lag = lag

    return (best_lag, round(best_corr, 6))


def build_propagation_graph(
    returns: dict[str, Sequence[float]],
    min_correlation: float = 0.3,
    max_lag: int = 5,
) -> PropagationGraph:
    """Build directed signal propagation graph from return series.

    For each pair of instruments:
        1. Compute lagged correlation at lag 0..max_lag.
        2. If best abs(correlation) > min_correlation AND lag > 0:
           Add directed edge from leader to follower.
        3. If lag == 0 and abs(corr) > min_correlation:
           Add bidirectional edges (simultaneous co-movement).

    Direction: positive correlation = "positive", negative = "negative".
    """
    instruments = sorted(returns.keys())
    edges: list[PropagationEdge] = []

    for i, inst_a in enumerate(instruments):
        for inst_b in instruments[i + 1:]:
            series_a = returns[inst_a]
            series_b = returns[inst_b]

            # Test A leading B
            lag_ab, corr_ab = compute_lagged_correlation(
                series_a, series_b, max_lag,
            )
            # Test B leading A
            lag_ba, corr_ba = compute_lagged_correlation(
                series_b, series_a, max_lag,
            )

            # Pick the stronger relationship
            if abs(corr_ab) >= abs(corr_ba):
                best_lag = lag_ab
                best_corr = corr_ab
                leader, follower = inst_a, inst_b
            else:
                best_lag = lag_ba
                best_corr = corr_ba
                leader, follower = inst_b, inst_a

            if abs(best_corr) < min_correlation:
                continue

            direction = "positive" if best_corr > 0 else "negative"

            if best_lag > 0:
                # Directed edge: leader -> follower
                edges.append(PropagationEdge(
                    source=leader,
                    target=follower,
                    correlation=best_corr,
                    lag_bars=best_lag,
                    direction=direction,
                ))
            else:
                # Simultaneous co-movement: bidirectional
                edges.append(PropagationEdge(
                    source=inst_a,
                    target=inst_b,
                    correlation=best_corr,
                    lag_bars=0,
                    direction=direction,
                ))
                edges.append(PropagationEdge(
                    source=inst_b,
                    target=inst_a,
                    correlation=best_corr,
                    lag_bars=0,
                    direction=direction,
                ))

    return PropagationGraph(
        edges=edges,
        n_instruments=len(instruments),
        n_edges=len(edges),
    )


def propagate_signals(
    graph: PropagationGraph,
    active_signals: dict[str, str],
    min_strength: float = 0.3,
) -> list[PropagationImpact]:
    """Propagate active signals through the graph (1-hop only).

    Args:
        graph: The propagation graph.
        active_signals: {instrument: "bullish" or "bearish"}.
        min_strength: Minimum abs(correlation) to include impact.

    For each active signal, finds all outgoing edges from that
    instrument and computes expected direction on the target:
      - positive edge + bullish source = bullish target
      - positive edge + bearish source = bearish target
      - negative edge + bullish source = bearish target
      - negative edge + bearish source = bullish target

    Does NOT propagate recursively (only 1 hop to avoid circular
    amplification).
    """
    impacts: list[PropagationImpact] = []

    for source_inst, signal_dir in active_signals.items():
        signal_dir_lower = signal_dir.lower()

        for edge in graph.edges:
            if edge.source != source_inst:
                continue

            strength = abs(edge.correlation)
            if strength < min_strength:
                continue

            # Skip if target already has an active signal
            if edge.target in active_signals:
                continue

            # Determine expected direction on target
            if edge.direction == "positive":
                expected = signal_dir_lower
            else:
                expected = "bearish" if signal_dir_lower == "bullish" else "bullish"

            impacts.append(PropagationImpact(
                instrument=edge.target,
                source_signal=source_inst,
                expected_direction=expected,
                strength=round(strength, 4),
                lag_bars=edge.lag_bars,
            ))

    return impacts


def get_leading_instruments(
    graph: PropagationGraph,
) -> list[tuple[str, int]]:
    """Identify instruments that lead others.

    Counts outgoing edges with lag > 0 for each instrument.
    Returns [(instrument, n_outgoing_edges)] sorted by count descending.
    """
    counts: dict[str, int] = {}
    for edge in graph.edges:
        if edge.lag_bars > 0:
            counts[edge.source] = counts.get(edge.source, 0) + 1

    ranked = sorted(counts.items(), key=lambda x: x[1], reverse=True)
    return ranked
