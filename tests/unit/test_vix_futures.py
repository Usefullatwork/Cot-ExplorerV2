"""Unit tests for src.trading.scrapers.vix_futures — VIX term structure."""

from __future__ import annotations

from src.trading.scrapers.vix_futures import (
    VixRegime,
    VixTermStructure,
    classify_regime,
    to_dict,
)


class TestClassifyRegime:
    """classify_regime threshold and classification tests."""

    def test_contango_normal(self):
        """VIX3M > spot by more than threshold -> CONTANGO."""
        assert classify_regime(18.0, 21.0) == VixRegime.CONTANGO

    def test_contango_at_threshold(self):
        """VIX3M > spot by exactly threshold -> FLAT (not > threshold)."""
        assert classify_regime(18.0, 18.5) == VixRegime.FLAT

    def test_contango_above_threshold(self):
        """VIX3M > spot by 0.51 -> CONTANGO."""
        assert classify_regime(18.0, 18.51) == VixRegime.CONTANGO

    def test_backwardation(self):
        """VIX spot > VIX3M by more than threshold -> BACKWARDATION."""
        assert classify_regime(30.0, 25.0) == VixRegime.BACKWARDATION

    def test_backwardation_at_threshold(self):
        """Spread exactly -0.5 -> FLAT."""
        assert classify_regime(20.0, 19.5) == VixRegime.FLAT

    def test_flat_equal(self):
        """Same values -> FLAT."""
        assert classify_regime(20.0, 20.0) == VixRegime.FLAT

    def test_flat_within_threshold(self):
        """Within threshold -> FLAT."""
        assert classify_regime(20.0, 20.3) == VixRegime.FLAT
        assert classify_regime(20.0, 19.7) == VixRegime.FLAT

    def test_custom_threshold(self):
        """Custom threshold works."""
        assert classify_regime(20.0, 21.0, threshold=1.5) == VixRegime.FLAT
        assert classify_regime(20.0, 22.0, threshold=1.5) == VixRegime.CONTANGO

    def test_extreme_backwardation(self):
        """Large VIX spike causes strong backwardation."""
        assert classify_regime(45.0, 25.0) == VixRegime.BACKWARDATION

    def test_extreme_contango(self):
        """Very calm market with steep contango."""
        assert classify_regime(12.0, 18.0) == VixRegime.CONTANGO


class TestVixTermStructure:
    """VixTermStructure NamedTuple behavior tests."""

    def test_fields(self):
        ts = VixTermStructure(spot=18.5, vix_9d=17.0, vix_3m=21.0, regime=VixRegime.CONTANGO, spread=2.5)
        assert ts.spot == 18.5
        assert ts.vix_9d == 17.0
        assert ts.vix_3m == 21.0
        assert ts.regime == VixRegime.CONTANGO
        assert ts.spread == 2.5


class TestToDict:
    """to_dict serialization tests."""

    def test_normal_structure(self):
        ts = VixTermStructure(spot=20.0, vix_9d=19.0, vix_3m=22.0, regime=VixRegime.CONTANGO, spread=2.0)
        d = to_dict(ts)
        assert d["spot"] == 20.0
        assert d["vix_9d"] == 19.0
        assert d["vix_3m"] == 22.0
        assert d["regime"] == "contango"
        assert d["spread"] == 2.0

    def test_none_returns_safe_default(self):
        d = to_dict(None)
        assert d["spot"] == 0.0
        assert d["regime"] == "flat"

    def test_backwardation_serialization(self):
        ts = VixTermStructure(spot=35.0, vix_9d=30.0, vix_3m=28.0, regime=VixRegime.BACKWARDATION, spread=-7.0)
        d = to_dict(ts)
        assert d["regime"] == "backwardation"
        assert d["spread"] == -7.0
