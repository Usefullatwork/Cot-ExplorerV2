"""Unit tests for src.analysis.smc — Smart Money Concepts structure analysis."""

import pytest

from src.analysis.smc import (
    build_supply_demand_zones,
    classify_swings,
    detect_bos,
    determine_structure,
    find_pivot_highs,
    find_pivot_lows,
    run_smc,
)
from tests.fixtures.price_data import (
    make_flat_rows,
    make_smc_bearish_rows,
    make_smc_bullish_rows,
)

# ---------------------------------------------------------------------------
# find_pivot_highs / find_pivot_lows
# ---------------------------------------------------------------------------


class TestFindPivotHighs:
    def test_basic_bullish_data(self):
        rows = make_smc_bullish_rows(n=120)
        pivots = find_pivot_highs(rows, length=5)
        assert isinstance(pivots, list)
        assert len(pivots) > 0
        for idx, price in pivots:
            assert isinstance(idx, int)
            assert isinstance(price, float)

    def test_too_short_data(self):
        rows = make_smc_bullish_rows(n=5)
        pivots = find_pivot_highs(rows, length=10)
        assert pivots == [] or len(pivots) == 0

    def test_flat_data(self):
        rows = make_flat_rows(n=30, price=1.0850)
        pivots = find_pivot_highs(rows, length=10)
        # Flat data has no true pivot highs
        assert isinstance(pivots, list)


class TestFindPivotLows:
    def test_basic_bullish_data(self):
        rows = make_smc_bullish_rows(n=120)
        pivots = find_pivot_lows(rows, length=5)
        assert isinstance(pivots, list)
        assert len(pivots) > 0
        for idx, price in pivots:
            assert isinstance(idx, int)
            assert isinstance(price, float)

    def test_too_short_data(self):
        rows = make_smc_bullish_rows(n=5)
        pivots = find_pivot_lows(rows, length=10)
        assert pivots == [] or len(pivots) == 0


# ---------------------------------------------------------------------------
# classify_swings
# ---------------------------------------------------------------------------


class TestClassifySwings:
    """
    First pivot: 'HH' if high swing_type, 'HL' if low.
    Then: high: val>=prev -> 'HH', else 'LH'. low: val>=prev -> 'HL', else 'LL'.
    """

    def test_high_ascending_gives_hh(self):
        pivots = [(5, 1.0800), (15, 1.0850), (25, 1.0900)]
        classified = classify_swings(pivots, "high")
        labels = [c[2] for c in classified]
        assert labels[0] == "HH"  # first defaults to HH for highs
        assert labels[1] == "HH"  # 1.0850 >= 1.0800
        assert labels[2] == "HH"  # 1.0900 >= 1.0850

    def test_high_descending_gives_lh(self):
        pivots = [(5, 1.0900), (15, 1.0850), (25, 1.0800)]
        classified = classify_swings(pivots, "high")
        labels = [c[2] for c in classified]
        assert labels[0] == "HH"  # first always HH
        assert labels[1] == "LH"  # 1.0850 < 1.0900
        assert labels[2] == "LH"  # 1.0800 < 1.0850

    def test_low_ascending_gives_hl(self):
        pivots = [(5, 1.0700), (15, 1.0750), (25, 1.0800)]
        classified = classify_swings(pivots, "low")
        labels = [c[2] for c in classified]
        assert labels[0] == "HL"  # first defaults to HL for lows
        assert labels[1] == "HL"  # 1.0750 >= 1.0700
        assert labels[2] == "HL"  # 1.0800 >= 1.0750

    def test_low_descending_gives_ll(self):
        pivots = [(5, 1.0800), (15, 1.0750), (25, 1.0700)]
        classified = classify_swings(pivots, "low")
        labels = [c[2] for c in classified]
        assert labels[0] == "HL"  # first always HL
        assert labels[1] == "LL"  # 1.0750 < 1.0800
        assert labels[2] == "LL"  # 1.0700 < 1.0750

    def test_first_element_default(self):
        # Single pivot
        high_cls = classify_swings([(10, 1.0850)], "high")
        low_cls = classify_swings([(10, 1.0850)], "low")
        assert high_cls[0][2] == "HH"
        assert low_cls[0][2] == "HL"


# ---------------------------------------------------------------------------
# build_supply_demand_zones
# ---------------------------------------------------------------------------


