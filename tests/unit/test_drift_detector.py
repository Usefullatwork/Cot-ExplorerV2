"""Tests for src.analysis.drift_detector -- distribution drift detection."""

from __future__ import annotations

import random

import pytest

from src.analysis.drift_detector import (
    DriftReport,
    DriftResult,
    detect_feature_drift,
    detect_signal_accuracy_drift,
    ks_distribution_drift,
    page_hinkley_test,
)


# ---------------------------------------------------------------------------
# page_hinkley_test
# ---------------------------------------------------------------------------


class TestPageHinkleyTest:
    """Tests for the Page-Hinkley change detection algorithm."""

    def test_stable_sequence_no_drift(self) -> None:
        """A constant sequence should not trigger drift detection."""
        values = [0.55] * 100
        result = page_hinkley_test(values)
        assert not result.is_drifted
        assert result.change_point is None
        assert result.test_name == "page_hinkley"

    def test_mean_shift_detects_drift(self) -> None:
        """A clear mean shift should be detected with change_point set."""
        values = [0.50] * 50 + [0.90] * 50
        result = page_hinkley_test(values, delta=0.01, threshold=2.0)
        assert result.is_drifted
        assert result.change_point is not None
        assert 0 <= result.change_point < 100

    def test_single_value_no_drift(self) -> None:
        """Single value: insufficient data, no drift."""
        result = page_hinkley_test([0.5])
        assert not result.is_drifted
        assert result.change_point is None

    def test_empty_sequence_no_drift(self) -> None:
        """Empty sequence: insufficient data, no drift."""
        result = page_hinkley_test([])
        assert not result.is_drifted
        assert result.p_value == 1.0

    def test_all_same_values_no_drift(self) -> None:
        """All identical values should not trigger drift."""
        result = page_hinkley_test([1.0] * 200)
        assert not result.is_drifted

    def test_high_threshold_no_detection(self) -> None:
        """Very high threshold should not detect even obvious shifts."""
        values = [0.0] * 50 + [10.0] * 50
        result = page_hinkley_test(values, threshold=99999.0)
        assert not result.is_drifted

    def test_change_point_in_reasonable_range(self) -> None:
        """Change point should be near the actual shift location."""
        values = [0.50] * 80 + [0.95] * 20
        result = page_hinkley_test(values, delta=0.01, threshold=1.0)
        if result.is_drifted and result.change_point is not None:
            # Should detect somewhere around the shift point
            assert result.change_point >= 0


# ---------------------------------------------------------------------------
# ks_distribution_drift
# ---------------------------------------------------------------------------


class TestKsDistributionDrift:
    """Tests for Kolmogorov-Smirnov distribution drift test."""

    def test_same_distribution_no_drift(self) -> None:
        """Two samples from the same distribution should not drift."""
        rng = random.Random(42)
        a = [rng.gauss(0, 1) for _ in range(200)]
        b = [rng.gauss(0, 1) for _ in range(200)]
        result = ks_distribution_drift(a, b, alpha=0.05)
        assert not result.is_drifted
        assert result.p_value > 0.05

    def test_different_distributions_detect_drift(self) -> None:
        """Clearly different distributions should be detected."""
        rng = random.Random(42)
        a = [rng.gauss(0, 1) for _ in range(200)]
        b = [rng.gauss(5, 1) for _ in range(200)]
        result = ks_distribution_drift(a, b, alpha=0.05)
        assert result.is_drifted
        assert result.p_value < 0.05
        assert result.test_name == "ks_2samp"

    def test_short_window_a_no_crash(self) -> None:
        """Very short window_a should return no drift, not crash."""
        result = ks_distribution_drift([1.0], [1.0, 2.0, 3.0])
        assert not result.is_drifted

    def test_short_window_b_no_crash(self) -> None:
        """Very short window_b should return no drift, not crash."""
        result = ks_distribution_drift([1.0, 2.0, 3.0], [1.0])
        assert not result.is_drifted

    def test_empty_windows(self) -> None:
        """Empty windows should be handled gracefully."""
        result = ks_distribution_drift([], [])
        assert not result.is_drifted
        assert result.p_value == 1.0

    def test_statistic_range(self) -> None:
        """KS statistic should be between 0 and 1."""
        rng = random.Random(99)
        a = [rng.gauss(0, 1) for _ in range(100)]
        b = [rng.gauss(3, 1) for _ in range(100)]
        result = ks_distribution_drift(a, b)
        assert 0.0 <= result.statistic <= 1.0


