"""
Out-of-sample validation for Cot-ExplorerV2 backtesting strategies.

Pure functions for generating purged cross-validation splits and analyzing
backtest results for overfitting. No I/O, no BacktestEngine dependency --
callers run the actual backtests on each split and pass metrics back here.

Key concepts:
  - Purged K-Fold: removes samples between train/test to prevent leakage
  - Embargo: removes samples after test to prevent forward-looking bias
  - CPCV: Combinatorial Purged Cross-Validation (all C(N,k) test groups)
  - PBO: Probability of Backtest Overfitting (fraction where best IS fails OOS)
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass


@dataclass(frozen=True)
class FoldSplit:
    """A single train/test split with purge and embargo."""

    train_indices: list[int]
    test_indices: list[int]
    purge_start: int
    purge_end: int


@dataclass(frozen=True)
class CPCVResult:
    """Combinatorial Purged Cross-Validation results."""

    n_splits: int
    n_combinations: int
    is_results: list[float]
    oos_results: list[float]
    pbo: float
    mean_oos: float
    std_oos: float
    is_significant: bool


@dataclass(frozen=True)
class HoldoutResult:
    """Holdout validation result."""

    train_metric: float
    test_metric: float
    degradation_pct: float
    is_overfit: bool


def purged_kfold_split(
    n_samples: int,
    n_splits: int = 5,
    purge_gap: int = 5,
    embargo_gap: int = 3,
) -> list[FoldSplit]:
    """Generate K-fold splits with purge and embargo gaps.

    Purge: remove ``purge_gap`` samples between train end and test start.
    Embargo: remove ``embargo_gap`` samples after test end before next train.
    This prevents information leakage in time-series data.

    Args:
        n_samples: Total number of samples in the dataset.
        n_splits: Number of folds (default 5).
        purge_gap: Samples removed before the test set (default 5).
        embargo_gap: Samples removed after the test set (default 3).

    Returns:
        List of FoldSplit objects, one per fold.

    Raises:
        ValueError: If n_samples is too small for the requested configuration.
    """
    if n_splits < 2:
        raise ValueError("n_splits must be >= 2")
    if n_samples < n_splits:
        raise ValueError(
            f"n_samples ({n_samples}) must be >= n_splits ({n_splits})"
        )

    all_indices = list(range(n_samples))
    fold_size = n_samples // n_splits
    if fold_size == 0:
        raise ValueError(
            f"Fold size is 0: n_samples={n_samples}, n_splits={n_splits}"
        )

    folds: list[list[int]] = []
    for i in range(n_splits):
        start = i * fold_size
        end = start + fold_size if i < n_splits - 1 else n_samples
        folds.append(all_indices[start:end])

    result: list[FoldSplit] = []
    for test_fold_idx in range(n_splits):
        test_indices = folds[test_fold_idx]
        test_start = test_indices[0]
        test_end = test_indices[-1]

        purge_start_idx = max(0, test_start - purge_gap)
        purge_end_idx = min(n_samples - 1, test_end + embargo_gap)

        excluded = set(range(purge_start_idx, test_end + embargo_gap + 1))
        excluded.update(test_indices)

        train_indices = [i for i in all_indices if i not in excluded]

        if not train_indices:
            continue

        result.append(FoldSplit(
            train_indices=train_indices,
            test_indices=test_indices,
            purge_start=purge_start_idx,
            purge_end=purge_end_idx,
        ))

    return result


def combinatorial_splits(
    n_samples: int,
    n_groups: int = 5,
    n_test_groups: int = 2,
    purge_gap: int = 5,
) -> list[FoldSplit]:
    """Generate all C(n_groups, n_test_groups) combinations of test groups.

    For n_groups=5, n_test_groups=2: generates C(5,2)=10 unique splits.
    Each split uses n_test_groups as test, rest as train, with purge gaps
    between adjacent train/test boundaries.

    Args:
        n_samples: Total number of samples.
        n_groups: Number of contiguous groups to partition data into.
        n_test_groups: Number of groups to use as test per split.
        purge_gap: Samples purged at each train/test boundary.

    Returns:
        List of FoldSplit objects, one per combination.

    Raises:
        ValueError: If configuration is invalid.
    """
    if n_groups < 2:
        raise ValueError("n_groups must be >= 2")
    if n_test_groups < 1 or n_test_groups >= n_groups:
        raise ValueError(
            f"n_test_groups ({n_test_groups}) must be in [1, {n_groups - 1}]"
        )
    if n_samples < n_groups:
        raise ValueError(
            f"n_samples ({n_samples}) must be >= n_groups ({n_groups})"
        )

    all_indices = list(range(n_samples))
    group_size = n_samples // n_groups

    groups: list[list[int]] = []
    for i in range(n_groups):
        start = i * group_size
        end = start + group_size if i < n_groups - 1 else n_samples
        groups.append(all_indices[start:end])

    result: list[FoldSplit] = []
    for test_combo in itertools.combinations(range(n_groups), n_test_groups):
        test_set = set(test_combo)
        test_indices: list[int] = []
        for gi in test_combo:
            test_indices.extend(groups[gi])

        test_index_set = set(test_indices)

        purge_indices: set[int] = set()
        for gi in test_combo:
            group_start = groups[gi][0]
            group_end = groups[gi][-1]
            for p in range(max(0, group_start - purge_gap), group_start):
                purge_indices.add(p)
            for p in range(group_end + 1, min(n_samples, group_end + purge_gap + 1)):
                purge_indices.add(p)

        excluded = test_index_set | purge_indices
        train_indices = [i for i in all_indices if i not in excluded]

        if not train_indices or not test_indices:
            continue

        purge_sorted = sorted(purge_indices) if purge_indices else [0]
        result.append(FoldSplit(
            train_indices=train_indices,
            test_indices=sorted(test_indices),
            purge_start=purge_sorted[0],
            purge_end=purge_sorted[-1],
        ))

    return result


def probability_of_backtest_overfit(
    is_metrics: list[float],
    oos_metrics: list[float],
) -> float:
    """Compute PBO: fraction of combinations where the best in-sample
    performer has negative out-of-sample performance.

    For each combination index, the IS-best configuration is identified.
    PBO counts how often that best-IS pick has OOS < 0.

    A PBO > 0.40 means the strategy is likely overfit.

    Args:
        is_metrics: In-sample metric per combination (higher = better).
        oos_metrics: Out-of-sample metric per combination (same ordering).

    Returns:
        PBO value in [0.0, 1.0].

    Raises:
        ValueError: If input lists are empty or mismatched in length.
    """
    if not is_metrics or not oos_metrics:
        raise ValueError("Metric lists must not be empty")
    if len(is_metrics) != len(oos_metrics):
        raise ValueError(
            f"Length mismatch: is_metrics={len(is_metrics)}, "
            f"oos_metrics={len(oos_metrics)}"
        )

    n = len(is_metrics)
    if n == 1:
        return 0.0 if oos_metrics[0] >= 0 else 1.0

    overfit_count = 0
    for i in range(n):
        is_rank_i = sum(1 for j in range(n) if is_metrics[j] > is_metrics[i])
        if is_rank_i == 0:
            if oos_metrics[i] < 0:
                overfit_count += 1

    best_is_count = sum(
        1 for i in range(n)
        if all(is_metrics[i] >= is_metrics[j] for j in range(n))
    )

    if best_is_count == 0:
        return 0.0

    overfit_among_best = sum(
        1 for i in range(n)
        if all(is_metrics[i] >= is_metrics[j] for j in range(n))
        and oos_metrics[i] < 0
    )

    return overfit_among_best / best_is_count


def holdout_split(
    n_samples: int,
    holdout_pct: float = 0.20,
    purge_gap: int = 5,
) -> tuple[list[int], list[int]]:
    """Reserve last holdout_pct of data as untouchable test set.

    Returns (train_indices, test_indices) with purge gap between them.

    Args:
        n_samples: Total number of samples.
        holdout_pct: Fraction of data to reserve for test (default 0.20).
        purge_gap: Samples to remove between train and test (default 5).

    Returns:
        Tuple of (train_indices, test_indices).

    Raises:
        ValueError: If holdout_pct not in (0, 1) or n_samples too small.
    """
    if not 0.0 < holdout_pct < 1.0:
        raise ValueError(f"holdout_pct must be in (0, 1), got {holdout_pct}")
    if n_samples < 3:
        raise ValueError(f"n_samples must be >= 3, got {n_samples}")

    test_size = max(1, int(n_samples * holdout_pct))
    split_point = n_samples - test_size

    train_end = max(0, split_point - purge_gap)
    train_indices = list(range(train_end))
    test_indices = list(range(split_point, n_samples))

    if not train_indices:
        train_indices = list(range(max(1, split_point)))
    if not test_indices:
        test_indices = list(range(n_samples - 1, n_samples))

    return train_indices, test_indices


def assess_degradation(
    train_metric: float,
    test_metric: float,
    threshold_pct: float = 30.0,
) -> HoldoutResult:
    """Compare train vs test performance to detect overfitting.

    degradation_pct = (train - test) / abs(train) * 100
    is_overfit = degradation_pct > threshold_pct

    Args:
        train_metric: In-sample performance metric.
        test_metric: Out-of-sample performance metric.
        threshold_pct: Degradation percentage above which overfitting
            is flagged (default 30.0).

    Returns:
        HoldoutResult with degradation analysis.
    """
    if train_metric == 0.0:
        degradation = 0.0 if test_metric >= 0.0 else 100.0
    else:
        degradation = (train_metric - test_metric) / abs(train_metric) * 100.0

    return HoldoutResult(
        train_metric=train_metric,
        test_metric=test_metric,
        degradation_pct=round(degradation, 4),
        is_overfit=degradation > threshold_pct,
    )


def validate_strategy_oos(
    is_results_by_param: dict[str, list[float]],
    oos_results_by_param: dict[str, list[float]],
) -> CPCVResult:
    """Full CPCV analysis: compute PBO, mean OOS, significance.

    Each key in the dicts is a parameter-set name. The value is a list of
    metric values (one per fold/combination). Both dicts must have the
    same keys.

    Args:
        is_results_by_param: {param_set_name: [metric per fold]}.
        oos_results_by_param: {param_set_name: [metric per fold]}.

    Returns:
        CPCVResult with aggregated statistics.

    Raises:
        ValueError: If inputs are empty or keys don't match.
    """
    if not is_results_by_param or not oos_results_by_param:
        raise ValueError("Result dicts must not be empty")

    is_keys = set(is_results_by_param.keys())
    oos_keys = set(oos_results_by_param.keys())
    if is_keys != oos_keys:
        raise ValueError(
            f"Key mismatch: IS has {is_keys - oos_keys} extra, "
            f"OOS has {oos_keys - is_keys} extra"
        )

    is_means: list[float] = []
    oos_means: list[float] = []
    for param_name in sorted(is_results_by_param.keys()):
        is_vals = is_results_by_param[param_name]
        oos_vals = oos_results_by_param[param_name]
        if not is_vals or not oos_vals:
            continue
        is_means.append(sum(is_vals) / len(is_vals))
        oos_means.append(sum(oos_vals) / len(oos_vals))

    if not is_means:
        return CPCVResult(
            n_splits=0, n_combinations=0,
            is_results=[], oos_results=[],
            pbo=0.0, mean_oos=0.0, std_oos=0.0,
            is_significant=False,
        )

    pbo = probability_of_backtest_overfit(is_means, oos_means)

    mean_oos = sum(oos_means) / len(oos_means)
    variance = (
        sum((x - mean_oos) ** 2 for x in oos_means) / len(oos_means)
    )
    std_oos = variance ** 0.5

    n_folds = max(
        len(v)
        for v in is_results_by_param.values()
        if v
    )

    return CPCVResult(
        n_splits=n_folds,
        n_combinations=len(is_means),
        is_results=is_means,
        oos_results=oos_means,
        pbo=round(pbo, 4),
        mean_oos=round(mean_oos, 6),
        std_oos=round(std_oos, 6),
        is_significant=mean_oos > 0,
    )
