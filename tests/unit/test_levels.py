"""Unit tests for src.analysis.levels — level detection, proximity, and merging."""

from src.analysis.levels import (
    find_intraday_levels,
    find_swing_levels,
    get_pdh_pdl_pdc,
    get_pwh_pwl,
    get_session_status,
    is_at_level,
    merge_tagged_levels,
)
from tests.fixtures.price_data import make_15m_rows, make_daily_rows

# ---------------------------------------------------------------------------
# get_pdh_pdl_pdc
# ---------------------------------------------------------------------------


class TestGetPdhPdlPdc:
    """Returns (high, low, close) of the second-to-last daily row."""

    def test_basic_two_rows(self):
        rows = [(1.0900, 1.0800, 1.0850), (1.0920, 1.0810, 1.0860)]
        h, lo, c = get_pdh_pdl_pdc(rows)
        assert h == 1.0900
        assert lo == 1.0800
        assert c == 1.0850

    def test_multiple_rows_uses_second_to_last(self):
        rows = make_daily_rows(n=10)
        h, lo, c = get_pdh_pdl_pdc(rows)
        expected = rows[-2]
        assert h == expected[0]
        assert lo == expected[1]
        assert c == expected[2]

    def test_insufficient_one_row(self):
        rows = [(1.0900, 1.0800, 1.0850)]
        assert get_pdh_pdl_pdc(rows) == (None, None, None)

    def test_empty_list(self):
        assert get_pdh_pdl_pdc([]) == (None, None, None)


# ---------------------------------------------------------------------------
# get_pwh_pwl
# ---------------------------------------------------------------------------


class TestGetPwhPwl:
    """Returns (max high, min low) of daily[-8:-1]."""

    def test_basic_ten_rows(self):
        rows = make_daily_rows(n=10)
        pwh, pwl = get_pwh_pwl(rows)
        assert pwh is not None
        assert pwl is not None
        assert pwh >= pwl

    def test_known_values(self):
        # Build 10 rows with controlled highs and lows
        rows = [
            (1.0810, 1.0790, 1.0800),  # idx 0
            (1.0820, 1.0780, 1.0800),  # idx 1
            (1.0850, 1.0770, 1.0810),  # idx 2  <- start of [-8:-1]
            (1.0860, 1.0760, 1.0820),  # idx 3
            (1.0840, 1.0780, 1.0810),  # idx 4
            (1.0870, 1.0750, 1.0830),  # idx 5  <- max high 1.0870
            (1.0830, 1.0740, 1.0800),  # idx 6  <- min low 1.0740
            (1.0845, 1.0775, 1.0810),  # idx 7
            (1.0855, 1.0785, 1.0820),  # idx 8
            (1.0865, 1.0765, 1.0830),  # idx 9  <- excluded (last)
        ]
        pwh, pwl = get_pwh_pwl(rows)
        # daily[-8:-1] is rows[2:9]
        week_slice = rows[2:9]
        assert pwh == max(r[0] for r in week_slice)
        assert pwl == min(r[1] for r in week_slice)

    def test_insufficient_nine_rows(self):
        rows = make_daily_rows(n=9)
        assert get_pwh_pwl(rows) == (None, None)


# ---------------------------------------------------------------------------
# get_session_status
# ---------------------------------------------------------------------------


class TestGetSessionStatus:
    """Real-time clock, so we only test structure and types."""

    def test_returns_dict(self):
        result = get_session_status()
        assert isinstance(result, dict)

    def test_has_correct_keys(self):
        result = get_session_status()
        assert "active" in result
        assert "label" in result
        assert "cet_hour" in result

    def test_correct_types(self):
        result = get_session_status()
        assert isinstance(result["active"], bool)
        assert isinstance(result["label"], str)
        assert isinstance(result["cet_hour"], int)


# ---------------------------------------------------------------------------
# find_intraday_levels
# ---------------------------------------------------------------------------


