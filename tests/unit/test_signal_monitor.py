"""Tests for src.analysis.signal_monitor — signal weighting and ensemble health."""

from __future__ import annotations

import pytest

from src.analysis.signal_monitor import (
    EnsembleHealthReport,
    SignalWeight,
    compute_regime_weights,
    compute_signal_weights,
    cusum_change_detection,
    get_ensemble_health,
)


# ---------------------------------------------------------------------------
# Helpers — generate deterministic outcome sequences
# ---------------------------------------------------------------------------

def _outcomes(win_rate: float, n: int = 100) -> list[bool]:
    """Create a deterministic interleaved outcome list with exact win rate.

    Interleaves wins/losses so the last 20 outcomes reflect the overall
    rate (avoids false decay detection).
    """
    wins = int(round(win_rate * n))
    result: list[bool] = []
    w_placed = 0
    l_placed = 0
    losses = n - wins
    for i in range(n):
        # Bresenham-style interleaving
        if losses == 0 or (wins > 0 and w_placed * losses <= l_placed * wins):
            result.append(True)
            w_placed += 1
        else:
            result.append(False)
            l_placed += 1
    return result


def _decayed_outcomes(
    early_rate: float, late_rate: float,
    early_n: int = 80, late_n: int = 20,
) -> list[bool]:
    """Create outcomes where early period is strong, late period decayed."""
    early = [True] * int(round(early_rate * early_n)) + \
            [False] * (early_n - int(round(early_rate * early_n)))
    late = [True] * int(round(late_rate * late_n)) + \
           [False] * (late_n - int(round(late_rate * late_n)))
    return early + late


# ---------------------------------------------------------------------------
# compute_signal_weights
# ---------------------------------------------------------------------------

class TestComputeSignalWeights:
    """Tests for compute_signal_weights."""

    def test_significant_signal_gets_weight_above_one(self) -> None:
        """A signal with 75% win rate (well above 50%) should get weight > 1."""
        outcomes = {"sig_a": _outcomes(0.75, 100)}
        weights = compute_signal_weights(outcomes, min_trades=30, n_signals=1)
        assert len(weights) == 1
        w = weights[0]
        assert w.weight > 1.0
        assert w.is_significant
        assert not w.is_decayed

    def test_insignificant_signal_gets_zero(self) -> None:
        """A coin-flip signal (50%) should not be significant -> weight 0."""
        outcomes = {"sig_a": _outcomes(0.50, 100)}
        weights = compute_signal_weights(outcomes, min_trades=30, n_signals=1)
        w = weights[0]
        assert w.weight == 0.0
        assert not w.is_significant

    def test_decayed_signal_gets_half(self) -> None:
        """Signal with recent decay should get weight 0.5."""
        outcomes = {"sig_a": _decayed_outcomes(0.80, 0.30, 80, 20)}
        weights = compute_signal_weights(
            outcomes, min_trades=30, n_signals=1, decay_window=20,
            decay_threshold=0.45,
        )
        w = weights[0]
        assert w.is_decayed
        assert w.weight == 0.5

    def test_few_trades_gets_default_weight(self) -> None:
        """Signal with fewer trades than min_trades keeps weight 1.0."""
        outcomes = {"sig_a": _outcomes(0.90, 10)}
        weights = compute_signal_weights(outcomes, min_trades=30, n_signals=1)
        w = weights[0]
        assert w.weight == 1.0
        assert w.n_trades == 10

    def test_weight_clamped_to_two(self) -> None:
        """Even extreme win rates should clamp weight to 2.0 max."""
        outcomes = {"sig_a": _outcomes(1.0, 100)}
        weights = compute_signal_weights(outcomes, min_trades=30, n_signals=1)
        w = weights[0]
        assert w.weight <= 2.0

    def test_empty_signal_outcomes(self) -> None:
        """Empty dict should return empty list."""
        weights = compute_signal_weights({})
        assert weights == []

    def test_all_true_outcomes(self) -> None:
        """All True outcomes -> significant, high weight."""
        outcomes = {"sig_a": [True] * 100}
        weights = compute_signal_weights(outcomes, min_trades=30, n_signals=1)
        w = weights[0]
        assert w.is_significant
        assert w.weight == 2.0

    def test_all_false_outcomes(self) -> None:
        """All False -> significant (significantly bad), but weight = 0/0.5 = 0."""
        outcomes = {"sig_a": [False] * 100}
        weights = compute_signal_weights(outcomes, min_trades=30, n_signals=1)
        w = weights[0]
        # 0% win rate is significantly different from 50%, so is_significant
        assert w.is_significant
        # weight = 0.0 / 0.5 = 0.0 (but also decayed since recent rate < 0.45)
        assert w.weight <= 0.5

    def test_multiple_signals_sorted(self) -> None:
        """Weights should be returned sorted by signal_id."""
        outcomes = {
            "zzz": _outcomes(0.75, 100),
            "aaa": _outcomes(0.50, 100),
        }
        weights = compute_signal_weights(outcomes, n_signals=2)
        assert weights[0].signal_id == "aaa"
        assert weights[1].signal_id == "zzz"


