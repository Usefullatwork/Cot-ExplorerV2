"""Unit tests for src.trading.scrapers.energy_infra — static infrastructure data."""

from __future__ import annotations

import pytest

from src.trading.scrapers.energy_infra import (
    LNG_TERMINALS,
    MINES,
    PIPELINES,
    SHIPPING_LANES,
)

EXPECTED_COMMODITIES = {"gold", "silver", "copper", "lithium", "rare_earth"}
MINE_REQUIRED_KEYS = {"name", "lat", "lon", "type", "commodity", "country", "production"}
PIPELINE_REQUIRED_KEYS = {"name", "type", "color", "coords"}
LNG_REQUIRED_KEYS = {"name", "lat", "lon", "type", "country"}
SHIPPING_REQUIRED_KEYS = {"name", "color", "coords"}


class TestMines:
    """MINES collection validation."""

    def test_mine_count(self):
        """MINES has exactly 25 entries."""
        assert len(MINES) == 25

    def test_mine_required_keys(self):
        """Every mine has all required keys."""
        for mine in MINES:
            missing = MINE_REQUIRED_KEYS - set(mine.keys())
            assert not missing, f"{mine['name']} missing keys: {missing}"

    def test_mine_lat_range(self):
        """All mine latitudes are within -90..90."""
        for mine in MINES:
            assert -90 <= mine["lat"] <= 90, f"{mine['name']} lat={mine['lat']} out of range"

    def test_mine_lon_range(self):
        """All mine longitudes are within -180..180."""
        for mine in MINES:
            assert -180 <= mine["lon"] <= 180, f"{mine['name']} lon={mine['lon']} out of range"

    def test_no_duplicate_mine_names(self):
        """No duplicate mine names exist."""
        names = [m["name"] for m in MINES]
        assert len(names) == len(set(names)), f"Duplicates: {[n for n in names if names.count(n) > 1]}"

    def test_all_commodities_in_expected_set(self):
        """All mine commodities are in the expected set."""
        for mine in MINES:
            assert mine["commodity"] in EXPECTED_COMMODITIES, (
                f"{mine['name']} has unexpected commodity: {mine['commodity']}"
            )


class TestPipelines:
    """PIPELINES collection validation."""

    def test_pipeline_count(self):
        """PIPELINES has exactly 8 entries."""
        assert len(PIPELINES) == 8

    def test_pipeline_required_keys(self):
        """Every pipeline has all required keys."""
        for pipe in PIPELINES:
            missing = PIPELINE_REQUIRED_KEYS - set(pipe.keys())
            assert not missing, f"{pipe['name']} missing keys: {missing}"

    def test_pipeline_coords_are_lat_lon_pairs(self):
        """Pipeline coords are lists of [lat, lon] pairs with valid ranges."""
        for pipe in PIPELINES:
            assert isinstance(pipe["coords"], list), f"{pipe['name']} coords is not a list"
            assert len(pipe["coords"]) >= 2, f"{pipe['name']} needs at least 2 coordinate pairs"
            for pair in pipe["coords"]:
                assert len(pair) == 2, f"{pipe['name']} has coord with {len(pair)} values"
                lat, lon = pair
                assert -90 <= lat <= 90, f"{pipe['name']} coord lat={lat} out of range"
                assert -180 <= lon <= 180, f"{pipe['name']} coord lon={lon} out of range"


class TestLNGTerminals:
    """LNG_TERMINALS collection validation."""

    def test_lng_count(self):
        """LNG_TERMINALS has exactly 6 entries."""
        assert len(LNG_TERMINALS) == 6

    def test_lng_required_keys(self):
        """Every LNG terminal has all required keys."""
        for term in LNG_TERMINALS:
            missing = LNG_REQUIRED_KEYS - set(term.keys())
            assert not missing, f"{term['name']} missing keys: {missing}"

    def test_lng_lat_range(self):
        """All LNG terminal latitudes are within -90..90."""
        for term in LNG_TERMINALS:
            assert -90 <= term["lat"] <= 90, f"{term['name']} lat={term['lat']} out of range"

    def test_lng_lon_range(self):
        """All LNG terminal longitudes are within -180..180."""
        for term in LNG_TERMINALS:
            assert -180 <= term["lon"] <= 180, f"{term['name']} lon={term['lon']} out of range"


class TestShippingLanes:
    """SHIPPING_LANES collection validation."""

    def test_shipping_count(self):
        """SHIPPING_LANES has exactly 4 entries."""
        assert len(SHIPPING_LANES) == 4

    def test_shipping_required_keys(self):
        """Every shipping lane has all required keys."""
        for lane in SHIPPING_LANES:
            missing = SHIPPING_REQUIRED_KEYS - set(lane.keys())
            assert not missing, f"{lane['name']} missing keys: {missing}"

    def test_shipping_coords_are_lat_lon_pairs(self):
        """Shipping lane coords are lists of [lat, lon] pairs with valid ranges."""
        for lane in SHIPPING_LANES:
            assert isinstance(lane["coords"], list), f"{lane['name']} coords is not a list"
            assert len(lane["coords"]) >= 2, f"{lane['name']} needs at least 2 coordinate pairs"
            for pair in lane["coords"]:
                assert len(pair) == 2, f"{lane['name']} has coord with {len(pair)} values"
                lat, lon = pair
                assert -90 <= lat <= 90, f"{lane['name']} coord lat={lat} out of range"
                assert -180 <= lon <= 180, f"{lane['name']} coord lon={lon} out of range"
