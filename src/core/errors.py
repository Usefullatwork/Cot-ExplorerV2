"""Custom exceptions for the trading signal platform."""


class ProviderError(Exception):
    """Base exception for data provider errors."""
    pass


class ProviderUnavailableError(ProviderError):
    """Raised when a data provider is unreachable or down."""
    pass


class RateLimitError(ProviderError):
    """Raised when a data provider rate limit is exceeded."""
    pass


class InvalidInstrumentError(ValueError):
    """Raised when an instrument key or symbol is not recognized."""
    pass


class InvalidDateRangeError(ValueError):
    """Raised when a date range is invalid or unsupported."""
    pass


class InsufficientDataError(Exception):
    """Raised when there is not enough historical data to compute a result."""
    pass
