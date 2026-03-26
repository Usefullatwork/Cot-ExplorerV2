"""Unit tests for src.agents.registry — YAML prompt loading, lookup, filtering, counts."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

import src.agents.registry as registry

# ── Helpers ──────────────────────────────────────────────────────────


def _reset_registry() -> None:
    """Clear cached state so each test starts clean."""
    registry._all_prompts = []
    registry._by_id = {}
    registry._loaded = False


def _write_yaml(path: Path, data: dict) -> None:
    """Write a dict as a YAML file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.dump(data, allow_unicode=True), encoding="utf-8")


@pytest.fixture(autouse=True)
def _isolate_registry(tmp_path, monkeypatch):
    """Point the registry at a temp directory and reset caches after each test."""
    monkeypatch.setattr(registry, "_PROMPTS_DIR", tmp_path)
    _reset_registry()
    yield
    _reset_registry()


# ── Loading & listing ────────────────────────────────────────────────


class TestListPrompts:
    """Loading YAML files and listing all prompts."""

    def test_empty_directory_returns_no_prompts(self):
        """An empty prompts dir yields an empty list."""
        assert registry.list_prompts() == []
        assert registry.get_all_ids() == []

    def test_loads_single_yaml_file(self, tmp_path):
        """A valid YAML file with one prompt is loaded."""
        _write_yaml(
            tmp_path / "test.yaml",
            {
                "prompts": [
                    {
                        "id": "alpha",
                        "name": "Alpha Prompt",
                        "category": "backtesting",
                        "subcategory": "analysis",
                        "instrument": None,
                        "model": "sonnet",
                        "schedule": "weekly",
                        "prompt": "Do something.",
                    }
                ],
            },
        )
        prompts = registry.list_prompts()
        assert len(prompts) == 1
        assert prompts[0]["id"] == "alpha"

    def test_loads_multiple_files_across_subdirs(self, tmp_path):
        """YAML files in nested subdirectories are discovered."""
        _write_yaml(
            tmp_path / "a" / "one.yaml",
            {
                "prompts": [{"id": "p1", "category": "fundamental"}],
            },
        )
        _write_yaml(
            tmp_path / "b" / "two.yml",
            {
                "prompts": [{"id": "p2", "category": "risk_assessment"}],
            },
        )
        ids = registry.get_all_ids()
        assert ids == ["p1", "p2"]

    def test_skips_non_yaml_files(self, tmp_path):
        """Non-.yaml/.yml files are silently ignored."""
        (tmp_path / "readme.md").write_text("# Not a prompt", encoding="utf-8")
        (tmp_path / "data.json").write_text("{}", encoding="utf-8")
        _write_yaml(
            tmp_path / "real.yaml",
            {
                "prompts": [{"id": "only_one", "category": "meta"}],
            },
        )
        assert registry.get_all_ids() == ["only_one"]

    def test_skips_yaml_without_prompts_key(self, tmp_path):
        """YAML files missing the top-level 'prompts' key are ignored."""
        _write_yaml(tmp_path / "bad.yaml", {"agents": [{"id": "nope"}]})
        assert registry.list_prompts() == []

    def test_skips_yaml_with_null_content(self, tmp_path):
        """Empty YAML files (parsing to None) are ignored."""
        (tmp_path / "empty.yaml").write_text("", encoding="utf-8")
        assert registry.list_prompts() == []


# ── Lookup by id ─────────────────────────────────────────────────────


class TestGetPrompt:
    """Looking up a single prompt by its id."""

    def test_returns_prompt_by_id(self, tmp_path):
        _write_yaml(
            tmp_path / "p.yaml",
            {
                "prompts": [
                    {"id": "first", "name": "First", "category": "backtesting"},
                    {"id": "second", "name": "Second", "category": "fundamental"},
                ],
            },
        )
        result = registry.get_prompt("second")
        assert result is not None
        assert result["name"] == "Second"

    def test_returns_none_for_missing_id(self, tmp_path):
        _write_yaml(
            tmp_path / "p.yaml",
            {
                "prompts": [{"id": "exists", "category": "meta"}],
            },
        )
        assert registry.get_prompt("nonexistent") is None

    def test_returns_none_on_empty_registry(self):
        assert registry.get_prompt("anything") is None


# ── Duplicate id detection ───────────────────────────────────────────


class TestDuplicateIds:
    """Duplicate prompt ids raise ValueError."""

    def test_duplicate_id_within_same_file(self, tmp_path):
        _write_yaml(
            tmp_path / "dup.yaml",
            {
                "prompts": [
                    {"id": "dup1", "category": "a"},
                    {"id": "dup1", "category": "b"},
                ],
            },
        )
        with pytest.raises(ValueError, match="Duplicate prompt id 'dup1'"):
            registry.list_prompts()

    def test_duplicate_id_across_files(self, tmp_path):
        _write_yaml(
            tmp_path / "a.yaml",
            {
                "prompts": [{"id": "shared", "category": "a"}],
            },
        )
        _write_yaml(
            tmp_path / "b.yaml",
            {
                "prompts": [{"id": "shared", "category": "b"}],
            },
        )
        with pytest.raises(ValueError, match="Duplicate prompt id 'shared'"):
            registry.list_prompts()


# ── Category / filter tests ──────────────────────────────────────────


