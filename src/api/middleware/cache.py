"""Dict-based TTL cache for API responses."""

from __future__ import annotations

import time
from typing import Any


class TTLCache:
    """Simple in-process TTL cache backed by a plain dict.

    Parameters
    ----------
    default_ttl : int
        Default time-to-live in seconds for cached entries.
    """

    def __init__(self, default_ttl: int = 3600) -> None:
        self._store: dict[str, tuple[float, Any]] = {}
        self.default_ttl = default_ttl

    def get(self, key: str) -> Any | None:
        """Return the cached value if present and not expired, else ``None``."""
        entry = self._store.get(key)
        if entry is None:
            return None
        expires_at, value = entry
        if time.monotonic() > expires_at:
            del self._store[key]
            return None
        return value

    def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        """Store *value* under *key* with an optional per-entry TTL override."""
        ttl = ttl if ttl is not None else self.default_ttl
        self._store[key] = (time.monotonic() + ttl, value)

    def invalidate(self, key: str) -> None:
        """Remove a single key from the cache."""
        self._store.pop(key, None)

    def clear(self) -> None:
        """Drop all cached entries."""
        self._store.clear()

    def __len__(self) -> int:
        """Return number of entries (including potentially expired ones)."""
        return len(self._store)


# Shared cache instances used by route handlers
instruments_cache = TTLCache(default_ttl=86400)  # 24 hours
macro_cache = TTLCache(default_ttl=3600)          # 1 hour
