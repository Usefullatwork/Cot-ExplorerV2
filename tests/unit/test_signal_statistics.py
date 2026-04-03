"""Unit tests for src.analysis.signal_statistics — ensemble signal stats."""

from __future__ import annotations

import math
import random

import pytest

from src.analysis.signal_statistics import (
    EnsembleReport,
    SignalCorrelation,
    SignalStat,
    binomial_p_value,
    bonferroni_alpha,
    compute_ensemble_report,
    identify_redundant_groups,
    pairwise_signal_correlations,
    phi_coefficient,
    rolling_win_rate,
    signal_decay_check,
)


# ---------------------------------------------------------------------------
# binomial_p_value
# ---------------------------------------------------------------------------

class TestBinomialPValue:
    """Tests for binomial significance testing."""

    def test_random_coin_flip(self) -> None:
        """50/100 wins at null_rate=0.5 should give p ~ 1.0."""
        p = binomial_p_value(50, 100, 0.5)
        assert p > 0.9

    def test_highly_significant(self) -> None:
        """80/100 wins at null=0.5 should give p < 0.001."""
        p = binomial_p_value(80, 100, 0.5)
        assert p < 0.001

    def test_zero_trades(self) -> None:
        """Zero trades returns p = 1.0."""
        assert binomial_p_value(0, 0) == 1.0

    def test_all_wins(self) -> None:
        """100/100 wins is extremely significant."""
        p = binomial_p_value(100, 100, 0.5)
        assert p < 1e-20

    def test_custom_null_rate(self) -> None:
        """30/100 wins at null_rate=0.3 should not be significant."""
        p = binomial_p_value(30, 100, 0.3)
        assert p > 0.5


# ---------------------------------------------------------------------------
# bonferroni_alpha
# ---------------------------------------------------------------------------

class TestBonferroniAlpha:
    """Tests for Bonferroni correction."""

    def test_default_19_signals(self) -> None:
        """0.05 / 19 ~ 0.00263."""
        result = bonferroni_alpha()
        assert abs(result - 0.05 / 19) < 1e-10

    def test_single_test(self) -> None:
        """Single test: no correction needed."""
        assert bonferroni_alpha(0.05, 1) == 0.05

    def test_custom_values(self) -> None:
        """Custom alpha and n_tests."""
        assert abs(bonferroni_alpha(0.10, 5) - 0.02) < 1e-10

    def test_zero_tests_returns_base(self) -> None:
        """Edge case: n_tests=0 returns base_alpha."""
        assert bonferroni_alpha(0.05, 0) == 0.05


# ---------------------------------------------------------------------------
# rolling_win_rate
# ---------------------------------------------------------------------------

class TestRollingWinRate:
    """Tests for rolling window win rate."""

    def test_known_sequence(self) -> None:
        """Manual check with window=3."""
        outcomes = [True, True, False, True, False]
        rates = rolling_win_rate(outcomes, window=3)
        assert len(rates) == 3
        assert abs(rates[0] - 2 / 3) < 1e-10
        assert abs(rates[1] - 2 / 3) < 1e-10
        assert abs(rates[2] - 1 / 3) < 1e-10

    def test_all_true(self) -> None:
        """All wins: every window rate = 1.0."""
        rates = rolling_win_rate([True] * 10, window=5)
        assert all(abs(r - 1.0) < 1e-10 for r in rates)
        assert len(rates) == 6

    def test_too_short(self) -> None:
        """Fewer outcomes than window returns empty."""
        assert rolling_win_rate([True, False], window=5) == []

    def test_window_equals_length(self) -> None:
        """Window == length gives exactly one rate."""
        rates = rolling_win_rate([True, False, True], window=3)
        assert len(rates) == 1
        assert abs(rates[0] - 2 / 3) < 1e-10

    def test_empty_outcomes(self) -> None:
        """Empty outcomes returns empty."""
        assert rolling_win_rate([], window=10) == []


# ---------------------------------------------------------------------------
# signal_decay_check
# ---------------------------------------------------------------------------

