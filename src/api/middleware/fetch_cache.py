"""Request coalescing cache for live API fetches.

Prevents triple-fetch when multiple frontend endpoints call the same
scraper within a short window (e.g. 3 geo-intel endpoints in parallel).

Simple module-level dict with timestamps. Thread-safe enough for
single-process uvicorn (no async race concern for read-then-write
since GIL serializes Python bytecode).
"""

from __future__ import annotations

import time
from typing import Any


_cache: dict[str, tuple[float, Any]] = {}


def get_cached(key: str, ttl: float = 60.0) -> Any | None:
    """Return cached value if it was stored less than `ttl` seconds ago.

    Args:
        key: Cache key (e.g. "seismic_live").
        ttl: Maximum age in seconds (default 60).

    Returns:
        The cached value, or None if missing/expired.
    """
    entry = _cache.get(key)
    if entry is None:
        return None
    stored_at, value = entry
    if time.monotonic() - stored_at > ttl:
        del _cache[key]
        return None
    return value


def set_cached(key: str, value: Any) -> None:
    """Store a value with the current timestamp.

    Args:
        key: Cache key.
        value: Value to cache.
    """
    _cache[key] = (time.monotonic(), value)


def clear_cache() -> None:
    """Clear all cached entries."""
    _cache.clear()