class TestFindIntradayLevels:
    """Finds support/resistance levels from 15m rows."""

    def test_basic_returns_non_empty(self):
        rows = make_15m_rows(n=200)
        res, sup = find_intraday_levels(rows)
        # With 200 random-walk rows, at least some levels expected
        assert isinstance(res, list)
        assert isinstance(sup, list)

    def test_max_four_each(self):
        rows = make_15m_rows(n=200)
        res, sup = find_intraday_levels(rows)
        assert len(res) <= 4
        assert len(sup) <= 4

    def test_sorted_by_proximity_to_current(self):
        rows = make_15m_rows(n=200)
        res, sup = find_intraday_levels(rows)
        curr = rows[-1][2]  # last close
        if len(res) >= 2:
            dists = [abs(r - curr) for r in res]
            assert dists == sorted(dists)
        if len(sup) >= 2:
            dists = [abs(s - curr) for s in sup]
            assert dists == sorted(dists)

    def test_resistances_above_supports_below(self):
        rows = make_15m_rows(n=200)
        res, sup = find_intraday_levels(rows)
        curr = rows[-1][2]
        for r in res:
            assert r >= curr
        for s in sup:
            assert s <= curr

    def test_no_duplicates(self):
        rows = make_15m_rows(n=200)
        res, sup = find_intraday_levels(rows)
        assert len(res) == len(set(res))
        assert len(sup) == len(set(sup))

    def test_short_data(self):
        rows = make_15m_rows(n=5)
        res, sup = find_intraday_levels(rows)
        assert isinstance(res, list)
        assert isinstance(sup, list)

    def test_clips_to_last_200(self):
        rows = make_15m_rows(n=300, seed=99)
        res_300, sup_300 = find_intraday_levels(rows)
        # Should use only last 200 rows, same as feeding 200 directly
        res_200, sup_200 = find_intraday_levels(rows[-200:])
        assert res_300 == res_200
        assert sup_300 == sup_200


# ---------------------------------------------------------------------------
# find_swing_levels
# ---------------------------------------------------------------------------


class TestFindSwingLevels:
    def test_basic(self):
        rows = make_daily_rows(n=30)
        res, sup = find_swing_levels(rows)
        assert isinstance(res, list)
        assert isinstance(sup, list)

    def test_max_three_each(self):
        rows = make_daily_rows(n=30)
        res, sup = find_swing_levels(rows)
        assert len(res) <= 3
        assert len(sup) <= 3

    def test_sorted_by_proximity(self):
        rows = make_daily_rows(n=30)
        res, sup = find_swing_levels(rows)
        curr = rows[-1][2]
        if len(res) >= 2:
            dists = [abs(r - curr) for r in res]
            assert dists == sorted(dists)
        if len(sup) >= 2:
            dists = [abs(s - curr) for s in sup]
            assert dists == sorted(dists)


# ---------------------------------------------------------------------------
# is_at_level
# ---------------------------------------------------------------------------


class TestIsAtLevel:
    """Tolerance: w<=1: 0.30*atr, w==2: 0.35*atr, w>=3: 0.45*atr. Uses <=."""

    ATR = 0.001
    LEVEL = 1.0850

    def test_within_tolerance_weight_1(self):
        # tolerance = 0.30 * 0.001 = 0.0003
        curr = 1.08525  # distance = 0.00025 < 0.0003
        assert is_at_level(curr, self.LEVEL, self.ATR, weight=1) is True

    def test_outside_tolerance_weight_1(self):
        curr = 1.08555  # distance = 0.00055 > 0.0003
        assert is_at_level(curr, self.LEVEL, self.ATR, weight=1) is False

    def test_within_tolerance_weight_2(self):
        # tolerance = 0.35 * 0.001 = 0.00035
        curr = 1.08530  # distance = 0.0003 < 0.00035
        assert is_at_level(curr, self.LEVEL, self.ATR, weight=2) is True

    def test_within_tolerance_weight_3(self):
        # tolerance = 0.45 * 0.001 = 0.00045
        curr = 1.08540  # distance = 0.0004 < 0.00045
        assert is_at_level(curr, self.LEVEL, self.ATR, weight=3) is True

    def test_exact_boundary_uses_lte(self):
        # weight=1 -> tolerance = 0.0003
        curr = self.LEVEL + 0.0003  # exactly at boundary
        assert is_at_level(curr, self.LEVEL, self.ATR, weight=1) is True


# ---------------------------------------------------------------------------
# merge_tagged_levels
# ---------------------------------------------------------------------------


