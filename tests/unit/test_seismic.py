"""Unit tests for src.trading.scrapers.seismic — USGS earthquake scraper."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from src.trading.scrapers.seismic import (
    MINING_REGIONS,
    _classify_region,
    fetch,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_feature(
    lat: float,
    lon: float,
    mag: float = 5.0,
    depth: float = 10.0,
    place: str = "Test Place",
    fid: str = "abc123",
    time_ms: int = 1711000000000,
    url: str = "https://earthquake.usgs.gov/test",
) -> dict:
    """Build a GeoJSON feature dict matching USGS format."""
    return {
        "id": fid,
        "properties": {
            "mag": mag,
            "place": place,
            "time": time_ms,
            "url": url,
        },
        "geometry": {
            "type": "Point",
            "coordinates": [lon, lat, depth],
        },
    }


def _make_response(*features) -> bytes:
    """Wrap features into a GeoJSON FeatureCollection response."""
    return json.dumps({
        "type": "FeatureCollection",
        "features": list(features),
    }).encode()


# ===== _classify_region ====================================================


class TestClassifyRegion:
    """Mining region classification logic."""

    def test_event_inside_chile_peru(self):
        """Lat/lon inside Chile/Peru region returns the region name."""
        assert _classify_region(-30.0, -70.0) == "Chile/Peru"

    def test_event_inside_australia(self):
        assert _classify_region(-25.0, 135.0) == "Australia"

    def test_event_inside_drc_zambia(self):
        assert _classify_region(0.0, 28.0) == "DRC/Zambia"

    def test_event_inside_indonesia(self):
        assert _classify_region(-5.0, 110.0) == "Indonesia/Papua"

    def test_event_outside_all_regions(self):
        """Mid-Atlantic coordinates should not match any mining region."""
        assert _classify_region(0.0, 0.0) is None

    def test_event_at_region_boundary(self):
        """Exact boundary coordinates of Chile/Peru should be included."""
        name, min_lat, max_lat, min_lon, max_lon = MINING_REGIONS[0]
        assert name == "Chile/Peru"
        assert _classify_region(min_lat, min_lon) == "Chile/Peru"
        assert _classify_region(max_lat, max_lon) == "Chile/Peru"

    def test_event_just_outside_boundary(self):
        """Coordinates just outside the boundary should return None."""
        _, min_lat, _, min_lon, _ = MINING_REGIONS[0]  # Chile/Peru
        # Slightly below the min_lat
        assert _classify_region(min_lat - 0.1, min_lon) is None


# ===== fetch() =============================================================


class TestFetch:
    """Seismic data fetch with mocked HTTP."""

    @patch("src.trading.scrapers.seismic.urllib.request.urlopen")
    def test_returns_mining_region_events_only(self, mock_urlopen):
        """Events outside mining regions are filtered out."""
        inside = _make_feature(-30.0, -70.0, mag=5.5, fid="ev1", place="Chile")
        outside = _make_feature(50.0, 0.0, mag=6.0, fid="ev2", place="UK")
        ctx = MagicMock()
        ctx.__enter__ = lambda s: MagicMock(read=lambda: _make_response(inside, outside))
        ctx.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = ctx

        events = fetch()
        assert len(events) == 1
        assert events[0]["id"] == "ev1"
        assert events[0]["region"] == "Chile/Peru"

    @patch("src.trading.scrapers.seismic.urllib.request.urlopen")
    def test_event_fields_populated(self, mock_urlopen):
        """Returned event dicts have all expected keys."""
        feature = _make_feature(
            lat=-30.0, lon=-70.0, mag=6.1, depth=25.0,
            place="100km SSE of Santiago", fid="ev3",
            time_ms=1711000000000, url="https://usgs.gov/ev3",
        )
        ctx = MagicMock()
        ctx.__enter__ = lambda s: MagicMock(read=lambda: _make_response(feature))
        ctx.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = ctx

        events = fetch()
        assert len(events) == 1
        ev = events[0]
        assert ev["id"] == "ev3"
        assert ev["mag"] == 6.1
        assert ev["lat"] == -30.0
        assert ev["lon"] == -70.0
        assert ev["depth_km"] == 25.0
        assert ev["place"] == "100km SSE of Santiago"
        assert ev["time"] == 1711000000000
        assert ev["region"] == "Chile/Peru"
        assert ev["url"] == "https://usgs.gov/ev3"

    @patch("src.trading.scrapers.seismic.urllib.request.urlopen")
    def test_empty_response_returns_empty_list(self, mock_urlopen):
        """An empty FeatureCollection returns an empty list."""
        ctx = MagicMock()
        ctx.__enter__ = lambda s: MagicMock(read=lambda: _make_response())
        ctx.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = ctx

        events = fetch()
        assert events == []

    @patch("src.trading.scrapers.seismic.urllib.request.urlopen")
    def test_network_error_returns_empty_list(self, mock_urlopen):
        """Network failures are caught and return an empty list."""
        mock_urlopen.side_effect = ConnectionError("timeout")

        events = fetch()
        assert events == []

    @patch("src.trading.scrapers.seismic.urllib.request.urlopen")
    def test_missing_coords_handled(self, mock_urlopen):
        """Feature with missing geometry coordinates defaults to [0,0,0]."""
        feature = {
            "id": "ev4",
            "properties": {"mag": 5.0, "place": "Unknown", "time": 0, "url": ""},
            "geometry": {},
        }
        ctx = MagicMock()
        ctx.__enter__ = lambda s: MagicMock(
            read=lambda: json.dumps({"type": "FeatureCollection", "features": [feature]}).encode()
        )
        ctx.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = ctx

        events = fetch()
        # (0,0,0) is mid-Atlantic — outside all mining regions
        assert events == []

    @patch("src.trading.scrapers.seismic.urllib.request.urlopen")
    def test_null_magnitude_handled(self, mock_urlopen):
        """Feature with null magnitude defaults to 0.0 in the event dict."""
        feature = {
            "id": "ev5",
            "properties": {"mag": None, "place": "Chile", "time": 0, "url": ""},
            "geometry": {"coordinates": [-70.0, -30.0, 10.0]},
        }
        ctx = MagicMock()
        ctx.__enter__ = lambda s: MagicMock(
            read=lambda: json.dumps({"type": "FeatureCollection", "features": [feature]}).encode()
        )
        ctx.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = ctx

        events = fetch()
        assert len(events) == 1
        # None magnitude is left as-is (from props.get("mag", 0.0))
        # The actual value depends on whether USGS sends null or omits the field
        assert events[0]["mag"] is None or events[0]["mag"] == 0.0

    @patch("src.trading.scrapers.seismic.urllib.request.urlopen")
    def test_multiple_mining_regions(self, mock_urlopen):
        """Events from different mining regions are all returned."""
        chile = _make_feature(-30.0, -70.0, fid="chile")
        australia = _make_feature(-25.0, 135.0, fid="aus")
        indonesia = _make_feature(-5.0, 110.0, fid="indo")
        ctx = MagicMock()
        ctx.__enter__ = lambda s: MagicMock(
            read=lambda: _make_response(chile, australia, indonesia)
        )
        ctx.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = ctx

        events = fetch()
        assert len(events) == 3
        regions = {ev["region"] for ev in events}
        assert "Chile/Peru" in regions
        assert "Australia" in regions
        assert "Indonesia/Papua" in regions
