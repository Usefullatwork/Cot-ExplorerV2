"""Unit tests for src.api.middleware.fetch_cache — request coalescing cache."""

from __future__ import annotations

import time
from unittest.mock import patch

from src.api.middleware.fetch_cache import clear_cache, get_cached, set_cached


class TestFetchCache:
    """get_cached / set_cached tests."""

    def setup_method(self):
        clear_cache()

    def test_miss_returns_none(self):
        assert get_cached("nonexistent") is None

    def test_set_then_get(self):
        set_cached("key1", {"data": 42})
        assert get_cached("key1") == {"data": 42}

    def test_expired_returns_none(self):
        set_cached("key2", "val")
        # Simulate expiry by patching time
        with patch("src.api.middleware.fetch_cache.time") as mock_time:
            mock_time.monotonic.return_value = time.monotonic() + 100
            assert get_cached("key2", ttl=60) is None

    def test_custom_ttl(self):
        set_cached("key3", "val")
        # Within TTL
        assert get_cached("key3", ttl=120) == "val"

    def test_clear_removes_all(self):
        set_cached("a", 1)
        set_cached("b", 2)
        clear_cache()
        assert get_cached("a") is None
        assert get_cached("b") is None

    def test_overwrite(self):
        set_cached("key", "old")
        set_cached("key", "new")
        assert get_cached("key") == "new"

    def test_different_keys_independent(self):
        set_cached("x", 10)
        set_cached("y", 20)
        assert get_cached("x") == 10
        assert get_cached("y") == 20