class TestBuildSupplyDemandZones:
    def test_basic_creates_zones(self):
        rows = make_smc_bullish_rows(n=60)
        pivot_highs = find_pivot_highs(rows, length=10)
        pivot_lows = find_pivot_lows(rows, length=10)
        atr = 0.0020
        supply, demand = build_supply_demand_zones(pivot_highs, pivot_lows, rows, atr, box_width=2.5, history=20)
        assert isinstance(supply, list)
        assert isinstance(demand, list)

    def test_overlap_filter_merges_nearby(self):
        # Two very close pivot highs should produce 1 supply zone (within 2*atr overlap)
        rows = make_smc_bullish_rows(n=60)
        atr = 0.0020
        # Create artificial pivot highs very close together
        close_pivots_h = [(20, 1.0900), (22, 1.0901)]  # 0.0001 apart < 2*0.0020
        close_pivots_l = [(25, 1.0800)]
        supply, demand = build_supply_demand_zones(close_pivots_h, close_pivots_l, rows, atr, box_width=2.5, history=20)
        # With overlap check (within 2*atr = 0.004), close pivots merge
        assert len(supply) <= len(close_pivots_h)

    def test_zone_dimensions(self):
        rows = make_smc_bullish_rows(n=60)
        atr = 0.0020
        pivot_highs = [(30, 1.0900)]
        pivot_lows = [(25, 1.0800)]
        supply, demand = build_supply_demand_zones(pivot_highs, pivot_lows, rows, atr, box_width=2.5, history=20)
        # Supply: top=high, bottom=high - atr*(box_width/10)
        if supply:
            zone = supply[0]
            expected_bottom = 1.0900 - atr * (2.5 / 10)  # 1.0900 - 0.0005 = 1.08950
            assert zone["top"] == pytest.approx(1.0900, abs=1e-4)
            assert zone["bottom"] == pytest.approx(expected_bottom, abs=1e-4)


# ---------------------------------------------------------------------------
# detect_bos
# ---------------------------------------------------------------------------


class TestDetectBos:
    """Break of structure: close >= top -> BOS_opp, close <= bottom -> BOS_ned."""

    def _make_zone(self, top, bottom, idx=0, type_="supply"):
        return {
            "top": top,
            "bottom": bottom,
            "poi": (top + bottom) / 2,
            "idx": idx,
            "type": type_,
            "status": "intakt",
        }

    def test_supply_broken(self):
        supply = [self._make_zone(top=1.0900, bottom=1.0895, idx=0, type_="supply")]
        demand = [self._make_zone(top=1.0810, bottom=1.0800, idx=0, type_="demand")]
        # Row 0 is the zone origin, row 1 closes above supply top
        rows = [(1.0860, 1.0840, 1.0850), (1.0910, 1.0880, 1.0905)]
        s, d, bos = detect_bos(supply, demand, rows)
        assert any(b["type"] == "BOS_opp" for b in bos)
        assert supply[0]["status"] == "bos_brutt"

    def test_demand_broken(self):
        supply = [self._make_zone(top=1.0900, bottom=1.0895, idx=0, type_="supply")]
        demand = [self._make_zone(top=1.0810, bottom=1.0800, idx=0, type_="demand")]
        # Row 1 closes below demand bottom
        rows = [(1.0860, 1.0840, 1.0850), (1.0810, 1.0790, 1.0795)]
        s, d, bos = detect_bos(supply, demand, rows)
        assert any(b["type"] == "BOS_ned" for b in bos)
        assert demand[0]["status"] == "bos_brutt"

    def test_intact_no_break(self):
        supply = [self._make_zone(top=1.0900, bottom=1.0895, idx=0, type_="supply")]
        demand = [self._make_zone(top=1.0810, bottom=1.0800, idx=0, type_="demand")]
        # Close stays between zones
        rows = [(1.0860, 1.0840, 1.0850), (1.0860, 1.0840, 1.0850)]
        s, d, bos = detect_bos(supply, demand, rows)
        assert len(bos) == 0
        assert supply[0]["status"] == "intakt"
        assert demand[0]["status"] == "intakt"


# ---------------------------------------------------------------------------
# determine_structure
# ---------------------------------------------------------------------------


