"""Unit tests for src.publishers.json_file — file write, v1 compat format."""

import json
from pathlib import Path

import pytest

from src.publishers.json_file import publish_static_json


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _sample_macro() -> dict:
    """Return a minimal v1-shaped macro data dict."""
    return {
        "date": "2026-03-25",
        "cot_date": "2026-03-21",
        "prices": {"ES": 5200, "NQ": 18500},
        "vix_regime": "LOW",
        "dollar_smile": "RISK_ON",
        "trading_levels": {"ES": {"pivot": 5150}},
        "calendar": [],
    }


# ===== File writing ========================================================

class TestPublishStaticJson:
    """Core write behaviour."""

    def test_creates_latest_json(self, tmp_path):
        data = _sample_macro()
        result = publish_static_json(data, output_dir=tmp_path)
        assert result == tmp_path / "latest.json"
        assert result.exists()

    def test_written_content_matches_input(self, tmp_path):
        data = _sample_macro()
        path = publish_static_json(data, output_dir=tmp_path)
        with open(path, encoding="utf-8") as f:
            loaded = json.load(f)
        assert loaded == data

    def test_json_is_pretty_printed(self, tmp_path):
        data = _sample_macro()
        path = publish_static_json(data, output_dir=tmp_path)
        raw = path.read_text(encoding="utf-8")
        # indent=2 means nested keys should be indented
        assert "\n  " in raw

    def test_unicode_preserved(self, tmp_path):
        data = {"date": "2026-03-25", "note": "V\u00e6r forsiktig"}
        path = publish_static_json(data, output_dir=tmp_path)
        raw = path.read_text(encoding="utf-8")
        assert "V\u00e6r forsiktig" in raw
        assert "\\u" not in raw  # ensure_ascii=False

    def test_creates_nested_dirs(self, tmp_path):
        nested = tmp_path / "a" / "b" / "c"
        data = _sample_macro()
        path = publish_static_json(data, output_dir=nested)
        assert path.exists()
        assert nested.exists()

    def test_overwrites_existing_file(self, tmp_path):
        data_v1 = {"version": 1}
        data_v2 = {"version": 2}
        publish_static_json(data_v1, output_dir=tmp_path)
        path = publish_static_json(data_v2, output_dir=tmp_path)
        with open(path, encoding="utf-8") as f:
            assert json.load(f) == data_v2


class TestPublishDefaults:
    """Test default output directory and return value."""

    def test_returns_path_object(self, tmp_path):
        result = publish_static_json({}, output_dir=tmp_path)
        assert isinstance(result, Path)

    def test_filename_is_latest_json(self, tmp_path):
        result = publish_static_json({}, output_dir=tmp_path)
        assert result.name == "latest.json"


class TestV1CompatFormat:
    """Verify all expected v1 keys survive the round-trip unchanged."""

    def test_all_v1_keys_present(self, tmp_path):
        data = _sample_macro()
        path = publish_static_json(data, output_dir=tmp_path)
        with open(path, encoding="utf-8") as f:
            loaded = json.load(f)
        for key in ("date", "cot_date", "prices", "vix_regime", "dollar_smile", "trading_levels", "calendar"):
            assert key in loaded, f"Missing v1 key: {key}"

    def test_nested_structures_preserved(self, tmp_path):
        data = _sample_macro()
        path = publish_static_json(data, output_dir=tmp_path)
        with open(path, encoding="utf-8") as f:
            loaded = json.load(f)
        assert loaded["prices"]["ES"] == 5200
        assert loaded["trading_levels"]["ES"]["pivot"] == 5150

    def test_empty_calendar_preserved(self, tmp_path):
        data = _sample_macro()
        path = publish_static_json(data, output_dir=tmp_path)
        with open(path, encoding="utf-8") as f:
            loaded = json.load(f)
        assert loaded["calendar"] == []