class TestSignalDecayCheck:
    """Tests for signal decay detection."""

    def test_decayed_signal(self) -> None:
        """Recent 20% win rate should flag decay."""
        old_good = [True] * 80
        recent_bad = [True] * 4 + [False] * 16
        is_decayed, rate = signal_decay_check(old_good + recent_bad)
        assert is_decayed is True
        assert abs(rate - 0.2) < 1e-10

    def test_healthy_signal(self) -> None:
        """Recent 70% win rate should not flag decay."""
        outcomes = [False] * 80 + [True] * 14 + [False] * 6
        is_decayed, rate = signal_decay_check(outcomes)
        assert is_decayed is False
        assert abs(rate - 0.7) < 1e-10

    def test_too_few_trades(self) -> None:
        """Fewer than short_window trades: not decayed."""
        is_decayed, rate = signal_decay_check([True, False, True])
        assert is_decayed is False

    def test_empty_outcomes(self) -> None:
        """Empty outcomes: not decayed, rate = 0."""
        is_decayed, rate = signal_decay_check([])
        assert is_decayed is False
        assert rate == 0.0

    def test_custom_threshold(self) -> None:
        """Custom threshold changes decay decision."""
        outcomes = [True] * 80 + [True] * 12 + [False] * 8
        is_decayed_strict, rate = signal_decay_check(
            outcomes, threshold=0.65,
        )
        assert is_decayed_strict is True
        assert abs(rate - 0.6) < 1e-10
        is_decayed_lax, _ = signal_decay_check(
            outcomes, threshold=0.55,
        )
        assert is_decayed_lax is False


# ---------------------------------------------------------------------------
# phi_coefficient
# ---------------------------------------------------------------------------

class TestPhiCoefficient:
    """Tests for Matthews/phi correlation."""

    def test_identical_signals(self) -> None:
        """Identical signals: phi = 1.0."""
        a = [True, False, True, True, False]
        assert abs(phi_coefficient(a, a) - 1.0) < 1e-10

    def test_opposite_signals(self) -> None:
        """Opposite signals: phi = -1.0."""
        a = [True, False, True, True, False]
        b = [not x for x in a]
        assert abs(phi_coefficient(a, b) - (-1.0)) < 1e-10

    def test_independent_signals(self) -> None:
        """Statistically independent signals: phi ~ 0."""
        rng = random.Random(42)
        a = [rng.random() > 0.5 for _ in range(1000)]
        b = [rng.random() > 0.5 for _ in range(1000)]
        phi = phi_coefficient(a, b)
        assert abs(phi) < 0.1

    def test_degenerate_all_true(self) -> None:
        """All-True vs all-True: degenerate, returns 0.0."""
        a = [True] * 10
        assert phi_coefficient(a, a) == 0.0

    def test_different_lengths_raises(self) -> None:
        """Different-length signals raise ValueError."""
        with pytest.raises(ValueError, match="same length"):
            phi_coefficient([True, False], [True])

    def test_empty_signals_raises(self) -> None:
        """Empty signals raise ValueError."""
        with pytest.raises(ValueError, match="non-empty"):
            phi_coefficient([], [])


# ---------------------------------------------------------------------------
# pairwise_signal_correlations
# ---------------------------------------------------------------------------

class TestPairwiseCorrelations:
    """Tests for all-pairs phi calculation."""

    def test_three_signals_three_pairs(self) -> None:
        """3 signals produce exactly 3 pairs."""
        matrix = {
            "A": [True, False, True, False],
            "B": [True, False, True, False],
            "C": [False, True, False, True],
        }
        corrs = pairwise_signal_correlations(matrix)
        assert len(corrs) == 3

    def test_identical_pair_is_redundant(self) -> None:
        """Identical signals: is_redundant = True at default threshold."""
        matrix = {
            "X": [True, False, True, True, False],
            "Y": [True, False, True, True, False],
        }
        corrs = pairwise_signal_correlations(matrix, threshold=0.7)
        assert len(corrs) == 1
        assert corrs[0].is_redundant is True
        assert abs(corrs[0].phi_coefficient - 1.0) < 1e-10

    def test_sorted_output(self) -> None:
        """Pairs are sorted alphabetically."""
        matrix = {
            "Z": [True, False],
            "A": [False, True],
            "M": [True, True],
        }
        corrs = pairwise_signal_correlations(matrix)
        pairs = [(c.signal_a, c.signal_b) for c in corrs]
        assert pairs == [("A", "M"), ("A", "Z"), ("M", "Z")]


# ---------------------------------------------------------------------------
# identify_redundant_groups
# ---------------------------------------------------------------------------