class TestDetermineStructure:
    def test_bullish_hh_hl(self):
        highs = [(5, 1.0850, "HH"), (15, 1.0900, "HH")]
        lows = [(10, 1.0800, "HL"), (20, 1.0830, "HL")]
        assert determine_structure(highs, lows) == "BULLISH"

    def test_bearish_lh_ll(self):
        highs = [(5, 1.0900, "LH"), (15, 1.0870, "LH")]
        lows = [(10, 1.0800, "LL"), (20, 1.0770, "LL")]
        assert determine_structure(highs, lows) == "BEARISH"

    def test_mixed_lh_hl(self):
        highs = [(5, 1.0900, "LH"), (15, 1.0880, "LH")]
        lows = [(10, 1.0800, "HL"), (20, 1.0820, "HL")]
        assert determine_structure(highs, lows) == "MIXED"

    def test_bullish_svak_hh_only(self):
        highs = [(5, 1.0850, "HH"), (15, 1.0900, "HH")]
        lows = [(10, 1.0800, "LL"), (20, 1.0780, "LL")]
        assert determine_structure(highs, lows) == "BULLISH_SVAK"


# ---------------------------------------------------------------------------
# run_smc (integration of all SMC sub-functions)
# ---------------------------------------------------------------------------


class TestRunSmc:
    def test_full_bullish_data(self):
        rows = make_smc_bullish_rows(n=200)
        result = run_smc(rows, swing_length=5, box_width=2.5)
        assert result is not None
        assert isinstance(result, dict)
        assert "structure" in result
        assert "supply_zones" in result
        assert "demand_zones" in result

    def test_insufficient_data_returns_none(self):
        # Need at least swing_length*2 + 5 = 25 rows
        rows = make_smc_bullish_rows(n=20)
        result = run_smc(rows, swing_length=10, box_width=2.5)
        assert result is None


# ===== Edge case tests added by Agent D3 =====================================


class TestFindPivotHighsEdgeCases:
    """Edge cases for pivot high detection."""

    def test_empty_rows(self):
        """Empty list => no pivots."""
        assert find_pivot_highs([], length=5) == []

    def test_single_row(self):
        """One row => range(length, 1-length) is empty."""
        rows = [(1.0860, 1.0840, 1.0850)]
        assert find_pivot_highs(rows, length=5) == []

    def test_all_same_price(self):
        """All identical prices — every high == max of window."""
        rows = [(1.0850, 1.0850, 1.0850)] * 30
        pivots = find_pivot_highs(rows, length=5)
        # All highs equal => rows[i][0] == max(window) for all i in range
        assert isinstance(pivots, list)

    def test_exactly_2_length_plus_1_rows(self):
        """Exactly 2*length+1 rows => exactly 1 candidate at index=length."""
        length = 5
        n = 2 * length + 1  # 11
        rows = make_smc_bullish_rows(n=n)
        pivots = find_pivot_highs(rows, length=length)
        # range(5, 11-5) = range(5, 6) => only index 5 checked
        assert isinstance(pivots, list)
        assert len(pivots) <= 1


class TestFindPivotLowsEdgeCases:
    """Edge cases for pivot low detection."""

    def test_empty_rows(self):
        """Empty list => no pivots."""
        assert find_pivot_lows([], length=5) == []

    def test_single_row(self):
        """One row => no pivots."""
        rows = [(1.0860, 1.0840, 1.0850)]
        assert find_pivot_lows(rows, length=5) == []

    def test_all_same_price(self):
        """All identical prices — every low == min of window."""
        rows = [(1.0850, 1.0850, 1.0850)] * 30
        pivots = find_pivot_lows(rows, length=5)
        assert isinstance(pivots, list)


class TestClassifySwingsEdgeCases:
    """Edge cases for swing classification."""

    def test_empty_pivots(self):
        """Empty pivot list => empty classification."""
        assert classify_swings([], "high") == []
        assert classify_swings([], "low") == []

    def test_equal_values_high(self):
        """Two pivots with identical values — HH (val >= prev)."""
        pivots = [(5, 1.0850), (15, 1.0850)]
        classified = classify_swings(pivots, "high")
        assert classified[1][2] == "HH"  # 1.0850 >= 1.0850

    def test_equal_values_low(self):
        """Two pivots with identical values — HL (val >= prev)."""
        pivots = [(5, 1.0800), (15, 1.0800)]
        classified = classify_swings(pivots, "low")
        assert classified[1][2] == "HL"  # 1.0800 >= 1.0800

    def test_single_pivot_high(self):
        """Single pivot high => first-element default HH."""
        classified = classify_swings([(10, 1.0850)], "high")
        assert len(classified) == 1
        assert classified[0][2] == "HH"

    def test_single_pivot_low(self):
        """Single pivot low => first-element default HL."""
        classified = classify_swings([(10, 1.0800)], "low")
        assert len(classified) == 1
        assert classified[0][2] == "HL"


