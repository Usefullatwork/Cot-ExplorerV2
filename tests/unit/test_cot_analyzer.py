"""Unit tests for src.analysis.cot_analyzer — classify_cot_bias, classify_cot_momentum, get_cot_for_instrument."""

import pytest

from src.analysis.cot_analyzer import (
    classify_cot_bias,
    classify_cot_momentum,
    get_cot_for_instrument,
)


# ===== classify_cot_bias ====================================================

class TestClassifyCotBias:
    """LONG if pct>4, SHORT if pct<-4, NØYTRAL otherwise. oi=0 -> uses 1."""

    def test_long_bias(self):
        label, pct = classify_cot_bias(5000, 100000)
        assert label == "LONG"
        assert pct == pytest.approx(5.0)

    def test_short_bias(self):
        label, pct = classify_cot_bias(-5000, 100000)
        assert label == "SHORT"
        assert pct == pytest.approx(-5.0)

    def test_neutral_bias(self):
        label, pct = classify_cot_bias(3000, 100000)
        assert label == "NØYTRAL"
        assert pct == pytest.approx(3.0)

    def test_boundary_exactly_4_percent_is_neutral(self):
        """4% is NOT > 4, so should be NØYTRAL."""
        label, pct = classify_cot_bias(4000, 100000)
        assert label == "NØYTRAL"
        assert pct == pytest.approx(4.0)

    def test_boundary_just_above_4_is_long(self):
        label, pct = classify_cot_bias(4010, 100000)
        assert label == "LONG"
        assert pct == pytest.approx(4.01)

    def test_boundary_exactly_neg4_is_neutral(self):
        label, pct = classify_cot_bias(-4000, 100000)
        assert label == "NØYTRAL"
        assert pct == pytest.approx(-4.0)

    def test_boundary_just_below_neg4_is_short(self):
        label, pct = classify_cot_bias(-4010, 100000)
        assert label == "SHORT"
        assert pct == pytest.approx(-4.01)

    def test_zero_oi_uses_1(self):
        """Division safety: oi=0 should use 1 as denominator."""
        label, pct = classify_cot_bias(5, 0)
        assert pct == pytest.approx(500.0)  # 5/1 * 100 = 500
        assert label == "LONG"

    def test_pct_calculation(self):
        label, pct = classify_cot_bias(10000, 200000)
        assert pct == pytest.approx(5.0)


# ===== classify_cot_momentum ================================================

class TestClassifyCotMomentum:
    """ØKER if adding to direction, SNUR if reducing/reversing, STABIL if change==0."""

    def test_oker_positive(self):
        """change>0 and net>=0 -> adding to longs."""
        result = classify_cot_momentum(500, 3000)
        assert result == "ØKER"

    def test_oker_negative(self):
        """change<0 and net<=0 -> adding to shorts."""
        result = classify_cot_momentum(-500, -3000)
        assert result == "ØKER"

    def test_snur_reducing_short(self):
        """change>0 but net<0 -> reducing short position."""
        result = classify_cot_momentum(500, -3000)
        assert result == "SNUR"

    def test_snur_reducing_long(self):
        """change<0 but net>0 -> reducing long position."""
        result = classify_cot_momentum(-500, 3000)
        assert result == "SNUR"

    def test_stabil(self):
        """change==0 -> stable."""
        result = classify_cot_momentum(0, 3000)
        assert result == "STABIL"


# ===== get_cot_for_instrument ===============================================

class TestGetCotForInstrument:

    def test_found(self):
        cot_data = {"WHEAT": {"spec_net": 5000, "oi": 100000}}
        cot_map = {"wheat_futures": "WHEAT"}
        result = get_cot_for_instrument(cot_data, "wheat_futures", cot_map)
        assert result is not None
        assert result["spec_net"] == 5000

    def test_not_in_map(self):
        cot_data = {"WHEAT": {"spec_net": 5000}}
        cot_map = {"wheat_futures": "WHEAT"}
        result = get_cot_for_instrument(cot_data, "corn_futures", cot_map)
        assert result is None

    def test_not_in_data(self):
        cot_data = {}
        cot_map = {"wheat_futures": "WHEAT"}
        result = get_cot_for_instrument(cot_data, "wheat_futures", cot_map)
        assert result is None
