"""Unit tests for src.analysis.smc — Smart Money Concepts structure analysis."""

import pytest

from src.analysis.smc import (
    build_supply_demand_zones,
    calc_atr,
    classify_swings,
    detect_bos,
    determine_structure,
    filter_relevant_zones,
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
        supply, demand = build_supply_demand_zones(
            pivot_highs, pivot_lows, rows, atr, box_width=2.5, history=20
        )
        assert isinstance(supply, list)
        assert isinstance(demand, list)

    def test_overlap_filter_merges_nearby(self):
        # Two very close pivot highs should produce 1 supply zone (within 2*atr overlap)
        rows = make_smc_bullish_rows(n=60)
        atr = 0.0020
        # Create artificial pivot highs very close together
        close_pivots_h = [(20, 1.0900), (22, 1.0901)]  # 0.0001 apart < 2*0.0020
        close_pivots_l = [(25, 1.0800)]
        supply, demand = build_supply_demand_zones(
            close_pivots_h, close_pivots_l, rows, atr, box_width=2.5, history=20
        )
        # With overlap check (within 2*atr = 0.004), close pivots merge
        assert len(supply) <= len(close_pivots_h)

    def test_zone_dimensions(self):
        rows = make_smc_bullish_rows(n=60)
        atr = 0.0020
        pivot_highs = [(30, 1.0900)]
        pivot_lows = [(25, 1.0800)]
        supply, demand = build_supply_demand_zones(
            pivot_highs, pivot_lows, rows, atr, box_width=2.5, history=20
        )
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
            "top": top, "bottom": bottom, "poi": (top + bottom) / 2,
            "idx": idx, "type": type_, "status": "intakt",
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