class TestRedundantGroups:
    """Tests for union-find clustering."""

    def test_two_redundant_signals(self) -> None:
        """Two correlated signals form one group."""
        corrs = [
            SignalCorrelation("A", "B", 0.85, True),
            SignalCorrelation("A", "C", 0.30, False),
            SignalCorrelation("B", "C", 0.20, False),
        ]
        groups = identify_redundant_groups(corrs, threshold=0.7)
        assert len(groups) == 1
        assert sorted(groups[0]) == ["A", "B"]

    def test_no_redundancy(self) -> None:
        """All low correlations: no groups."""
        corrs = [
            SignalCorrelation("A", "B", 0.1, False),
            SignalCorrelation("A", "C", 0.2, False),
        ]
        groups = identify_redundant_groups(corrs, threshold=0.7)
        assert groups == []

    def test_chain_grouping(self) -> None:
        """A-B redundant, B-C redundant => A,B,C in one group."""
        corrs = [
            SignalCorrelation("A", "B", 0.8, True),
            SignalCorrelation("B", "C", 0.75, True),
            SignalCorrelation("A", "C", 0.5, False),
        ]
        groups = identify_redundant_groups(corrs, threshold=0.7)
        assert len(groups) == 1
        assert sorted(groups[0]) == ["A", "B", "C"]

    def test_empty_correlations(self) -> None:
        """No correlations: no groups."""
        assert identify_redundant_groups([]) == []


# ---------------------------------------------------------------------------
# compute_ensemble_report (integration)
# ---------------------------------------------------------------------------

class TestComputeEnsembleReport:
    """Integration test with realistic multi-signal data."""

    def _make_19_signals(self) -> dict[str, list[bool]]:
        """Generate 19 signals with varying win rates."""
        rng = random.Random(42)
        signal_ids = [
            "sma200", "momentum_20d", "cot_confirms", "cot_strong",
            "at_level_now", "htf_level_nearby", "trend_congruent",
            "no_event_risk", "news_confirms", "fund_confirms",
            "bos_confirms", "smc_struct_confirms", "order_block",
            "fvg", "session_alignment", "correlation_clear",
            "comex_stress", "seismic_risk", "chokepoint_clear",
        ]
        outcomes: dict[str, list[bool]] = {}
        for i, sid in enumerate(signal_ids):
            win_prob = 0.4 + 0.03 * i
            outcomes[sid] = [rng.random() < win_prob for _ in range(200)]
        return outcomes

    def test_report_structure(self) -> None:
        """Report contains correct counts and types."""
        data = self._make_19_signals()
        report = compute_ensemble_report(data)
        assert isinstance(report, EnsembleReport)
        assert report.total_signals == 19
        assert len(report.signal_stats) == 19
        n_pairs = 19 * 18 // 2
        assert len(report.correlations) == n_pairs

    def test_bonferroni_applied(self) -> None:
        """Bonferroni alpha is 0.05/19."""
        data = self._make_19_signals()
        report = compute_ensemble_report(data)
        assert abs(report.bonferroni_alpha - 0.05 / 19) < 1e-10

    def test_active_signals_bounded(self) -> None:
        """Active signals <= total signals."""
        data = self._make_19_signals()
        report = compute_ensemble_report(data)
        assert 0 <= report.active_signals <= report.total_signals

    def test_strong_signal_is_significant(self) -> None:
        """A signal with 90% win rate over 200 trades is significant."""
        data = self._make_19_signals()
        data["sma200"] = [True] * 180 + [False] * 20
        report = compute_ensemble_report(data)
        sma_stat = next(
            s for s in report.signal_stats if s.signal_id == "sma200"
        )
        assert sma_stat.is_significant is True
        assert sma_stat.p_value < 0.001

    def test_decayed_signal_detected(self) -> None:
        """A signal with good history but terrible recent trades is decayed."""
        data = self._make_19_signals()
        good_then_bad = [True] * 180 + [False] * 20
        data["fvg"] = good_then_bad
        report = compute_ensemble_report(data, decay_window=20)
        fvg_stat = next(
            s for s in report.signal_stats if s.signal_id == "fvg"
        )
        assert fvg_stat.is_decayed is True
        assert fvg_stat.decay_rate == 0.0

    def test_redundant_identical_pair(self) -> None:
        """Two identical signals appear in redundant groups."""
        data = self._make_19_signals()
        data["cot_confirms"] = list(data["cot_strong"])
        report = compute_ensemble_report(data, correlation_threshold=0.7)
        flat = [s for g in report.redundant_groups for s in g]
        assert "cot_confirms" in flat
        assert "cot_strong" in flat

    def test_all_random_no_significance(self) -> None:
        """19 coin-flip signals: very few (if any) pass Bonferroni."""
        rng = random.Random(99)
        data = {
            f"sig_{i}": [rng.random() > 0.5 for _ in range(100)]
            for i in range(19)
        }
        report = compute_ensemble_report(data)
        assert report.active_signals <= 2
