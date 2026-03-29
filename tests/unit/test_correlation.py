"""Unit tests for src.analysis.correlation — Pearson correlation and matrix."""

from __future__ import annotations

import math

from src.analysis.correlation import (
    INSTRUMENTS,
    calculate_correlation_matrix,
    pearson,
)


# ===== pearson() ===========================================================


class TestPearson:
    """Pure Pearson correlation coefficient."""

    def test_perfect_positive_correlation(self):
        """Two identical series have correlation 1.0."""
        x = [1.0, 2.0, 3.0, 4.0, 5.0]
        y = [1.0, 2.0, 3.0, 4.0, 5.0]
        assert abs(pearson(x, y) - 1.0) < 1e-10

    def test_perfect_negative_correlation(self):
        """Perfectly inversely related series have correlation -1.0."""
        x = [1.0, 2.0, 3.0, 4.0, 5.0]
        y = [5.0, 4.0, 3.0, 2.0, 1.0]
        assert abs(pearson(x, y) - (-1.0)) < 1e-10

    def test_near_zero_correlation(self):
        """Orthogonal-like series have near-zero correlation."""
        x = [1.0, 0.0, -1.0, 0.0]
        y = [0.0, 1.0, 0.0, -1.0]
        corr = pearson(x, y)
        assert abs(corr) < 0.01

    def test_constant_x_returns_zero(self):
        """Zero variance in x returns 0.0."""
        x = [5.0, 5.0, 5.0, 5.0]
        y = [1.0, 2.0, 3.0, 4.0]
        assert pearson(x, y) == 0.0

    def test_constant_y_returns_zero(self):
        """Zero variance in y returns 0.0."""
        x = [1.0, 2.0, 3.0, 4.0]
        y = [5.0, 5.0, 5.0, 5.0]
        assert pearson(x, y) == 0.0

    def test_length_less_than_2_returns_zero(self):
        """Series with fewer than 2 points returns 0.0."""
        assert pearson([1.0], [2.0]) == 0.0
        assert pearson([], []) == 0.0

    def test_different_lengths_uses_minimum(self):
        """Mismatched lengths use min(len(x), len(y))."""
        x = [1.0, 2.0, 3.0, 4.0, 5.0]
        y = [1.0, 2.0, 3.0]
        corr = pearson(x, y)
        # Should compute on first 3 elements only: perfect positive
        assert abs(corr - 1.0) < 1e-10

    def test_scaled_series_perfect_correlation(self):
        """Linearly scaled series still have correlation 1.0."""
        x = [1.0, 2.0, 3.0, 4.0, 5.0]
        y = [10.0, 20.0, 30.0, 40.0, 50.0]
        assert abs(pearson(x, y) - 1.0) < 1e-10


# ===== calculate_correlation_matrix ========================================


class TestCalculateCorrelationMatrix:
    """Correlation matrix computation across instrument pairs."""

    def test_three_instrument_matrix(self):
        """3 instruments produce 3 pairs."""
        price_data = {
            "A": [float(i) for i in range(20)],
            "B": [float(i * 2) for i in range(20)],
            "C": [float(20 - i) for i in range(20)],
        }
        matrix = calculate_correlation_matrix(price_data, window=20)
        # 3 instruments => 3 pairs: (A,B), (A,C), (B,C)
        assert len(matrix) == 3

    def test_matrix_symmetry(self):
        """corr(A,B) should equal corr(B,A) — stored as alphabetical pair."""
        price_data = {
            "EURUSD": [float(i) for i in range(20)],
            "GBPUSD": [float(i * 1.5 + 0.3) for i in range(20)],
        }
        matrix = calculate_correlation_matrix(price_data, window=20)
        # Only one entry should exist: ("EURUSD", "GBPUSD")
        assert ("EURUSD", "GBPUSD") in matrix
        # Reverse pair should NOT exist (no duplicates)
        assert ("GBPUSD", "EURUSD") not in matrix

    def test_self_correlation_omitted(self):
        """Diagonal (self-correlation) entries are not stored."""
        price_data = {
            "A": [float(i) for i in range(20)],
            "B": [float(i) for i in range(20)],
        }
        matrix = calculate_correlation_matrix(price_data, window=20)
        assert ("A", "A") not in matrix
        assert ("B", "B") not in matrix

    def test_perfect_positive_pair(self):
        """Identical series produce correlation 1.0."""
        price_data = {
            "X": [float(i) for i in range(20)],
            "Y": [float(i) for i in range(20)],
        }
        matrix = calculate_correlation_matrix(price_data, window=20)
        assert abs(matrix[("X", "Y")] - 1.0) < 1e-5

    def test_perfect_negative_pair(self):
        """Inversely related series produce correlation -1.0."""
        price_data = {
            "A": [float(i) for i in range(20)],
            "B": [float(20 - i) for i in range(20)],
        }
        matrix = calculate_correlation_matrix(price_data, window=20)
        assert abs(matrix[("A", "B")] - (-1.0)) < 1e-5

    def test_insufficient_data_excluded(self):
        """Instruments with fewer data points than window are excluded."""
        price_data = {
            "A": [float(i) for i in range(20)],
            "B": [float(i) for i in range(5)],  # too short
        }
        matrix = calculate_correlation_matrix(price_data, window=20)
        assert len(matrix) == 0

    def test_window_uses_trailing_observations(self):
        """Matrix uses last N observations, not the entire series."""
        # First 20 values go up, last 20 go down
        a = [float(i) for i in range(40)]
        b = list(range(20)) + list(range(20, 0, -1))
        b = [float(x) for x in b]
        price_data = {"A": a, "B": b}
        matrix = calculate_correlation_matrix(price_data, window=20)
        # Last 20 of A: [20..39] (increasing)
        # Last 20 of B: [20,19,18,...,1] (decreasing)
        assert matrix[("A", "B")] < 0  # should be negatively correlated in last window

    def test_empty_price_data(self):
        """Empty price data returns empty matrix."""
        matrix = calculate_correlation_matrix({}, window=20)
        assert len(matrix) == 0

    def test_values_rounded_to_6_decimals(self):
        """All correlation values are rounded to 6 decimal places."""
        price_data = {
            "A": [float(i) for i in range(20)],
            "B": [float(i * 1.1 + 0.7) for i in range(20)],
        }
        matrix = calculate_correlation_matrix(price_data, window=20)
        for val in matrix.values():
            # Check that the value has at most 6 decimal places
            assert val == round(val, 6)
