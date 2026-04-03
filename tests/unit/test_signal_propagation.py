"""Unit tests for src.analysis.signal_propagation — cross-asset signal flow."""

from __future__ import annotations

import math

from src.analysis.signal_propagation import (
    PropagationEdge,
    PropagationGraph,
    build_propagation_graph,
    compute_lagged_correlation,
    get_leading_instruments,
    propagate_signals,
)


# ===== compute_lagged_correlation() =========================================


class TestComputeLaggedCorrelation:
    """Lagged Pearson correlation between return series."""

    def test_leader_shifted_by_2(self):
        """Leader series shifted forward by 2 bars -> best_lag=2."""
        # A leads B by 2 bars
        leader = [0.1, -0.2, 0.3, -0.1, 0.2, -0.3, 0.15, -0.1, 0.25, -0.15]
        follower = [0.0, 0.0, 0.1, -0.2, 0.3, -0.1, 0.2, -0.3, 0.15, -0.1]
        lag, corr = compute_lagged_correlation(leader, follower, max_lag=5)
        assert lag == 2
        assert corr > 0.5

    def test_simultaneous_correlation_lag_zero(self):
        """Identical series have best lag 0."""
        series = [0.1, -0.2, 0.3, -0.1, 0.2, -0.3, 0.15]
        lag, corr = compute_lagged_correlation(series, series, max_lag=5)
        assert lag == 0
        assert abs(corr - 1.0) < 1e-4

    def test_uncorrelated_series(self):
        """Unrelated series have lower correlation than perfectly correlated."""
        a = [0.1, 0.4, -0.3, 0.2, -0.5, 0.1, 0.3, -0.2, 0.4, -0.1]
        b = [0.2, -0.1, 0.3, 0.1, 0.2, -0.4, -0.1, 0.5, -0.3, 0.1]
        _lag, corr = compute_lagged_correlation(a, b, max_lag=3)
        # Not perfectly correlated (allow some spurious correlation in short series)
        assert abs(corr) < 1.0

    def test_empty_series_returns_zero(self):
        """Empty input returns (0, 0.0)."""
        lag, corr = compute_lagged_correlation([], [], max_lag=5)
        assert lag == 0
        assert corr == 0.0

    def test_short_series_returns_zero(self):
        """Series shorter than 3 returns (0, 0.0)."""
        lag, corr = compute_lagged_correlation([0.1, 0.2], [0.3, 0.4])
        assert lag == 0
        assert corr == 0.0

    def test_inverse_correlation(self):
        """Inversely correlated series produce negative correlation."""
        a = [0.1, -0.2, 0.3, -0.1, 0.2, -0.3, 0.15]
        b = [-0.1, 0.2, -0.3, 0.1, -0.2, 0.3, -0.15]
        _lag, corr = compute_lagged_correlation(a, b, max_lag=3)
        assert corr < 0.0


# ===== build_propagation_graph() ============================================