# ---------------------------------------------------------------------------
# get_ensemble_health
# ---------------------------------------------------------------------------

class TestGetEnsembleHealth:
    """Tests for get_ensemble_health."""

    def test_19_healthy_signals(self) -> None:
        """19 strong signals -> healthy ensemble."""
        outcomes = {
            f"sig_{i:02d}": _outcomes(0.80, 100) for i in range(19)
        }
        report = get_ensemble_health(outcomes, min_trades=30)
        assert isinstance(report, EnsembleHealthReport)
        assert report.ensemble_quality == "healthy"
        assert report.active_count >= 12
        assert report.total_signals == 19

    def test_5_active_signals_is_critical(self) -> None:
        """Only 5 active signals should flag 'critical'."""
        # 5 significant signals + 14 coin-flip signals
        outcomes: dict[str, list[bool]] = {}
        for i in range(5):
            outcomes[f"sig_{i:02d}"] = _outcomes(0.80, 100)
        for i in range(5, 19):
            outcomes[f"sig_{i:02d}"] = _outcomes(0.50, 100)
        report = get_ensemble_health(outcomes, min_trades=30)
        assert report.ensemble_quality == "critical"
        assert report.active_count < 6

    def test_alerts_populated_for_excluded(self) -> None:
        """Excluded signals should generate alert messages."""
        outcomes = {
            "good": _outcomes(0.80, 100),
            "bad": _outcomes(0.50, 100),
        }
        report = get_ensemble_health(outcomes, min_trades=30)
        alert_texts = " ".join(report.alerts)
        assert "not significant" in alert_texts or "CRITICAL" in alert_texts

    def test_alerts_for_decayed_signals(self) -> None:
        """Decayed signals should generate decay alert messages."""
        outcomes = {
            "decayed_sig": _decayed_outcomes(0.80, 0.30, 80, 20),
        }
        report = get_ensemble_health(
            outcomes, min_trades=30, decay_window=20, decay_threshold=0.45,
        )
        decay_alerts = [a for a in report.alerts if "decayed" in a]
        assert len(decay_alerts) >= 1

    def test_critical_alert_message(self) -> None:
        """Critical ensemble should have CRITICAL alert."""
        outcomes = {
            f"sig_{i:02d}": _outcomes(0.50, 100) for i in range(19)
        }
        report = get_ensemble_health(outcomes, min_trades=30)
        critical_alerts = [a for a in report.alerts if "CRITICAL" in a]
        assert len(critical_alerts) == 1

    def test_mean_win_rate_computed(self) -> None:
        """Mean win rate should reflect signal win rates."""
        outcomes = {
            "a": _outcomes(0.60, 100),
            "b": _outcomes(0.80, 100),
        }
        report = get_ensemble_health(outcomes, min_trades=30)
        assert 0.65 < report.mean_win_rate < 0.75

    def test_empty_outcomes(self) -> None:
        """Empty dict should return 0 counts and critical quality."""
        report = get_ensemble_health({})
        assert report.total_signals == 0
        assert report.active_count == 0
        assert report.ensemble_quality == "critical"


# ---------------------------------------------------------------------------
# compute_regime_weights
# ---------------------------------------------------------------------------

