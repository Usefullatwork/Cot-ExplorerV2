"""Core enumerations for the trading signal platform."""

from enum import Enum


class Direction(str, Enum):
    """Price direction bias."""

    BULL = "bull"
    BEAR = "bear"


class Grade(str, Enum):
    """Confluence score grade."""

    A_PLUS = "A+"
    A = "A"
    B = "B"
    C = "C"


class TimeframeBias(str, Enum):
    """Timeframe classification for trade setups."""

    MAKRO = "MAKRO"
    SWING = "SWING"
    SCALP = "SCALP"
    WATCHLIST = "WATCHLIST"


class VixRegime(str, Enum):
    """VIX volatility regime."""

    NORMAL = "normal"
    ELEVATED = "elevated"
    EXTREME = "extreme"


class SmcStructure(str, Enum):
    """Smart Money Concept market structure."""

    BULLISH = "BULLISH"
    BEARISH = "BEARISH"
    MIXED = "MIXED"
    BULLISH_SVAK = "BULLISH_SVAK"
    BEARISH_SVAK = "BEARISH_SVAK"


class CotMomentum(str, Enum):
    """COT positioning momentum."""

    OKER = "ØKER"
    SNUR = "SNUR"
    STABIL = "STABIL"


class CotBias(str, Enum):
    """COT directional bias."""

    LONG = "LONG"
    SHORT = "SHORT"
    NOYTRAL = "NØYTRAL"
