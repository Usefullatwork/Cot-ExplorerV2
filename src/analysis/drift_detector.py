"""Distribution drift detection for signal and feature monitoring.

Provides pure statistical tests (Page-Hinkley, Kolmogorov-Smirnov,
two-proportion z-test) to detect when signal accuracy or feature
distributions have shifted.  Used by the weekly retrain pipeline
to decide whether model reweighting is needed.

All functions are pure -- no I/O, no DB, no side effects.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Sequence

from scipy import stats as scipy_stats

# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DriftResult:
    """Result of a single drift test."""

    test_name: str
    statistic: float
    p_value: float
    is_drifted: bool
    change_point: int | None  # index where drift detected (if applicable)
    description: str


@dataclass(frozen=True)
class DriftReport:
    """Complete drift analysis across multiple features."""

    results: list[DriftResult]
    any_drift: bool
    critical_drifts: int   # count of drifts with p < 0.01
    warning_drifts: int    # count of drifts with 0.01 <= p < 0.05


# ---------------------------------------------------------------------------
# Page-Hinkley change detection
# ---------------------------------------------------------------------------


def page_hinkley_test(
    values: Sequence[float],
    delta: float = 0.05,
    threshold: float = 5.0,
) -> DriftResult:
    """Page-Hinkley change detection test.

    Detects a change in the mean of a sequence.

    Algorithm:
    1. Compute cumulative sum: m_t = sum(x_i - mean(x) - delta) for i=0..t
    2. Track minimum: M_t = min(m_0..m_t)
    3. Test statistic: PH_t = m_t - M_t
    4. If PH_t > threshold at any t: drift detected at that point

    Args:
        values: Sequence of observed values.
        delta: Minimum magnitude of change to detect.
        threshold: Alarm threshold for the PH test statistic.

    Returns:
        DriftResult with change_point = first t where PH_t > threshold.
    """
    n = len(values)
    if n < 2:
        return DriftResult(
            test_name="page_hinkley",
            statistic=0.0,
            p_value=1.0,
            is_drifted=False,
            change_point=None,
            description="Insufficient data (need >= 2 values).",
        )

    mean_val = sum(values) / n
    cumsum = 0.0
    min_cumsum = 0.0
    max_ph = 0.0

    for i, val in enumerate(values):
        cumsum += val - mean_val - delta
        if cumsum < min_cumsum:
            min_cumsum = cumsum
        ph_stat = cumsum - min_cumsum
        if ph_stat > max_ph:
            max_ph = ph_stat

        if ph_stat > threshold:
            return DriftResult(
                test_name="page_hinkley",
                statistic=ph_stat,
                p_value=0.0,  # exact p-value not available for PH
                is_drifted=True,
                change_point=i,
                description=(
                    f"Change detected at index {i} "
                    f"(PH={ph_stat:.4f} > threshold={threshold})."
                ),
            )

    return DriftResult(
        test_name="page_hinkley",
        statistic=max_ph,
        p_value=1.0,  # no alarm triggered
        is_drifted=False,
        change_point=None,
        description=f"No drift detected (max PH={max_ph:.4f}).",
    )


# ---------------------------------------------------------------------------
# Kolmogorov-Smirnov distribution drift
# ---------------------------------------------------------------------------


def ks_distribution_drift(
    window_a: Sequence[float],
    window_b: Sequence[float],
    alpha: float = 0.05,
) -> DriftResult:
    """Kolmogorov-Smirnov test for distribution drift between two windows.

    Uses scipy.stats.ks_2samp(window_a, window_b).
    is_drifted = p_value < alpha.

    Args:
        window_a: First sample (e.g. historical window).
        window_b: Second sample (e.g. current window).
        alpha: Significance level for drift detection.

    Returns:
        DriftResult with KS statistic and p-value.
    """
    if len(window_a) < 2 or len(window_b) < 2:
        return DriftResult(
            test_name="ks_2samp",
            statistic=0.0,
            p_value=1.0,
            is_drifted=False,
            change_point=None,
            description="Insufficient data (need >= 2 values per window).",
        )

    stat, p_val = scipy_stats.ks_2samp(window_a, window_b)
    is_drifted = p_val < alpha

    desc = (
        f"KS statistic={stat:.4f}, p={p_val:.4f}. "
        f"{'Drift detected' if is_drifted else 'No drift'} at alpha={alpha}."
    )

    return DriftResult(
        test_name="ks_2samp",
        statistic=float(stat),
        p_value=float(p_val),
        is_drifted=is_drifted,
        change_point=None,
        description=desc,
    )


# ---------------------------------------------------------------------------
# Multi-feature drift detection
# ---------------------------------------------------------------------------


def detect_feature_drift(
    current_window: dict[str, Sequence[float]],
    historical_window: dict[str, Sequence[float]],
    alpha: float = 0.05,
) -> DriftReport:
    """Test multiple features for distribution drift.

    For each feature key present in both windows:
    1. Run KS test between current and historical distributions
    2. Classify: p < 0.01 = critical, p < 0.05 = warning, else OK

    Args:
        current_window: {feature_name: [current values]}.
        historical_window: {feature_name: [historical values]}.
        alpha: Significance level for drift detection.

    Returns:
        DriftReport aggregating all results.
    """
    results: list[DriftResult] = []
    critical = 0
    warning = 0

    common_keys = sorted(
        set(current_window.keys()) & set(historical_window.keys())
    )

    for key in common_keys:
        result = ks_distribution_drift(
            historical_window[key],
            current_window[key],
            alpha=alpha,
        )
        # Re-wrap with feature name in description
        result = DriftResult(
            test_name=f"ks_2samp:{key}",
            statistic=result.statistic,
            p_value=result.p_value,
            is_drifted=result.is_drifted,
            change_point=result.change_point,
            description=f"Feature '{key}': {result.description}",
        )
        results.append(result)

        if result.p_value < 0.01:
            critical += 1
        elif result.p_value < 0.05:
            warning += 1

    any_drift = any(r.is_drifted for r in results)

    return DriftReport(
        results=results,
        any_drift=any_drift,
        critical_drifts=critical,
        warning_drifts=warning,
    )


# ---------------------------------------------------------------------------
# Signal accuracy drift (two-proportion z-test)
# ---------------------------------------------------------------------------


def detect_signal_accuracy_drift(
    recent_outcomes: Sequence[bool],
    historical_outcomes: Sequence[bool],
    alpha: float = 0.05,
) -> DriftResult:
    """Test if signal accuracy has drifted between two outcome windows.

    Computes win rates for both windows, then uses a two-proportion z-test.
    z = (p1 - p2) / sqrt(p_hat * (1-p_hat) * (1/n1 + 1/n2))
    where p_hat = (wins1 + wins2) / (n1 + n2)

    Uses scipy.stats.norm.sf for the two-sided p-value.

    Args:
        recent_outcomes: Recent trade outcomes (True=win, False=loss).
        historical_outcomes: Historical trade outcomes.
        alpha: Significance level.

    Returns:
        DriftResult indicating whether accuracy has shifted.
    """
    n1 = len(recent_outcomes)
    n2 = len(historical_outcomes)

    if n1 < 2 or n2 < 2:
        return DriftResult(
            test_name="accuracy_z_test",
            statistic=0.0,
            p_value=1.0,
            is_drifted=False,
            change_point=None,
            description="Insufficient data (need >= 2 outcomes per window).",
        )

    wins1 = sum(1 for o in recent_outcomes if o)
    wins2 = sum(1 for o in historical_outcomes if o)

    p1 = wins1 / n1
    p2 = wins2 / n2
    p_hat = (wins1 + wins2) / (n1 + n2)

    # Avoid division by zero when p_hat is 0 or 1
    if p_hat == 0.0 or p_hat == 1.0:
        return DriftResult(
            test_name="accuracy_z_test",
            statistic=0.0,
            p_value=1.0,
            is_drifted=False,
            change_point=None,
            description=(
                f"Identical win rates (p1={p1:.4f}, p2={p2:.4f}). "
                "No variance to test."
            ),
        )

    se = math.sqrt(p_hat * (1.0 - p_hat) * (1.0 / n1 + 1.0 / n2))
    if se == 0.0:
        return DriftResult(
            test_name="accuracy_z_test",
            statistic=0.0,
            p_value=1.0,
            is_drifted=False,
            change_point=None,
            description="Zero standard error -- cannot compute z-test.",
        )

    z = abs(p1 - p2) / se
    # Two-sided p-value
    p_value = float(2.0 * scipy_stats.norm.sf(z))
    is_drifted = p_value < alpha

    desc = (
        f"Win rates: recent={p1:.4f}, historical={p2:.4f}. "
        f"z={z:.4f}, p={p_value:.4f}. "
        f"{'Accuracy drift detected' if is_drifted else 'No drift'} "
        f"at alpha={alpha}."
    )

    return DriftResult(
        test_name="accuracy_z_test",
        statistic=z,
        p_value=p_value,
        is_drifted=is_drifted,
        change_point=None,
        description=desc,
    )