class TestCategoryFiltering:
    """list_prompts filters by category, subcategory, instrument, model, schedule."""

    @pytest.fixture(autouse=True)
    def _seed_prompts(self, tmp_path):
        _write_yaml(
            tmp_path / "mixed.yaml",
            {
                "prompts": [
                    {
                        "id": "bt1",
                        "category": "backtesting",
                        "subcategory": "analysis",
                        "instrument": None,
                        "model": "sonnet",
                        "schedule": "weekly",
                    },
                    {
                        "id": "fa1",
                        "category": "fundamental",
                        "subcategory": "sector",
                        "instrument": "XAUUSD",
                        "model": "opus",
                        "schedule": "daily",
                    },
                    {
                        "id": "fa2",
                        "category": "fundamental",
                        "subcategory": "macro",
                        "instrument": None,
                        "model": "sonnet",
                        "schedule": "daily",
                    },
                ],
            },
        )

    def test_filter_by_category(self):
        results = registry.list_prompts(category="fundamental")
        assert len(results) == 2
        assert all(p["category"] == "fundamental" for p in results)

    def test_filter_by_subcategory(self):
        results = registry.list_prompts(subcategory="sector")
        assert len(results) == 1
        assert results[0]["id"] == "fa1"

    def test_filter_by_instrument(self):
        results = registry.list_prompts(instrument="XAUUSD")
        assert len(results) == 1
        assert results[0]["id"] == "fa1"

    def test_filter_by_model(self):
        results = registry.list_prompts(model="sonnet")
        assert len(results) == 2

    def test_filter_by_schedule(self):
        results = registry.list_prompts(schedule="daily")
        assert len(results) == 2

    def test_combined_filters(self):
        results = registry.list_prompts(category="fundamental", model="sonnet")
        assert len(results) == 1
        assert results[0]["id"] == "fa2"

    def test_no_matches_returns_empty(self):
        assert registry.list_prompts(category="nonexistent") == []

    def test_no_filters_returns_all(self):
        assert len(registry.list_prompts()) == 3


# ── Instrument lookup ────────────────────────────────────────────────


class TestGetPromptsForInstrument:
    """get_prompts_for_instrument returns instrument-specific + cross-instrument prompts."""

    @pytest.fixture(autouse=True)
    def _seed(self, tmp_path):
        _write_yaml(
            tmp_path / "inst.yaml",
            {
                "prompts": [
                    {"id": "specific", "category": "risk", "instrument": "EURUSD"},
                    {"id": "cross", "category": "meta", "instrument": None},
                    {"id": "other", "category": "risk", "instrument": "GBPUSD"},
                ],
            },
        )

    def test_includes_matching_instrument(self):
        results = registry.get_prompts_for_instrument("EURUSD")
        ids = [p["id"] for p in results]
        assert "specific" in ids

    def test_includes_cross_instrument(self):
        results = registry.get_prompts_for_instrument("EURUSD")
        ids = [p["id"] for p in results]
        assert "cross" in ids

    def test_excludes_other_instrument(self):
        results = registry.get_prompts_for_instrument("EURUSD")
        ids = [p["id"] for p in results]
        assert "other" not in ids


# ── count_prompts / summary ──────────────────────────────────────────


class TestCountsAndSummary:
    """count_prompts and summary aggregate correctly."""

    @pytest.fixture(autouse=True)
    def _seed(self, tmp_path):
        _write_yaml(
            tmp_path / "mix.yaml",
            {
                "prompts": [
                    {"id": "a", "category": "backtesting", "model": "sonnet", "schedule": "weekly"},
                    {"id": "b", "category": "backtesting", "model": "sonnet", "schedule": "daily"},
                    {"id": "c", "category": "fundamental", "model": "opus", "schedule": "daily"},
                ],
            },
        )

    def test_count_prompts(self):
        counts = registry.count_prompts()
        assert counts == {"backtesting": 2, "fundamental": 1}

    def test_summary_total(self):
        s = registry.summary()
        assert s["total_prompts"] == 3

    def test_summary_by_model(self):
        s = registry.summary()
        assert s["by_model"] == {"sonnet": 2, "opus": 1}

    def test_summary_by_schedule(self):
        s = registry.summary()
        assert s["by_schedule"] == {"weekly": 1, "daily": 2}


# ── reload ───────────────────────────────────────────────────────────


class TestReload:
    """reload() re-reads YAML files picking up changes."""

    def test_reload_picks_up_new_file(self, tmp_path):
        _write_yaml(
            tmp_path / "v1.yaml",
            {
                "prompts": [{"id": "original", "category": "meta"}],
            },
        )
        assert registry.get_all_ids() == ["original"]

        # Add another file and reload
        _write_yaml(
            tmp_path / "v2.yaml",
            {
                "prompts": [{"id": "added", "category": "meta"}],
            },
        )
        registry.reload()
        assert sorted(registry.get_all_ids()) == ["added", "original"]


# ── Source file tracking ─────────────────────────────────────────────


class TestSourceFileTracking:
    """Each loaded prompt records its _source_file relative to prompts dir."""

    def test_source_file_set(self, tmp_path):
        _write_yaml(
            tmp_path / "sub" / "deep.yaml",
            {
                "prompts": [{"id": "tracked", "category": "meta"}],
            },
        )
        p = registry.get_prompt("tracked")
        assert p is not None
        # Relative path under the prompts dir, normalized to forward slashes
        assert "deep.yaml" in p["_source_file"]


# ── Prompts without id ───────────────────────────────────────────────


class TestPromptsWithoutId:
    """Prompts missing an 'id' key still load but are not in _by_id."""

    def test_no_id_prompt_in_list(self, tmp_path):
        _write_yaml(
            tmp_path / "noid.yaml",
            {
                "prompts": [
                    {"name": "Anonymous", "category": "meta"},
                    {"id": "has_id", "name": "Named", "category": "meta"},
                ],
            },
        )
        all_prompts = registry.list_prompts()
        assert len(all_prompts) == 2
        # Only the one with id is in get_all_ids
        assert registry.get_all_ids() == ["has_id"]