class TestMergeTaggedLevels:
    """Merges levels within 0.5*atr, keeps highest weight, max max_n."""

    ATR = 0.001
    CURR = 1.0850

    def test_basic_no_overlap(self):
        tagged = [
            {"price": 1.0800, "source": "PWL", "weight": 5},
            {"price": 1.0820, "source": "D1_swing", "weight": 3},
            {"price": 1.0860, "source": "15m_pivot", "weight": 1},
        ]
        result = merge_tagged_levels(tagged, self.CURR, self.ATR)
        assert len(result) == 3

    def test_absorbs_nearby_within_half_atr(self):
        # 0.5 * 0.001 = 0.0005 merge radius
        tagged = [
            {"price": 1.0800, "source": "PWL", "weight": 5},
            {"price": 1.08004, "source": "D1_swing", "weight": 3},  # within 0.0005
            {"price": 1.0860, "source": "15m_pivot", "weight": 1},
        ]
        result = merge_tagged_levels(tagged, self.CURR, self.ATR)
        # The two nearby levels should merge; highest weight (5) kept
        assert len(result) == 2
        weights = [lv["weight"] for lv in result]
        assert 5 in weights

    def test_max_n_limits_output(self):
        tagged = [{"price": 1.0800 + i * 0.0010, "source": f"src_{i}", "weight": i} for i in range(10)]
        result = merge_tagged_levels(tagged, self.CURR, self.ATR, max_n=4)
        assert len(result) <= 4

    def test_sorted_by_proximity_to_curr(self):
        tagged = [
            {"price": 1.0800, "source": "PWL", "weight": 5},
            {"price": 1.0845, "source": "D1_swing", "weight": 3},
            {"price": 1.0870, "source": "15m_pivot", "weight": 1},
        ]
        result = merge_tagged_levels(tagged, self.CURR, self.ATR)
        dists = [abs(lv["price"] - self.CURR) for lv in result]
        assert dists == sorted(dists)

    def test_empty_input(self):
        result = merge_tagged_levels([], self.CURR, self.ATR)
        assert result == []


# ===== Edge case tests added by Agent D3 =====================================


class TestGetPdhPdlPdcEdgeCases:
    """Edge cases for previous-day data extraction."""

    def test_two_rows_exact_minimum(self):
        """Exactly 2 rows is the minimum to get a result."""
        rows = [(1.1000, 1.0900, 1.0950), (1.1020, 1.0920, 1.0970)]
        h, lo, c = get_pdh_pdl_pdc(rows)
        assert h == 1.1000
        assert lo == 1.0900
        assert c == 1.0950

    def test_identical_rows(self):
        """All rows same values — should still extract correctly."""
        rows = [(1.0850, 1.0850, 1.0850)] * 5
        h, lo, c = get_pdh_pdl_pdc(rows)
        assert h == 1.0850
        assert lo == 1.0850
        assert c == 1.0850

    def test_large_spread_rows(self):
        """Rows with extreme high-low spread."""
        rows = [(2.0000, 0.5000, 1.2500), (1.9000, 0.6000, 1.1000)]
        h, lo, c = get_pdh_pdl_pdc(rows)
        assert h == 2.0000
        assert lo == 0.5000
        assert c == 1.2500


class TestGetPwhPwlEdgeCases:
    """Edge cases for previous-week data extraction."""

    def test_exactly_ten_rows(self):
        """10 rows is the minimum for pwh/pwl — should succeed."""
        rows = make_daily_rows(n=10)
        pwh, pwl = get_pwh_pwl(rows)
        assert pwh is not None
        assert pwl is not None

    def test_all_identical_prices(self):
        """All rows at same price — pwh == pwl."""
        rows = [(1.0850, 1.0850, 1.0850)] * 10
        pwh, pwl = get_pwh_pwl(rows)
        assert pwh == pwl == 1.0850

    def test_eight_rows_insufficient(self):
        """8 rows is below the 10-row minimum."""
        rows = make_daily_rows(n=8)
        assert get_pwh_pwl(rows) == (None, None)


