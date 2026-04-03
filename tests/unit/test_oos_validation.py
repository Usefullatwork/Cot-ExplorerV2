"""Unit tests for src.trading.backtesting.oos_validation — purged CV, PBO, holdout."""

from __future__ import annotations

import pytest

from src.trading.backtesting.oos_validation import (
    CPCVResult,
    FoldSplit,
    HoldoutResult,
    assess_degradation,
    combinatorial_splits,
    holdout_split,
    probability_of_backtest_overfit,
    purged_kfold_split,
    validate_strategy_oos,
)

# ===========================================================================
# purged_kfold_split
# ===========================================================================


def test_purged_kfold_returns_correct_number_of_folds():
    """5-fold split on 100 samples -> 5 FoldSplit objects."""
    splits = purged_kfold_split(100, n_splits=5)
    assert len(splits) == 5


def test_purged_kfold_no_overlap():
    """Train and test indices must never overlap within a fold."""
    splits = purged_kfold_split(100, n_splits=5, purge_gap=5, embargo_gap=3)
    for fold in splits:
        train_set = set(fold.train_indices)
        test_set = set(fold.test_indices)
        assert train_set.isdisjoint(test_set), "Train/test overlap detected"


def test_purged_kfold_purge_gap_exists():
    """No train index should be within purge_gap of the test start."""
    purge_gap = 5
    splits = purged_kfold_split(100, n_splits=5, purge_gap=purge_gap, embargo_gap=3)
    for fold in splits:
        test_start = min(fold.test_indices)
        purge_zone = set(range(max(0, test_start - purge_gap), test_start))
        train_set = set(fold.train_indices)
        overlap = train_set & purge_zone
        assert not overlap, f"Train indices {overlap} violate purge gap"


def test_purged_kfold_embargo_gap_exists():
    """No train index should be within embargo_gap after the test end."""
    embargo_gap = 3
    splits = purged_kfold_split(100, n_splits=5, purge_gap=5, embargo_gap=embargo_gap)
    for fold in splits:
        test_end = max(fold.test_indices)
        embargo_zone = set(range(test_end + 1, min(100, test_end + embargo_gap + 1)))
        train_set = set(fold.train_indices)
        overlap = train_set & embargo_zone
        assert not overlap, f"Train indices {overlap} violate embargo gap"


def test_purged_kfold_all_test_indices_covered():
    """Union of all test sets should cover all 100 indices."""
    splits = purged_kfold_split(100, n_splits=5, purge_gap=0, embargo_gap=0)
    all_test = set()
    for fold in splits:
        all_test.update(fold.test_indices)
    assert all_test == set(range(100))


def test_purged_kfold_fold_split_is_frozen():
    """FoldSplit is a frozen dataclass."""
    fold = FoldSplit(
        train_indices=[0, 1], test_indices=[2, 3],
        purge_start=1, purge_end=4,
    )
    with pytest.raises(AttributeError):
        fold.train_indices = [5, 6]  # type: ignore[misc]


def test_purged_kfold_too_few_samples():
    """n_samples < n_splits should raise ValueError."""
    with pytest.raises(ValueError, match="n_samples"):
        purged_kfold_split(3, n_splits=5)


def test_purged_kfold_n_splits_less_than_2():
    """n_splits < 2 should raise ValueError."""
    with pytest.raises(ValueError, match="n_splits"):
        purged_kfold_split(100, n_splits=1)


# ===========================================================================
# combinatorial_splits
# ===========================================================================


def test_combinatorial_correct_count():
    """C(5,2) = 10 combinations."""
    splits = combinatorial_splits(100, n_groups=5, n_test_groups=2)
    assert len(splits) == 10


def test_combinatorial_each_split_has_train_and_test():
    """Every combination must have both train and test indices."""
    splits = combinatorial_splits(100, n_groups=5, n_test_groups=2, purge_gap=3)
    for fold in splits:
        assert len(fold.train_indices) > 0, "Empty train set"
        assert len(fold.test_indices) > 0, "Empty test set"


def test_combinatorial_no_overlap():
    """Train and test must not overlap in any combination."""
    splits = combinatorial_splits(100, n_groups=5, n_test_groups=2, purge_gap=3)
    for fold in splits:
        train_set = set(fold.train_indices)
        test_set = set(fold.test_indices)
        assert train_set.isdisjoint(test_set), "Train/test overlap"


def test_combinatorial_c_4_1():
    """C(4,1) = 4 combinations."""
    splits = combinatorial_splits(80, n_groups=4, n_test_groups=1, purge_gap=2)
    assert len(splits) == 4


def test_combinatorial_test_groups_cover_all():
    """Each index should appear in at least one test set (with zero purge)."""
    splits = combinatorial_splits(50, n_groups=5, n_test_groups=2, purge_gap=0)
    all_test = set()
    for fold in splits:
        all_test.update(fold.test_indices)
    assert all_test == set(range(50))


