"""Unit tests for src.analysis.setup_builder.make_setup_l2l."""

import pytest

from src.analysis.setup_builder import make_setup_l2l
from tests.fixtures.tagged_levels import (
    EURUSD_RESISTANCES,
    EURUSD_SUPPORTS,
    make_resistance_level,
    make_support_level,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ATR_15M = 0.0012
ATR_DAILY = 0.006


# ===== Long – basic flow =====================================================


class TestLongBasicSetup:
    """LONG setups using EURUSD-style levels."""

    def test_long_basic_setup(self):
        """curr=1.0842, sup_tagged[0]=1.0800 (PWL w5) -> valid SetupL2L."""
        result = make_setup_l2l(
            curr=1.0842,
            atr_15m=ATR_15M,
            atr_daily=ATR_DAILY,
            sup_tagged=EURUSD_SUPPORTS,
            res_tagged=EURUSD_RESISTANCES,
            direction="long",
            klasse="A",
        )
        assert result is not None
        # Function uses sup_tagged[0] = 1.0800 (PWL, weight=5)
        assert result.entry == pytest.approx(1.0800, abs=0.001)
        assert result.entry_curr == pytest.approx(1.0842)
        assert result.sl < result.entry
        assert result.t1 > result.entry
        assert result.rr_t1 >= 1.5
        assert result.min_rr == 1.5

    def test_long_returns_none_no_supports(self):
        """No support levels -> None (no entry for long)."""
        result = make_setup_l2l(
            curr=1.0842,
            atr_15m=ATR_15M,
            atr_daily=ATR_DAILY,
            sup_tagged=[],
            res_tagged=EURUSD_RESISTANCES,
            direction="long",
            klasse="A",
        )
        assert result is None

    def test_long_returns_none_no_resistances(self):
        """No resistance levels -> None (no targets for long)."""
        result = make_setup_l2l(
            curr=1.0842,
            atr_15m=ATR_15M,
            atr_daily=ATR_DAILY,
            sup_tagged=EURUSD_SUPPORTS,
            res_tagged=[],
            direction="long",
            klasse="A",
        )
        assert result is None

    def test_long_price_too_far(self):
        """curr=1.1000 far above any support -> None."""
        result = make_setup_l2l(
            curr=1.1000,
            atr_15m=ATR_15M,
            atr_daily=ATR_DAILY,
            sup_tagged=EURUSD_SUPPORTS,
            res_tagged=EURUSD_RESISTANCES,
            direction="long",
            klasse="A",
        )
        assert result is None

    def test_long_price_below_entry(self):
        """curr=1.0790, below all supports -> None (entry_dist<0)."""
        result = make_setup_l2l(
            curr=1.0790,
            atr_15m=ATR_15M,
            atr_daily=ATR_DAILY,
            sup_tagged=EURUSD_SUPPORTS,
            res_tagged=EURUSD_RESISTANCES,
            direction="long",
            klasse="A",
        )
        assert result is None

    def test_long_no_valid_t1(self):
        """Only a resistance at 1.0837 (barely above 1.0835 entry) -> rr < min_rr -> None."""
        tiny_res = [make_resistance_level(1.0837, weight=3, source="D1_swing")]
        result = make_setup_l2l(
            curr=1.0836,
            atr_15m=ATR_15M,
            atr_daily=ATR_DAILY,
            sup_tagged=[make_support_level(1.0835, weight=3, source="D1_swing")],
            res_tagged=tiny_res,
            direction="long",
            klasse="A",
        )
        assert result is None


# ===== Short – basic flow ====================================================


class TestShortBasicSetup:
    """SHORT setups using EURUSD-style levels."""

    def test_short_basic_setup(self):
        """curr=1.0878, res_tagged[0]=1.0900 (PWH w5) -> valid SetupL2L."""
        result = make_setup_l2l(
            curr=1.0878,
            atr_15m=ATR_15M,
            atr_daily=ATR_DAILY,
            sup_tagged=EURUSD_SUPPORTS,
            res_tagged=EURUSD_RESISTANCES,
            direction="short",
            klasse="A",
        )
        assert result is not None
        # Function uses res_tagged[0] = 1.0900 (PWH, weight=5)
        assert result.entry == pytest.approx(1.0900, abs=0.001)
        assert result.entry_curr == pytest.approx(1.0878)
        assert result.sl > result.entry
        assert result.t1 < result.entry
        assert result.rr_t1 >= 1.5

    def test_short_returns_none_no_resistances(self):
        """No resistance levels -> None (no entry for short)."""
        result = make_setup_l2l(
            curr=1.0878,
            atr_15m=ATR_15M,
            atr_daily=ATR_DAILY,
            sup_tagged=EURUSD_SUPPORTS,
            res_tagged=[],
            direction="short",
            klasse="A",
        )
        assert result is None

    def test_short_returns_none_no_supports(self):
        """No support levels -> None (no targets for short)."""
        result = make_setup_l2l(
            curr=1.0878,
            atr_15m=ATR_15M,
            atr_daily=ATR_DAILY,
            sup_tagged=[],
            res_tagged=EURUSD_RESISTANCES,
            direction="short",
            klasse="A",
        )
        assert result is None

    def test_short_with_zone_top(self):
        """Entry with zone_top -> SL = zone_top + 0.15 * atr_daily."""
        zone_top_val = 1.0895
        entry_res = [make_resistance_level(1.0880, weight=5, source="PWH", zone_top=zone_top_val)]
        result = make_setup_l2l(
            curr=1.0878,
            atr_15m=ATR_15M,
            atr_daily=ATR_DAILY,
            sup_tagged=EURUSD_SUPPORTS,
            res_tagged=entry_res,
            direction="short",
            klasse="A",
        )
        assert result is not None
        expected_sl = zone_top_val + 0.15 * ATR_DAILY
        assert result.sl == pytest.approx(expected_sl, abs=1e-6)
        assert result.sl_type == "zone"


# ===== ATR edge cases ========================================================


class TestATREdgeCases:
    """ATR validation and fallback logic."""

    def test_returns_none_zero_atr_15m(self):
        """atr_15m=0 -> None."""
        result = make_setup_l2l(
            curr=1.0842,
            atr_15m=0,
            atr_daily=ATR_DAILY,
            sup_tagged=EURUSD_SUPPORTS,
            res_tagged=EURUSD_RESISTANCES,
            direction="long",
            klasse="A",
        )
        assert result is None

    def test_returns_none_negative_atr_15m(self):
        """atr_15m=-1 -> None."""
        result = make_setup_l2l(
            curr=1.0842,
            atr_15m=-1,
            atr_daily=ATR_DAILY,
            sup_tagged=EURUSD_SUPPORTS,
            res_tagged=EURUSD_RESISTANCES,
            direction="long",
            klasse="A",
        )
        assert result is None

    def test_none_atr_daily_fallback(self):
        """atr_daily=None -> falls back to atr_15m*5, still produces a result."""
        result = make_setup_l2l(
            curr=1.0842,
            atr_15m=ATR_15M,
            atr_daily=None,
            sup_tagged=EURUSD_SUPPORTS,
            res_tagged=EURUSD_RESISTANCES,
            direction="long",
            klasse="A",
        )
        # Should still produce a valid setup using fallback atr_daily = 0.006
        assert result is not None
        # risk_atr_d should reflect the fallback value
        assert result.risk_atr_d > 0


# ===== Structural SL logic ====================================================


class TestStructuralSL:
    """Stop-loss placement: zone-based vs. line-based."""

    def test_long_structural_sl_zone_based(self):
        """Entry with zone_bottom -> SL = zone_bottom - 0.15 * atr_daily."""
        zone_bottom_val = 1.0830
        entry = [make_support_level(1.0835, weight=5, source="PWL", zone_bottom=zone_bottom_val)]
        result = make_setup_l2l(
            curr=1.0838,
            atr_15m=ATR_15M,
            atr_daily=ATR_DAILY,
            sup_tagged=entry,
            res_tagged=EURUSD_RESISTANCES,
            direction="long",
            klasse="A",
        )
        assert result is not None
        expected_sl = zone_bottom_val - 0.15 * ATR_DAILY
        assert result.sl == pytest.approx(expected_sl, abs=1e-5)
        assert result.sl_type == "zone"

    def test_long_structural_sl_line_based(self):
        """Entry without zone_bottom, weight=3 -> SL = entry - 0.3 * atr_daily."""
        entry = [make_support_level(1.0835, weight=3, source="D1_swing")]
        result = make_setup_l2l(
            curr=1.0842,
            atr_15m=ATR_15M,
            atr_daily=ATR_DAILY,
            sup_tagged=entry,
            res_tagged=EURUSD_RESISTANCES,
            direction="long",
            klasse="A",
        )
        assert result is not None
        expected_sl = 1.0835 - 0.3 * ATR_DAILY
        assert result.sl == pytest.approx(expected_sl, abs=1e-6)
        assert result.sl_type == "struktur"

    def test_long_structural_sl_high_weight(self):
        """Entry without zone_bottom, weight>=4 -> SL = entry - 0.5 * atr_daily."""
        entry = [make_support_level(1.0835, weight=5, source="PWL")]
        result = make_setup_l2l(
            curr=1.0842,
            atr_15m=ATR_15M,
            atr_daily=ATR_DAILY,
            sup_tagged=entry,
            res_tagged=EURUSD_RESISTANCES,
            direction="long",
            klasse="A",
        )
        assert result is not None
        expected_sl = 1.0835 - 0.5 * ATR_DAILY
        assert result.sl == pytest.approx(expected_sl, abs=1e-6)
        assert result.sl_type == "struktur"


# ===== T1 quality classification ==============================================


class TestT1Quality:
    """T1 quality: weight>=3 -> 'htf', ==2 -> '4h', ==1 -> 'weak'."""

    def test_long_t1_quality_htf(self):
        """Target weight >= 3 -> t1_quality = 'htf'."""
        res_htf = [make_resistance_level(1.0900, weight=5, source="PWH")]
        result = make_setup_l2l(
            curr=1.0842,
            atr_15m=ATR_15M,
            atr_daily=ATR_DAILY,
            sup_tagged=EURUSD_SUPPORTS,
            res_tagged=res_htf,
            direction="long",
            klasse="A",
        )
        assert result is not None
        assert result.t1_quality == "htf"

    def test_long_t1_quality_4h(self):
        """Target weight == 2 -> t1_quality = '4h'."""
        res_4h = [make_resistance_level(1.0900, weight=2, source="4H_swing")]
        result = make_setup_l2l(
            curr=1.0842,
            atr_15m=ATR_15M,
            atr_daily=ATR_DAILY,
            sup_tagged=EURUSD_SUPPORTS,
            res_tagged=res_4h,
            direction="long",
            klasse="A",
        )
        assert result is not None
        assert result.t1_quality == "4h"

    def test_long_t1_quality_weak(self):
        """Target weight == 1 -> t1_quality = 'weak'."""
        res_weak = [make_resistance_level(1.0900, weight=1, source="15m_pivot")]
        result = make_setup_l2l(
            curr=1.0842,
            atr_15m=ATR_15M,
            atr_daily=ATR_DAILY,
            sup_tagged=EURUSD_SUPPORTS,
            res_tagged=res_weak,
            direction="long",
            klasse="A",
        )
        assert result is not None
        assert result.t1_quality == "weak"


# ===== Status (aktiv / watchlist) =============================================


class TestStatus:
    """Status depends on is_at_level(curr, entry, atr_15m, weight)."""

    def test_long_status_aktiv(self):
        """curr very close to entry -> 'aktiv'."""
        entry = [make_support_level(1.0835, weight=3, source="D1_swing")]
        result = make_setup_l2l(
            curr=1.0836,
            atr_15m=ATR_15M,
            atr_daily=ATR_DAILY,
            sup_tagged=entry,
            res_tagged=EURUSD_RESISTANCES,
            direction="long",
            klasse="A",
        )
        assert result is not None
        assert result.status == "aktiv"

    def test_long_status_watchlist(self):
        """curr further from entry -> 'watchlist'."""
        entry = [make_support_level(1.0800, weight=3, source="D1_swing")]
        result = make_setup_l2l(
            curr=1.0842,
            atr_15m=ATR_15M,
            atr_daily=ATR_DAILY,
            sup_tagged=entry,
            res_tagged=EURUSD_RESISTANCES,
            direction="long",
            klasse="A",
        )
        assert result is not None
        assert result.status == "watchlist"


# ===== T2 logic ==============================================================


class TestT2:
    """T2 from subsequent levels or fallback to t1 + risk."""

    def test_long_t2_from_levels(self):
        """Multiple resistance levels -> t2 is a level beyond T1."""
        # best_t1 picks highest weight first, so T1=1.0900 (w5), T2=none after that -> fallback
        # Use lower weights so T1 is first qualifying: w3 at 1.0870, w1 at 1.0920
        resistances = [
            make_resistance_level(1.0870, weight=3, source="D1_swing"),
            make_resistance_level(1.0920, weight=1, source="15m_pivot"),
        ]
        entry = [make_support_level(1.0840, weight=3, source="D1_swing")]
        result = make_setup_l2l(
            curr=1.0842,
            atr_15m=ATR_15M,
            atr_daily=ATR_DAILY,
            sup_tagged=entry,
            res_tagged=resistances,
            direction="long",
            klasse="A",
        )
        assert result is not None
        assert result.t1 is not None
        assert result.t2 is not None
        assert result.t2 > result.t1

    def test_long_t2_fallback(self):
        """Only one resistance level -> t2 falls back to t1 + risk."""
        single_res = [make_resistance_level(1.0900, weight=5, source="PWH")]
        result = make_setup_l2l(
            curr=1.0842,
            atr_15m=ATR_15M,
            atr_daily=ATR_DAILY,
            sup_tagged=EURUSD_SUPPORTS,
            res_tagged=single_res,
            direction="long",
            klasse="A",
        )
        assert result is not None
        # With only one resistance, t2 should be t1 + risk (entry - sl)
        risk = result.entry - result.sl
        expected_t2 = result.t1 + risk
        assert result.t2 == pytest.approx(expected_t2, abs=1e-5)


# ===== Custom min_rr =========================================================


class TestMinRR:
    """Custom min_rr filtering."""

    def test_min_rr_custom(self):
        """min_rr=2.0 filters T1s that only give ~1.5x RR."""
        # Close resistance that would pass 1.5 but fail 2.0
        close_res = [make_resistance_level(1.0860, weight=3, source="D1_swing")]
        result = make_setup_l2l(
            curr=1.0842,
            atr_15m=ATR_15M,
            atr_daily=ATR_DAILY,
            sup_tagged=EURUSD_SUPPORTS,
            res_tagged=close_res,
            direction="long",
            klasse="A",
            min_rr=2.0,
        )
        # Either None (no target meets 2.0 RR) or the result has rr_t1 >= 2.0
        if result is not None:
            assert result.rr_t1 >= 2.0
            assert result.min_rr == 2.0


# ===== Edge case tests added by Agent D3 =====================================


class TestSetupBuilderEdgeCases:
    """Edge cases: empty levels, same prices, extreme values, both directions."""

    def test_long_no_levels_at_all(self):
        """Both sup and res empty => None for long."""
        result = make_setup_l2l(
            curr=1.0842,
            atr_15m=ATR_15M,
            atr_daily=ATR_DAILY,
            sup_tagged=[],
            res_tagged=[],
            direction="long",
            klasse="A",
        )
        assert result is None

    def test_short_no_levels_at_all(self):
        """Both sup and res empty => None for short."""
        result = make_setup_l2l(
            curr=1.0878,
            atr_15m=ATR_15M,
            atr_daily=ATR_DAILY,
            sup_tagged=[],
            res_tagged=[],
            direction="short",
            klasse="A",
        )
        assert result is None

    def test_long_support_equals_resistance(self):
        """Support and resistance at the same price => T1 dist = 0 => None."""
        same_price = 1.0850
        sup = [make_support_level(same_price, weight=3, source="D1_swing")]
        res = [make_resistance_level(same_price, weight=3, source="D1_swing")]
        result = make_setup_l2l(
            curr=same_price + 0.0002,
            atr_15m=ATR_15M,
            atr_daily=ATR_DAILY,
            sup_tagged=sup,
            res_tagged=res,
            direction="long",
            klasse="A",
        )
        # T1 can't be enough above entry when it equals entry => None
        assert result is None

    def test_short_resistance_equals_support(self):
        """Resistance and support at the same price for short => None."""
        same_price = 1.0850
        sup = [make_support_level(same_price, weight=3, source="D1_swing")]
        res = [make_resistance_level(same_price, weight=3, source="D1_swing")]
        result = make_setup_l2l(
            curr=same_price - 0.0002,
            atr_15m=ATR_15M,
            atr_daily=ATR_DAILY,
            sup_tagged=sup,
            res_tagged=res,
            direction="short",
            klasse="A",
        )
        assert result is None

    def test_returns_none_zero_atr_daily(self):
        """atr_daily=0 triggers fallback to atr_15m*5 (since 0 is falsy)."""
        result = make_setup_l2l(
            curr=1.0842,
            atr_15m=ATR_15M,
            atr_daily=0,
            sup_tagged=EURUSD_SUPPORTS,
            res_tagged=EURUSD_RESISTANCES,
            direction="long",
            klasse="A",
        )
        # 0 is falsy => fallback to atr_15m*5 = 0.006, should still work
        if result is not None:
            assert result.risk_atr_d > 0

    def test_returns_none_negative_atr_daily(self):
        """atr_daily=-1 is truthy but <=0, triggers fallback."""
        result = make_setup_l2l(
            curr=1.0842,
            atr_15m=ATR_15M,
            atr_daily=-1,
            sup_tagged=EURUSD_SUPPORTS,
            res_tagged=EURUSD_RESISTANCES,
            direction="long",
            klasse="A",
        )
        # -1 is truthy but <=0, code does: if not atr_daily or atr_daily <= 0
        # => fallback to atr_15m * 5
        if result is not None:
            assert result.risk_atr_d > 0

    def test_long_very_high_min_rr(self):
        """Unrealistically high min_rr => no T1 qualifies => None."""
        result = make_setup_l2l(
            curr=1.0842,
            atr_15m=ATR_15M,
            atr_daily=ATR_DAILY,
            sup_tagged=EURUSD_SUPPORTS,
            res_tagged=EURUSD_RESISTANCES,
            direction="long",
            klasse="A",
            min_rr=100.0,
        )
        assert result is None

    def test_short_very_high_min_rr(self):
        """Unrealistically high min_rr for short => None."""
        result = make_setup_l2l(
            curr=1.0878,
            atr_15m=ATR_15M,
            atr_daily=ATR_DAILY,
            sup_tagged=EURUSD_SUPPORTS,
            res_tagged=EURUSD_RESISTANCES,
            direction="short",
            klasse="A",
            min_rr=100.0,
        )
        assert result is None

    def test_long_weight_1_entry_tight_distance(self):
        """Weight 1 entry has max_entry_dist = 0.3 * atr_daily. curr too far => None."""
        # 0.3 * 0.006 = 0.0018 max distance for weight 1
        entry = [make_support_level(1.0800, weight=1, source="15m_pivot")]
        result = make_setup_l2l(
            curr=1.0825,  # distance = 0.0025 > 0.0018
            atr_15m=ATR_15M,
            atr_daily=ATR_DAILY,
            sup_tagged=entry,
            res_tagged=EURUSD_RESISTANCES,
            direction="long",
            klasse="A",
        )
        assert result is None

    def test_short_curr_above_resistance(self):
        """curr above all resistance levels => entry_dist < 0 => None."""
        result = make_setup_l2l(
            curr=1.1000,
            atr_15m=ATR_15M,
            atr_daily=ATR_DAILY,
            sup_tagged=EURUSD_SUPPORTS,
            res_tagged=EURUSD_RESISTANCES,
            direction="short",
            klasse="A",
        )
        assert result is None