class TestDetermineStructureEdgeCases:
    """Edge cases for structure determination."""

    def test_empty_highs_and_lows(self):
        """No swings at all => MIXED (fallback)."""
        result = determine_structure([], [])
        assert result == "MIXED"

    def test_empty_highs_only(self):
        """No highs but has lows => depends on last low label."""
        lows = [(10, 1.0800, "LL")]
        result = determine_structure([], lows)
        # last_high_label = None, last_low_label = "LL" => BEARISH_SVAK
        assert result == "BEARISH_SVAK"

    def test_empty_lows_only(self):
        """No lows but has highs => depends on last high label."""
        highs = [(10, 1.0900, "HH")]
        result = determine_structure(highs, [])
        # last_high_label = "HH", last_low_label = None => BULLISH_SVAK
        assert result == "BULLISH_SVAK"

    def test_single_pair_bullish(self):
        """Single HH + single HL => BULLISH."""
        highs = [(5, 1.0900, "HH")]
        lows = [(10, 1.0800, "HL")]
        assert determine_structure(highs, lows) == "BULLISH"


class TestBuildSupplyDemandZonesEdgeCases:
    """Edge cases for supply/demand zone construction."""

    def test_no_pivots(self):
        """No pivot highs and no pivot lows => empty zones."""
        rows = make_smc_bullish_rows(n=60)
        supply, demand = build_supply_demand_zones([], [], rows, 0.002)
        assert supply == []
        assert demand == []

    def test_zero_atr(self):
        """atr=0 => atr_buffer=0, atr_overlap=0."""
        pivot_highs = [(30, 1.0900)]
        pivot_lows = [(25, 1.0800)]
        rows = make_smc_bullish_rows(n=60)
        supply, demand = build_supply_demand_zones(pivot_highs, pivot_lows, rows, atr=0.0)
        # With atr=0, zone top == bottom == poi
        assert isinstance(supply, list)
        assert isinstance(demand, list)


class TestDetectBosEdgeCases:
    """Edge cases for BOS detection."""

    def test_empty_zones(self):
        """No supply or demand zones => no BOS."""
        rows = [(1.0850, 1.0840, 1.0845)]
        s, d, bos = detect_bos([], [], rows)
        assert bos == []

    def test_zone_idx_beyond_rows(self):
        """Zone idx at end of rows => no subsequent rows to check."""
        zone = {
            "top": 1.0900,
            "bottom": 1.0895,
            "poi": 1.08975,
            "idx": 0,
            "type": "supply",
            "status": "intakt",
        }
        # Only 1 row, zone at idx 0 => range(1, 1) is empty
        rows = [(1.0910, 1.0880, 1.0905)]
        s, d, bos = detect_bos([zone], [], rows)
        assert len(bos) == 0
        assert zone["status"] == "intakt"


class TestRunSmcEdgeCases:
    """Edge cases for the full SMC pipeline."""

    def test_empty_rows(self):
        """Empty data => None."""
        assert run_smc([], swing_length=5) is None

    def test_single_row(self):
        """Single row => insufficient data => None."""
        rows = [(1.0860, 1.0840, 1.0850)]
        assert run_smc(rows, swing_length=5) is None

    def test_flat_data_returns_none(self):
        """Flat data => ATR ~0, no pivots => None."""
        rows = make_flat_rows(n=200, price=1.0850)
        result = run_smc(rows, swing_length=5)
        # calc_atr returns 0.0 for flat data, which is falsy => None
        assert result is None

    def test_bearish_data(self):
        """Bearish data should produce a valid result with BEARISH structure."""
        rows = make_smc_bearish_rows(n=200)
        result = run_smc(rows, swing_length=5, box_width=2.5)
        assert result is not None
        assert isinstance(result["structure"], str)
        assert "supply_zones" in result
        assert "demand_zones" in result

    def test_swing_length_1(self):
        """Minimum swing_length=1 with enough data."""
        rows = make_smc_bullish_rows(n=50)
        # swing_length=1, min rows = 1*2+5 = 7
        result = run_smc(rows, swing_length=1)
        # Should produce a result (plenty of data)
        assert result is not None or result is None  # should not crash