def test_combinatorial_invalid_n_groups():
    """n_groups < 2 should raise ValueError."""
    with pytest.raises(ValueError, match="n_groups"):
        combinatorial_splits(100, n_groups=1, n_test_groups=1)


def test_combinatorial_invalid_n_test_groups():
    """n_test_groups >= n_groups should raise ValueError."""
    with pytest.raises(ValueError, match="n_test_groups"):
        combinatorial_splits(100, n_groups=5, n_test_groups=5)


def test_combinatorial_too_few_samples():
    """n_samples < n_groups should raise ValueError."""
    with pytest.raises(ValueError, match="n_samples"):
        combinatorial_splits(3, n_groups=5, n_test_groups=2)


# ===========================================================================
# probability_of_backtest_overfit
# ===========================================================================


def test_pbo_detects_overfitting():
    """Best IS performer has negative OOS -> PBO = 1.0."""
    is_metrics = [0.5, 0.3, 0.1]
    oos_metrics = [-0.2, 0.1, 0.05]
    pbo = probability_of_backtest_overfit(is_metrics, oos_metrics)
    assert pbo == 1.0


def test_pbo_detects_robustness():
    """Best IS performer has best OOS -> PBO = 0.0."""
    is_metrics = [0.5, 0.3, 0.1]
    oos_metrics = [0.4, 0.2, 0.05]
    pbo = probability_of_backtest_overfit(is_metrics, oos_metrics)
    assert pbo == 0.0


def test_pbo_partial_overfit():
    """Two tied IS-best; one has negative OOS -> PBO = 0.5."""
    is_metrics = [0.5, 0.5, 0.1]
    oos_metrics = [-0.1, 0.3, 0.2]
    pbo = probability_of_backtest_overfit(is_metrics, oos_metrics)
    assert pbo == 0.5


def test_pbo_single_combination():
    """Single combination with positive OOS -> PBO = 0.0."""
    pbo = probability_of_backtest_overfit([0.5], [0.3])
    assert pbo == 0.0


def test_pbo_single_combination_negative():
    """Single combination with negative OOS -> PBO = 1.0."""
    pbo = probability_of_backtest_overfit([0.5], [-0.1])
    assert pbo == 1.0


def test_pbo_empty_raises():
    """Empty metric lists should raise ValueError."""
    with pytest.raises(ValueError, match="must not be empty"):
        probability_of_backtest_overfit([], [])


def test_pbo_length_mismatch_raises():
    """Mismatched list lengths should raise ValueError."""
    with pytest.raises(ValueError, match="Length mismatch"):
        probability_of_backtest_overfit([0.5, 0.3], [0.1])


# ===========================================================================
# holdout_split
# ===========================================================================


def test_holdout_80_20_split():
    """80/20 split on 100 samples: ~80 train, 20 test."""
    train, test = holdout_split(100, holdout_pct=0.20, purge_gap=5)
    assert len(test) == 20
    assert max(train) < min(test), "Train must come before test"


def test_holdout_purge_gap_respected():
    """There must be a gap between last train index and first test index."""
    purge_gap = 5
    train, test = holdout_split(100, holdout_pct=0.20, purge_gap=purge_gap)
    gap = min(test) - max(train)
    assert gap >= purge_gap, f"Gap {gap} < purge_gap {purge_gap}"


def test_holdout_no_overlap():
    """Train and test must not overlap."""
    train, test = holdout_split(100, holdout_pct=0.20, purge_gap=5)
    assert set(train).isdisjoint(set(test))


def test_holdout_small_dataset():
    """10 samples with 20% holdout should still produce valid splits."""
    train, test = holdout_split(10, holdout_pct=0.20, purge_gap=1)
    assert len(test) >= 1
    assert len(train) >= 1


def test_holdout_invalid_pct_zero():
    """holdout_pct=0 should raise ValueError."""
    with pytest.raises(ValueError, match="holdout_pct"):
        holdout_split(100, holdout_pct=0.0)


def test_holdout_invalid_pct_one():
    """holdout_pct=1.0 should raise ValueError."""
    with pytest.raises(ValueError, match="holdout_pct"):
        holdout_split(100, holdout_pct=1.0)


def test_holdout_too_few_samples():
    """n_samples < 3 should raise ValueError."""
    with pytest.raises(ValueError, match="n_samples"):
        holdout_split(2, holdout_pct=0.20)


# ===========================================================================
# assess_degradation
# ===========================================================================


def test_degradation_overfit_detected():
    """50% degradation with 30% threshold -> is_overfit=True."""
    result = assess_degradation(train_metric=1.0, test_metric=0.5)
    assert result.is_overfit is True
    assert result.degradation_pct == 50.0


def test_degradation_healthy():
    """10% degradation with 30% threshold -> is_overfit=False."""
    result = assess_degradation(train_metric=1.0, test_metric=0.9)
    assert result.is_overfit is False
    assert abs(result.degradation_pct - 10.0) < 0.01


