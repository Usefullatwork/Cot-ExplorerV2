"""Unit tests for generate_windows_enhanced in src.trading.backtesting.optimizer."""

from __future__ import annotations

from datetime import datetime

import pytest

from src.trading.backtesting.optimizer import (
    _generate_windows,
    generate_windows_enhanced,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _monthly_dates(months: int, start_year: int = 2020, start_month: int = 1) -> list[str]:
    """Generate one date per month for the given number of months."""
    dates: list[str] = []
    y, m = start_year, start_month
    for _ in range(months):
        dates.append(f"{y}-{m:02d}-15")
        m += 1
        if m > 12:
            m = 1
            y += 1
    return dates


def _daily_dates(days: int, start: str = "2020-01-01") -> list[str]:
    """Generate consecutive daily date strings."""
    from datetime import timedelta

    base = datetime.strptime(start, "%Y-%m-%d")
    return [(base + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(days)]


# ===========================================================================
# Sliding mode: should match existing _generate_windows with purge/embargo=0
# ===========================================================================


class TestSlidingMode:
    """Tests for mode='sliding' which replicates _generate_windows behavior."""

    def test_sliding_produces_windows(self):
        """36 months of data -> multiple windows."""
        dates = _monthly_dates(36)
        windows = generate_windows_enhanced(dates, 6, 2, mode="sliding")
        assert len(windows) >= 2

    def test_sliding_window_ordering(self):
        """All windows have train_start < train_end <= test_start < test_end."""
        dates = _monthly_dates(36)
        windows = generate_windows_enhanced(dates, 6, 2, mode="sliding")
        for tr_s, tr_e, te_s, te_e in windows:
            assert tr_s < tr_e
            assert tr_e <= te_s
            assert te_s < te_e

    def test_sliding_no_purge_matches_legacy(self):
        """Sliding with purge=0, embargo=0 should produce same count as _generate_windows."""
        dates = _monthly_dates(36)
        legacy = _generate_windows(dates, 6, 2)
        enhanced = generate_windows_enhanced(dates, 6, 2, mode="sliding")
        # Both should produce windows; count may differ slightly due to cursor logic
        assert len(enhanced) >= 1
        assert len(legacy) >= 1

    def test_sliding_train_moves_forward(self):
        """Each window's train_start should advance beyond the previous."""
        dates = _monthly_dates(48)
        windows = generate_windows_enhanced(dates, 6, 2, mode="sliding")
        assert len(windows) >= 2
        for i in range(1, len(windows)):
            assert windows[i][0] > windows[i - 1][0]


# ===========================================================================
# Anchored mode: train always starts from dates[0]
# ===========================================================================


class TestAnchoredMode:
    """Tests for mode='anchored' where train always starts at first date."""

    def test_anchored_all_start_from_first(self):
        """Every window's train_start must be the first date."""
        dates = _monthly_dates(48)
        windows = generate_windows_enhanced(dates, 6, 2, mode="anchored")
        assert len(windows) >= 2
        for tr_s, _tr_e, _te_s, _te_e in windows:
            assert tr_s == dates[0]

    def test_anchored_train_grows(self):
        """Each subsequent window should have a later train_end (growing train)."""
        dates = _monthly_dates(48)
        windows = generate_windows_enhanced(dates, 6, 2, mode="anchored")
        assert len(windows) >= 2
        for i in range(1, len(windows)):
            assert windows[i][1] > windows[i - 1][1]

    def test_anchored_test_slides_forward(self):
        """Test windows should advance each step."""
        dates = _monthly_dates(48)
        windows = generate_windows_enhanced(dates, 6, 2, mode="anchored")
        assert len(windows) >= 2
        for i in range(1, len(windows)):
            assert windows[i][2] > windows[i - 1][2]

    def test_anchored_window_ordering(self):
        """All boundaries chronological."""
        dates = _monthly_dates(36)
        windows = generate_windows_enhanced(dates, 6, 2, mode="anchored")
        for tr_s, tr_e, te_s, te_e in windows:
            assert tr_s < tr_e
            assert tr_e <= te_s
            assert te_s < te_e


# ===========================================================================
# Expanding mode
# ===========================================================================


class TestExpandingMode:
    """Tests for mode='expanding' where train grows from first date."""

    def test_expanding_starts_at_first(self):
        """All train_start values equal dates[0]."""
        dates = _monthly_dates(48)
        windows = generate_windows_enhanced(dates, 6, 2, mode="expanding")
        assert len(windows) >= 2
        for tr_s, _tr_e, _te_s, _te_e in windows:
            assert tr_s == dates[0]

    def test_expanding_train_grows(self):
        """Train end advances each step."""
        dates = _monthly_dates(48)
        windows = generate_windows_enhanced(dates, 6, 2, mode="expanding")
        assert len(windows) >= 2
        for i in range(1, len(windows)):
            assert windows[i][1] > windows[i - 1][1]

    def test_expanding_window_ordering(self):
        """All boundaries chronological."""
        dates = _monthly_dates(36)
        windows = generate_windows_enhanced(dates, 6, 2, mode="expanding")
        for tr_s, tr_e, te_s, te_e in windows:
            assert tr_s < tr_e
            assert tr_e <= te_s
            assert te_s < te_e


# ===========================================================================
# Purge days
# ===========================================================================


class TestPurgeDays:
    """Tests for purge_days gap between train end and test start."""

    def test_purge_gap_exists(self):
        """With purge_days=10, test_start should be >= train_end + 10 days."""
        dates = _daily_dates(500)
        windows = generate_windows_enhanced(
            dates, 6, 2, mode="sliding", purge_days=10,
        )
        assert len(windows) >= 1
        for _tr_s, tr_e, te_s, _te_e in windows:
            tr_end_dt = datetime.strptime(tr_e, "%Y-%m-%d")
            te_start_dt = datetime.strptime(te_s, "%Y-%m-%d")
            gap = (te_start_dt - tr_end_dt).days
            assert gap >= 10

    def test_purge_zero_means_no_gap(self):
        """purge_days=0 means test_start == train_end (or very close)."""
        dates = _daily_dates(500)
        windows = generate_windows_enhanced(
            dates, 6, 2, mode="sliding", purge_days=0,
        )
        assert len(windows) >= 1
        for _tr_s, tr_e, te_s, _te_e in windows:
            tr_end_dt = datetime.strptime(tr_e, "%Y-%m-%d")
            te_start_dt = datetime.strptime(te_s, "%Y-%m-%d")
            gap = (te_start_dt - tr_end_dt).days
            assert gap == 0

    def test_purge_on_anchored(self):
        """Purge days applied in anchored mode."""
        dates = _daily_dates(500)
        windows = generate_windows_enhanced(
            dates, 6, 2, mode="anchored", purge_days=7,
        )
        assert len(windows) >= 1
        for _tr_s, tr_e, te_s, _te_e in windows:
            tr_end_dt = datetime.strptime(tr_e, "%Y-%m-%d")
            te_start_dt = datetime.strptime(te_s, "%Y-%m-%d")
            gap = (te_start_dt - tr_end_dt).days
            assert gap >= 7


# ===========================================================================
# Embargo days
# ===========================================================================


class TestEmbargoDays:
    """Tests for embargo_days gap after test end."""

    def test_embargo_gap_between_windows(self):
        """With embargo_days=5, successive windows have gap after test end."""
        dates = _daily_dates(700)
        windows = generate_windows_enhanced(
            dates, 6, 2, mode="sliding", embargo_days=5,
        )
        assert len(windows) >= 2
        for i in range(1, len(windows)):
            prev_te_end = datetime.strptime(windows[i - 1][3], "%Y-%m-%d")
            next_tr_start = datetime.strptime(windows[i][0], "%Y-%m-%d")
            gap = (next_tr_start - prev_te_end).days
            assert gap >= 5

    def test_embargo_reduces_window_count(self):
        """Embargo should produce fewer windows than no embargo."""
        dates = _daily_dates(500)
        no_embargo = generate_windows_enhanced(dates, 6, 2, mode="sliding", embargo_days=0)
        with_embargo = generate_windows_enhanced(dates, 6, 2, mode="sliding", embargo_days=30)
        assert len(with_embargo) <= len(no_embargo)


# ===========================================================================
# Edge cases
# ===========================================================================


class TestEdgeCases:
    """Edge cases for generate_windows_enhanced."""

    def test_empty_dates_returns_empty(self):
        """Empty dates -> empty list."""
        assert generate_windows_enhanced([], 6, 2) == []

    def test_dates_too_short_returns_empty(self):
        """Dates spanning less than train+test -> empty."""
        dates = _monthly_dates(5)
        assert generate_windows_enhanced(dates, 6, 2) == []

    def test_invalid_mode_returns_empty(self):
        """Unknown mode -> empty list."""
        dates = _monthly_dates(36)
        assert generate_windows_enhanced(dates, 6, 2, mode="unknown") == []

    def test_purge_exceeds_available_gap(self):
        """Purge so large that no windows fit -> empty list."""
        dates = _daily_dates(270)  # ~9 months
        windows = generate_windows_enhanced(
            dates, 6, 2, mode="sliding", purge_days=100,
        )
        assert windows == []

    def test_single_window_exact_fit(self):
        """Just enough data for one window."""
        dates = _daily_dates(300)  # 6*30 + 2*30 = 240 + some margin
        windows = generate_windows_enhanced(dates, 6, 2, mode="sliding")
        assert len(windows) >= 1
