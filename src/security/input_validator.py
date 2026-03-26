"""Input validation and sanitization for API boundaries."""

import re

# Patterns that should never appear in user input
DANGEROUS_PATTERNS = [
    re.compile(r'[;\'"\\]'),  # SQL injection chars
    re.compile(r"<script", re.IGNORECASE),  # XSS
    re.compile(r"\.\./"),  # Path traversal
]


def sanitize_string(value: str, max_length: int = 1000) -> str:
    """Sanitize a string input by truncating and stripping dangerous chars."""
    value = value.strip()[:max_length]
    for pattern in DANGEROUS_PATTERNS:
        value = pattern.sub("", value)
    return value


def validate_symbol(symbol: str) -> str:
    """Validate a trading symbol (e.g., 'EURUSD', 'XAUUSD')."""
    symbol = symbol.upper().strip()
    if not re.match(r"^[A-Z0-9_./]{1,20}$", symbol):
        raise ValueError(f"Invalid symbol: {symbol}")
    return symbol


def validate_instrument_key(key: str) -> str:
    """Validate an instrument key from instruments.yaml."""
    key = key.lower().strip()
    if not re.match(r"^[a-z0-9_-]{1,50}$", key):
        raise ValueError(f"Invalid instrument key: {key}")
    return key