def test_degradation_test_better_than_train():
    """Test outperforms train -> negative degradation, not overfit."""
    result = assess_degradation(train_metric=1.0, test_metric=1.5)
    assert result.is_overfit is False
    assert result.degradation_pct < 0


def test_degradation_zero_train():
    """Train=0 with negative test -> degradation=100."""
    result = assess_degradation(train_metric=0.0, test_metric=-0.5)
    assert result.degradation_pct == 100.0
    assert result.is_overfit is True


def test_degradation_zero_train_positive_test():
    """Train=0 with positive test -> degradation=0."""
    result = assess_degradation(train_metric=0.0, test_metric=0.5)
    assert result.degradation_pct == 0.0
    assert result.is_overfit is False


def test_degradation_custom_threshold():
    """Custom threshold of 10% flags 15% degradation."""
    result = assess_degradation(
        train_metric=1.0, test_metric=0.85, threshold_pct=10.0,
    )
    assert result.is_overfit is True


def test_degradation_holdout_result_frozen():
    """HoldoutResult is a frozen dataclass."""
    result = assess_degradation(1.0, 0.5)
    with pytest.raises(AttributeError):
        result.is_overfit = False  # type: ignore[misc]


# ===========================================================================
# validate_strategy_oos
# ===========================================================================


def test_validate_oos_integration_overfit():
    """Overfit scenario: best IS param has worst OOS -> high PBO."""
    is_results = {
        "aggressive": [0.8, 0.9, 0.7],
        "moderate": [0.5, 0.4, 0.6],
        "conservative": [0.3, 0.2, 0.4],
    }
    oos_results = {
        "aggressive": [-0.5, -0.4, -0.3],
        "moderate": [-0.1, -0.05, 0.0],
        "conservative": [0.05, 0.1, 0.0],
    }
    result = validate_strategy_oos(is_results, oos_results)
    assert isinstance(result, CPCVResult)
    assert result.pbo == 1.0
    assert result.n_combinations == 3
    assert result.n_splits == 3
    assert result.mean_oos < 0
    assert result.is_significant is False


def test_validate_oos_integration_robust():
    """Robust scenario: best IS param also best OOS -> PBO=0."""
    is_results = {
        "param_a": [0.6, 0.7, 0.65],
        "param_b": [0.4, 0.35, 0.5],
    }
    oos_results = {
        "param_a": [0.5, 0.55, 0.6],
        "param_b": [0.3, 0.25, 0.35],
    }
    result = validate_strategy_oos(is_results, oos_results)
    assert result.pbo == 0.0
    assert result.is_significant is True
    assert result.mean_oos > 0


def test_validate_oos_std_calculation():
    """Std should be > 0 when OOS results vary across params."""
    is_results = {
        "p1": [0.5], "p2": [0.3], "p3": [0.1],
    }
    oos_results = {
        "p1": [0.4], "p2": [0.1], "p3": [-0.2],
    }
    result = validate_strategy_oos(is_results, oos_results)
    assert result.std_oos > 0


def test_validate_oos_empty_raises():
    """Empty dicts should raise ValueError."""
    with pytest.raises(ValueError, match="must not be empty"):
        validate_strategy_oos({}, {})


def test_validate_oos_key_mismatch_raises():
    """Mismatched keys should raise ValueError."""
    with pytest.raises(ValueError, match="Key mismatch"):
        validate_strategy_oos(
            {"a": [0.5]},
            {"b": [0.3]},
        )


# ===========================================================================
# Edge cases: very small datasets
# ===========================================================================


def test_small_dataset_purged_kfold():
    """10 samples, 2 folds should work without error."""
    splits = purged_kfold_split(10, n_splits=2, purge_gap=1, embargo_gap=1)
    assert len(splits) == 2
    for fold in splits:
        assert len(fold.train_indices) > 0
        assert len(fold.test_indices) > 0


def test_small_dataset_combinatorial():
    """15 samples, 3 groups, 1 test group."""
    splits = combinatorial_splits(15, n_groups=3, n_test_groups=1, purge_gap=1)
    assert len(splits) == 3


def test_small_dataset_holdout():
    """5 samples with small purge gap."""
    train, test = holdout_split(5, holdout_pct=0.40, purge_gap=0)
    assert len(test) >= 1
    assert len(train) >= 1


def test_purge_gap_larger_than_fold_size():
    """Purge gap larger than fold -> train may be very small but still valid."""
    splits = purged_kfold_split(20, n_splits=2, purge_gap=8, embargo_gap=0)
    assert len(splits) >= 1
    for fold in splits:
        assert set(fold.train_indices).isdisjoint(set(fold.test_indices))


def test_combinatorial_large_purge():
    """Large purge gap relative to group size should still produce results."""
    splits = combinatorial_splits(50, n_groups=5, n_test_groups=1, purge_gap=8)
    assert len(splits) == 5
    for fold in splits:
        assert set(fold.train_indices).isdisjoint(set(fold.test_indices))