class TestBuildPropagationGraph:
    """Graph construction from return data."""

    def test_correlated_pairs_get_edges(self):
        """Strongly correlated instruments produce edges."""
        # A and B are identical (lag 0, corr ~1.0)
        returns = {
            "A": [0.1, -0.2, 0.3, -0.1, 0.2, -0.3, 0.15],
            "B": [0.1, -0.2, 0.3, -0.1, 0.2, -0.3, 0.15],
        }
        graph = build_propagation_graph(returns, min_correlation=0.3)
        assert graph.n_edges > 0
        assert graph.n_instruments == 2

    def test_uncorrelated_no_edges(self):
        """Weakly correlated instruments produce no edges."""
        returns = {
            "A": [0.1, 0.3, -0.2, 0.4, -0.1, 0.2, -0.3, 0.1, 0.0, -0.1],
            "B": [-0.3, 0.1, 0.2, -0.1, 0.3, -0.2, 0.1, -0.4, 0.0, 0.2],
        }
        graph = build_propagation_graph(returns, min_correlation=0.9)
        assert graph.n_edges == 0

    def test_lagged_pair_directed_edge(self):
        """Lagged pair produces directed edge from leader to follower."""
        leader = [0.1, -0.2, 0.3, -0.1, 0.2, -0.3, 0.15, -0.1, 0.25, -0.15]
        follower = [0.0, 0.0, 0.1, -0.2, 0.3, -0.1, 0.2, -0.3, 0.15, -0.1]
        returns = {"LEADER": leader, "FOLLOWER": follower}
        graph = build_propagation_graph(returns, min_correlation=0.3, max_lag=5)
        # Should have exactly 1 directed edge from LEADER -> FOLLOWER
        lagged_edges = [e for e in graph.edges if e.lag_bars > 0]
        assert len(lagged_edges) >= 1
        assert lagged_edges[0].source == "LEADER"
        assert lagged_edges[0].target == "FOLLOWER"

    def test_simultaneous_bidirectional(self):
        """Lag-0 correlation produces bidirectional edges."""
        series = [0.1, -0.2, 0.3, -0.1, 0.2, -0.3, 0.15]
        returns = {"A": series, "B": series}
        graph = build_propagation_graph(returns, min_correlation=0.3)
        lag0_edges = [e for e in graph.edges if e.lag_bars == 0]
        # Bidirectional: A->B and B->A
        assert len(lag0_edges) == 2

    def test_empty_returns(self):
        """No instruments produce empty graph."""
        graph = build_propagation_graph({})
        assert graph.n_edges == 0
        assert graph.n_instruments == 0

    def test_single_instrument(self):
        """Single instrument produces no edges."""
        returns = {"A": [0.1, -0.2, 0.3, -0.1, 0.2]}
        graph = build_propagation_graph(returns)
        assert graph.n_edges == 0

    def test_edge_direction_positive(self):
        """Positively correlated pair has direction='positive'."""
        series = [0.1, -0.2, 0.3, -0.1, 0.2, -0.3, 0.15]
        returns = {"A": series, "B": series}
        graph = build_propagation_graph(returns, min_correlation=0.3)
        for edge in graph.edges:
            assert edge.direction == "positive"

    def test_edge_direction_negative(self):
        """Inversely correlated pair has direction='negative'."""
        a = [0.1, -0.2, 0.3, -0.1, 0.2, -0.3, 0.15]
        b = [-0.1, 0.2, -0.3, 0.1, -0.2, 0.3, -0.15]
        returns = {"A": a, "B": b}
        graph = build_propagation_graph(returns, min_correlation=0.3)
        for edge in graph.edges:
            assert edge.direction == "negative"


# ===== propagate_signals() ==================================================