class TestComputeRegimeWeights:
    """Tests for compute_regime_weights."""

    def _make_base_weights(self) -> list[SignalWeight]:
        """Create base weights for 3 test signals."""
        return [
            SignalWeight("bos_confirms", 1.0, 0.01, True, False, 0.65, 100),
            SignalWeight("cot_confirms", 1.0, 0.01, True, False, 0.65, 100),
            SignalWeight("fund_confirms", 1.0, 0.01, True, False, 0.65, 100),
        ]

    def test_risk_off_boosts_cot(self) -> None:
        """RISK_OFF should boost cot_confirms by 1.5x."""
        base = self._make_base_weights()
        adjusted = compute_regime_weights(base, "RISK_OFF")
        cot = next(w for w in adjusted if w.signal_id == "cot_confirms")
        assert cot.weight == pytest.approx(1.5)

    def test_risk_off_reduces_bos(self) -> None:
        """RISK_OFF should reduce bos_confirms by 0.5x."""
        base = self._make_base_weights()
        adjusted = compute_regime_weights(base, "RISK_OFF")
        bos = next(w for w in adjusted if w.signal_id == "bos_confirms")
        assert bos.weight == pytest.approx(0.5)

    def test_crisis_reduces_most(self) -> None:
        """CRISIS should reduce bos_confirms to 0.3x."""
        base = self._make_base_weights()
        adjusted = compute_regime_weights(base, "CRISIS")
        bos = next(w for w in adjusted if w.signal_id == "bos_confirms")
        assert bos.weight == pytest.approx(0.3)

    def test_crisis_keeps_cot_at_1(self) -> None:
        """CRISIS should keep cot_confirms at 1.0."""
        base = self._make_base_weights()
        adjusted = compute_regime_weights(base, "CRISIS")
        cot = next(w for w in adjusted if w.signal_id == "cot_confirms")
        assert cot.weight == pytest.approx(1.0)

    def test_normal_no_change(self) -> None:
        """NORMAL should keep all weights at 1.0."""
        base = self._make_base_weights()
        adjusted = compute_regime_weights(base, "NORMAL")
        for w in adjusted:
            assert w.weight == pytest.approx(1.0)

    def test_unknown_regime_no_change(self) -> None:
        """Unknown regime should apply default=1.0 (no change)."""
        base = self._make_base_weights()
        adjusted = compute_regime_weights(base, "UNICORN")
        for w in adjusted:
            assert w.weight == pytest.approx(1.0)

    def test_clamp_to_two(self) -> None:
        """Regime multiplier should not push weight above 2.0."""
        base = [SignalWeight("cot_confirms", 1.8, 0.01, True, False, 0.7, 100)]
        adjusted = compute_regime_weights(base, "RISK_OFF")
        assert adjusted[0].weight <= 2.0

    def test_custom_multipliers(self) -> None:
        """Custom regime_multipliers should override defaults."""
        base = self._make_base_weights()
        custom = {"TURBO": {"cot_confirms": 2.0, "default": 0.1}}
        adjusted = compute_regime_weights(base, "TURBO", custom)
        cot = next(w for w in adjusted if w.signal_id == "cot_confirms")
        bos = next(w for w in adjusted if w.signal_id == "bos_confirms")
        assert cot.weight == pytest.approx(2.0)
        assert bos.weight == pytest.approx(0.1)


# ---------------------------------------------------------------------------
# cusum_change_detection
# ---------------------------------------------------------------------------

class TestCusumChangeDetection:
    """Tests for cusum_change_detection."""

    def test_stable_sequence_no_detection(self) -> None:
        """A constant sequence should not trigger detection."""
        values = [0.55] * 50
        detected, idx = cusum_change_detection(values)
        assert not detected
        assert idx is None

    def test_shifted_sequence_detected(self) -> None:
        """A sequence with a clear shift should be detected."""
        values = [0.55] * 50 + [0.90] * 50
        detected, idx = cusum_change_detection(values, delta=0.05, threshold=3.0)
        assert detected
        assert idx is not None
        # CUSUM uses the global mean so it accumulates from early values;
        # change point index is where the cumulative sum first exceeds threshold.
        assert 0 <= idx < 100

    def test_empty_sequence(self) -> None:
        """Empty sequence returns no detection."""
        detected, idx = cusum_change_detection([])
        assert not detected
        assert idx is None

    def test_single_value(self) -> None:
        """Single value returns no detection."""
        detected, idx = cusum_change_detection([0.5])
        assert not detected
        assert idx is None

    def test_gradual_drift_may_detect(self) -> None:
        """Gradual drift with steep enough change can be detected."""
        values = [0.50 + i * 0.01 for i in range(100)]
        detected, _ = cusum_change_detection(values, delta=0.01, threshold=2.0)
        # With such a steep drift, CUSUM should detect
        assert detected

    def test_high_threshold_no_detection(self) -> None:
        """Very high threshold should not trigger even on shifted data."""
        values = [0.55] * 50 + [0.60] * 50
        detected, idx = cusum_change_detection(
            values, delta=0.05, threshold=999.0,
        )
        assert not detected
        assert idx is None