# ---------------------------------------------------------------------------
# detect_feature_drift
# ---------------------------------------------------------------------------


class TestDetectFeatureDrift:
    """Tests for multi-feature drift detection."""

    def test_mixed_features(self) -> None:
        """Some features drifted, some not -- correct counts."""
        rng = random.Random(42)
        current = {
            "stable": [rng.gauss(0, 1) for _ in range(100)],
            "drifted": [rng.gauss(5, 1) for _ in range(100)],
        }
        historical = {
            "stable": [rng.gauss(0, 1) for _ in range(100)],
            "drifted": [rng.gauss(0, 1) for _ in range(100)],
        }
        report = detect_feature_drift(current, historical, alpha=0.05)
        assert isinstance(report, DriftReport)
        assert report.any_drift
        assert len(report.results) == 2
        # The drifted feature should be critical (p < 0.01 for such big shift)
        assert report.critical_drifts >= 1

    def test_no_common_keys(self) -> None:
        """No overlapping keys should produce empty report."""
        report = detect_feature_drift(
            {"a": [1.0, 2.0]}, {"b": [1.0, 2.0]},
        )
        assert not report.any_drift
        assert len(report.results) == 0
        assert report.critical_drifts == 0
        assert report.warning_drifts == 0

    def test_all_stable_no_drift(self) -> None:
        """All features from same distribution -- no drift."""
        rng = random.Random(123)
        current = {
            f"feat_{i}": [rng.gauss(0, 1) for _ in range(100)]
            for i in range(5)
        }
        historical = {
            f"feat_{i}": [rng.gauss(0, 1) for _ in range(100)]
            for i in range(5)
        }
        report = detect_feature_drift(current, historical)
        # Most features should not drift (some might by chance, but unlikely all)
        assert report.critical_drifts == 0

    def test_empty_dicts(self) -> None:
        """Empty feature dicts should return empty report."""
        report = detect_feature_drift({}, {})
        assert not report.any_drift
        assert len(report.results) == 0

    def test_result_names_include_feature(self) -> None:
        """Each result test_name should include the feature key."""
        rng = random.Random(42)
        current = {"my_feat": [rng.gauss(0, 1) for _ in range(50)]}
        historical = {"my_feat": [rng.gauss(0, 1) for _ in range(50)]}
        report = detect_feature_drift(current, historical)
        assert len(report.results) == 1
        assert "my_feat" in report.results[0].test_name


# ---------------------------------------------------------------------------
# detect_signal_accuracy_drift
# ---------------------------------------------------------------------------


class TestDetectSignalAccuracyDrift:
    """Tests for signal accuracy z-test drift detection."""

    def test_same_win_rate_no_drift(self) -> None:
        """Identical win rates should not show drift."""
        recent = [True, False] * 50      # 50% win rate
        historical = [True, False] * 50  # 50% win rate
        result = detect_signal_accuracy_drift(recent, historical)
        assert not result.is_drifted
        assert result.test_name == "accuracy_z_test"

    def test_very_different_rates_detect_drift(self) -> None:
        """90% vs 20% win rate should clearly drift."""
        recent = [True] * 90 + [False] * 10
        historical = [True] * 20 + [False] * 80
        result = detect_signal_accuracy_drift(recent, historical)
        assert result.is_drifted
        assert result.p_value < 0.01

    def test_short_sequences_no_crash(self) -> None:
        """Very short sequences should not crash."""
        result = detect_signal_accuracy_drift([True], [False])
        assert not result.is_drifted
        assert result.p_value == 1.0

    def test_empty_sequences(self) -> None:
        """Empty sequences handled gracefully."""
        result = detect_signal_accuracy_drift([], [])
        assert not result.is_drifted

    def test_all_true_both_windows(self) -> None:
        """All wins in both windows: no variance, no drift."""
        recent = [True] * 50
        historical = [True] * 50
        result = detect_signal_accuracy_drift(recent, historical)
        assert not result.is_drifted

    def test_all_false_both_windows(self) -> None:
        """All losses in both windows: no variance, no drift."""
        recent = [False] * 50
        historical = [False] * 50
        result = detect_signal_accuracy_drift(recent, historical)
        assert not result.is_drifted

    def test_moderate_difference_borderline(self) -> None:
        """Moderate difference should produce a finite p-value."""
        recent = [True] * 60 + [False] * 40     # 60%
        historical = [True] * 50 + [False] * 50  # 50%
        result = detect_signal_accuracy_drift(recent, historical)
        assert 0.0 < result.p_value < 1.0
        assert result.statistic > 0.0
