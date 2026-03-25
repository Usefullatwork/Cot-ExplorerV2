"""Input validation and sanitization for the API boundary."""

from __future__ import annotations

import re
from datetime import datetime

from src.core.errors import InvalidDateRangeError, InvalidInstrumentError

# Whitelist of valid instrument keys — must match config/instruments.yaml
VALID_INSTRUMENTS = frozenset({
    "EURUSD", "USDJPY", "GBPUSD", "AUDUSD",
    "Gold", "Silver", "Brent", "WTI",
    "SPX", "NAS100", "VIX", "DXY",
})

# Maximum allowed date range: 20 years
_MAX_DATE_RANGE_DAYS = 20 * 365

# Characters stripped from search queries to prevent injection
_INJECTION_PATTERN = re.compile(r"[;'\"\\\x00-\x1f<>{}|^`]")


def validate_instrument(key: str) -> str:
    """Validate an instrument key against the whitelist.

    Parameters
    ----------
    key : str
        The instrument key to validate.

    Returns
    -------
    str
        The validated key.

    Raises
    ------
    InvalidInstrumentError
        If the key is not in the whitelist.
    """
    if key not in VALID_INSTRUMENTS:
        raise InvalidInstrumentError(
            f"Unknown instrument: {key!r}. "
            f"Valid keys: {', '.join(sorted(VALID_INSTRUMENTS))}"
        )
    return key


def validate_date_range(start: str, end: str) -> tuple[str, str]:
    """Validate that a date range is sane (max 20 years, start <= end).

    Parameters
    ----------
    start : str
        Start date in YYYY-MM-DD format.
    end : str
        End date in YYYY-MM-DD format.

    Returns
    -------
    tuple[str, str]
        The validated (start, end) pair.

    Raises
    ------
    InvalidDateRangeError
        If the range is invalid.
    """
    try:
        dt_start = datetime.strptime(start, "%Y-%m-%d")
        dt_end = datetime.strptime(end, "%Y-%m-%d")
    except ValueError as exc:
        raise InvalidDateRangeError(f"Invalid date format (expected YYYY-MM-DD): {exc}") from exc

    if dt_start > dt_end:
        raise InvalidDateRangeError(f"Start date {start} is after end date {end}")

    delta = (dt_end - dt_start).days
    if delta > _MAX_DATE_RANGE_DAYS:
        raise InvalidDateRangeError(
            f"Date range too large: {delta} days (max {_MAX_DATE_RANGE_DAYS})"
        )

    return start, end


def sanitize_search_query(q: str) -> str:
    """Strip injection-risk characters from a search query.

    Removes SQL metacharacters, control characters, and shell-special
    characters.  Returns the cleaned string, truncated to 200 chars.
    """
    cleaned = _INJECTION_PATTERN.sub("", q)
    return cleaned.strip()[:200]