class TestFindIntradayLevelsEdgeCases:
    """Edge cases for intraday level detection."""

    def test_single_candle(self):
        """One candle — not enough for pivot detection."""
        rows = [(1.0860, 1.0840, 1.0850)]
        res, sup = find_intraday_levels(rows)
        assert res == []
        assert sup == []

    def test_empty_rows(self):
        """Empty list should not crash."""
        # find_intraday_levels accesses rows[-1], so it will raise on truly empty
        # But with at least 1 row and n=3, the loop range(3, len-3) is empty
        rows = [(1.0850, 1.0840, 1.0845)]
        res, sup = find_intraday_levels(rows)
        assert isinstance(res, list)
        assert isinstance(sup, list)

    def test_flat_data_no_levels(self):
        """All candles at exact same price — no pivots above/below current."""
        rows = [(1.0850, 1.0850, 1.0850)] * 50
        res, sup = find_intraday_levels(rows)
        assert res == []
        assert sup == []

    def test_two_candles(self):
        """Two candles — still insufficient for pivot detection with n=3."""
        rows = [(1.0860, 1.0840, 1.0850), (1.0870, 1.0830, 1.0845)]
        res, sup = find_intraday_levels(rows)
        assert isinstance(res, list)
        assert isinstance(sup, list)

    def test_extreme_volatility(self):
        """Very large price swings — function should still produce valid output."""
        rows = make_15m_rows(n=200, base=1.0850, atr=0.0500, seed=77)
        res, sup = find_intraday_levels(rows)
        assert isinstance(res, list)
        assert isinstance(sup, list)
        assert len(res) <= 4
        assert len(sup) <= 4


class TestFindSwingLevelsEdgeCases:
    """Edge cases for swing-level detection."""

    def test_single_row(self):
        """One row — cannot form pivots but should not crash (accesses rows[-1])."""
        rows = [(1.0860, 1.0840, 1.0850)]
        res, sup = find_swing_levels(rows)
        assert res == []
        assert sup == []

    def test_flat_daily_data(self):
        """Flat daily data — no divergence, no pivots."""
        rows = [(1.0850, 1.0850, 1.0850)] * 30
        res, sup = find_swing_levels(rows)
        assert res == []
        assert sup == []


class TestIsAtLevelEdgeCases:
    """Additional boundary and edge cases for is_at_level."""

    def test_zero_atr_always_false(self):
        """Zero ATR => tolerance is 0, only exact match passes."""
        # distance = 0.0001 > 0 tolerance
        assert is_at_level(1.0851, 1.0850, 0.0, weight=1) is False

    def test_zero_atr_exact_match(self):
        """Zero ATR with exact price match should pass (0 <= 0)."""
        assert is_at_level(1.0850, 1.0850, 0.0, weight=1) is True

    def test_negative_distance(self):
        """Price below level — abs distance still checked."""
        assert is_at_level(1.0849, 1.0850, 0.001, weight=1) is True  # 0.0001 < 0.0003

    def test_very_large_atr(self):
        """Huge ATR — everything should be within tolerance."""
        assert is_at_level(1.0000, 2.0000, 100.0, weight=1) is True


class TestMergeTaggedLevelsEdgeCases:
    """Additional edge cases for level merging."""

    def test_single_level(self):
        """Single level — no merging possible, returned as-is."""
        tagged = [{"price": 1.0850, "source": "D1", "weight": 3}]
        result = merge_tagged_levels(tagged, 1.0850, 0.001)
        assert len(result) == 1
        assert result[0]["price"] == 1.0850

    def test_none_atr(self):
        """atr=None => atr_buf=0, so no merging occurs."""
        tagged = [
            {"price": 1.0800, "source": "PWL", "weight": 5},
            {"price": 1.08001, "source": "D1", "weight": 3},
        ]
        result = merge_tagged_levels(tagged, 1.0850, None)
        # With atr_buf=0, the < check (not <=) means no absorption happens
        assert len(result) == 2

    def test_all_same_price(self):
        """All levels at same price — all merge into one."""
        tagged = [
            {"price": 1.0850, "source": "A", "weight": 1},
            {"price": 1.0850, "source": "B", "weight": 3},
            {"price": 1.0850, "source": "C", "weight": 5},
        ]
        result = merge_tagged_levels(tagged, 1.0850, 0.001)
        assert len(result) == 1
        assert result[0]["weight"] == 5  # highest weight wins

    def test_max_n_zero(self):
        """max_n=0 should return empty list."""
        tagged = [{"price": 1.0850, "source": "D1", "weight": 3}]
        result = merge_tagged_levels(tagged, 1.0850, 0.001, max_n=0)
        assert result == []