# ---------------------------------------------------------------------------
# Weighted scoring integration (scoring.py)
# ---------------------------------------------------------------------------

class TestCalculateWeightedConfluence:
    """Tests for calculate_weighted_confluence in scoring.py."""

    def test_none_weights_falls_back(self) -> None:
        """Passing weights=None should produce same result as calculate_confluence."""
        from src.analysis.scoring import (
            calculate_confluence,
            calculate_weighted_confluence,
        )
        from src.core.models import ScoringInput

        inp = ScoringInput(
            above_sma200=True, momentum_confirms=True,
            cot_confirms=True, cot_strong=True,
            at_level_now=True, htf_level_nearby=True,
            trend_congruent=True, no_event_risk=True,
            news_confirms=True, fund_confirms=True,
            bos_confirms=True, smc_struct_confirms=True,
        )
        original = calculate_confluence(inp)
        weighted = calculate_weighted_confluence(inp, weights=None)
        assert original.score == weighted.score
        assert original.grade == weighted.grade

    def test_weighted_all_ones_similar_to_unweighted(self) -> None:
        """Weights all = 1.0 should give similar grade as unweighted."""
        from src.analysis.scoring import (
            _SIGNAL_IDS,
            calculate_weighted_confluence,
        )
        from src.core.models import ScoringInput

        inp = ScoringInput(
            above_sma200=True, momentum_confirms=True,
            cot_confirms=True, cot_strong=True,
            at_level_now=True, htf_level_nearby=True,
            trend_congruent=True, no_event_risk=True,
            news_confirms=True, fund_confirms=True,
            bos_confirms=True, smc_struct_confirms=True,
        )
        weights = {sid: 1.0 for sid in _SIGNAL_IDS}
        result = calculate_weighted_confluence(inp, weights=weights)
        # With 16/19 passing (12 True + 4 auto-pass), should be a good grade
        assert result.grade in ("A+", "A", "B")
        assert result.score >= 10

    def test_zero_weights_produce_low_score(self) -> None:
        """All weights = 0 should produce score 0 and grade C."""
        from src.analysis.scoring import (
            _SIGNAL_IDS,
            calculate_weighted_confluence,
        )
        from src.core.models import ScoringInput

        inp = ScoringInput(
            above_sma200=True, momentum_confirms=True,
            cot_confirms=True, cot_strong=True,
            at_level_now=True, htf_level_nearby=True,
            trend_congruent=True, no_event_risk=True,
            news_confirms=True, fund_confirms=True,
            bos_confirms=True, smc_struct_confirms=True,
        )
        weights = {sid: 0.0 for sid in _SIGNAL_IDS}
        result = calculate_weighted_confluence(inp, weights=weights)
        assert result.score == 0
        assert result.grade == "C"

    def test_high_weights_boost_grade(self) -> None:
        """High weights on passing signals should produce high grade."""
        from src.analysis.scoring import (
            _SIGNAL_IDS,
            calculate_weighted_confluence,
        )
        from src.core.models import ScoringInput

        inp = ScoringInput(
            above_sma200=True, momentum_confirms=True,
            cot_confirms=True, cot_strong=True,
            at_level_now=True, htf_level_nearby=True,
            trend_congruent=True, no_event_risk=True,
            news_confirms=True, fund_confirms=True,
            bos_confirms=True, smc_struct_confirms=True,
        )
        weights = {sid: 2.0 for sid in _SIGNAL_IDS}
        result = calculate_weighted_confluence(inp, weights=weights)
        assert result.grade in ("A+", "A")