class TestPropagateSignals:
    """Signal propagation through the graph."""

    def _make_graph(self, edges: list[PropagationEdge]) -> PropagationGraph:
        """Helper to build a PropagationGraph from edges."""
        instruments = set()
        for e in edges:
            instruments.add(e.source)
            instruments.add(e.target)
        return PropagationGraph(
            edges=edges,
            n_instruments=len(instruments),
            n_edges=len(edges),
        )

    def test_bullish_positive_edge(self):
        """Bullish EURUSD + positive edge -> bullish GBPUSD."""
        graph = self._make_graph([
            PropagationEdge("EURUSD", "GBPUSD", 0.7, 2, "positive"),
        ])
        impacts = propagate_signals(graph, {"EURUSD": "bullish"})
        assert len(impacts) == 1
        assert impacts[0].instrument == "GBPUSD"
        assert impacts[0].expected_direction == "bullish"
        assert impacts[0].strength == 0.7

    def test_bullish_negative_edge(self):
        """Bullish DXY + negative edge to Gold -> bearish Gold."""
        graph = self._make_graph([
            PropagationEdge("DXY", "Gold", -0.8, 1, "negative"),
        ])
        impacts = propagate_signals(graph, {"DXY": "bullish"})
        assert len(impacts) == 1
        assert impacts[0].instrument == "Gold"
        assert impacts[0].expected_direction == "bearish"

    def test_bearish_negative_edge(self):
        """Bearish DXY + negative edge to Gold -> bullish Gold."""
        graph = self._make_graph([
            PropagationEdge("DXY", "Gold", -0.8, 1, "negative"),
        ])
        impacts = propagate_signals(graph, {"DXY": "bearish"})
        assert len(impacts) == 1
        assert impacts[0].expected_direction == "bullish"

    def test_no_active_signals(self):
        """No active signals produce no impacts."""
        graph = self._make_graph([
            PropagationEdge("A", "B", 0.7, 2, "positive"),
        ])
        impacts = propagate_signals(graph, {})
        assert len(impacts) == 0

    def test_min_strength_filters(self):
        """Weak edges are filtered by min_strength."""
        graph = self._make_graph([
            PropagationEdge("A", "B", 0.2, 1, "positive"),
        ])
        impacts = propagate_signals(graph, {"A": "bullish"}, min_strength=0.3)
        assert len(impacts) == 0

    def test_no_recursive_propagation(self):
        """Signals propagate only 1 hop, not recursively."""
        graph = self._make_graph([
            PropagationEdge("A", "B", 0.8, 1, "positive"),
            PropagationEdge("B", "C", 0.8, 1, "positive"),
        ])
        # Only A is active; B should appear as impact, C should NOT
        impacts = propagate_signals(graph, {"A": "bullish"})
        target_instruments = {i.instrument for i in impacts}
        assert "B" in target_instruments
        assert "C" not in target_instruments

    def test_skip_already_active_targets(self):
        """Targets that already have active signals are skipped."""
        graph = self._make_graph([
            PropagationEdge("A", "B", 0.8, 1, "positive"),
        ])
        # Both A and B are active — no propagation needed
        impacts = propagate_signals(graph, {"A": "bullish", "B": "bearish"})
        assert len(impacts) == 0

    def test_lag_bars_preserved(self):
        """Impact preserves the lag from the edge."""
        graph = self._make_graph([
            PropagationEdge("A", "B", 0.7, 3, "positive"),
        ])
        impacts = propagate_signals(graph, {"A": "bullish"})
        assert impacts[0].lag_bars == 3


# ===== get_leading_instruments() ============================================


class TestGetLeadingInstruments:
    """Ranking instruments by outgoing lagged edges."""

    def test_most_outgoing_ranked_first(self):
        """Instrument with most outgoing lag>0 edges is first."""
        graph = PropagationGraph(
            edges=[
                PropagationEdge("A", "B", 0.7, 2, "positive"),
                PropagationEdge("A", "C", 0.6, 1, "positive"),
                PropagationEdge("A", "D", 0.5, 3, "positive"),
                PropagationEdge("B", "D", 0.4, 1, "positive"),
            ],
            n_instruments=4,
            n_edges=4,
        )
        leaders = get_leading_instruments(graph)
        assert leaders[0] == ("A", 3)
        assert leaders[1] == ("B", 1)

    def test_lag_zero_edges_excluded(self):
        """Lag-0 (simultaneous) edges don't count as leading."""
        graph = PropagationGraph(
            edges=[
                PropagationEdge("A", "B", 0.7, 0, "positive"),
                PropagationEdge("B", "A", 0.7, 0, "positive"),
            ],
            n_instruments=2,
            n_edges=2,
        )
        leaders = get_leading_instruments(graph)
        assert len(leaders) == 0

    def test_empty_graph(self):
        """Empty graph returns empty list."""
        graph = PropagationGraph(edges=[], n_instruments=0, n_edges=0)
        leaders = get_leading_instruments(graph)
        assert len(leaders) == 0
