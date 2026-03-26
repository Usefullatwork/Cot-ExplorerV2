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


class BotState(str, Enum):
    """Trading bot lifecycle state."""

    STOPPED = "STOPPED"
    STARTING = "STARTING"
    RUNNING = "RUNNING"
    STOPPING = "STOPPING"
    ERROR = "ERROR"


class PositionStatus(str, Enum):
    """Position lifecycle status.

    PENDING  – signal received but not yet filled.
    OPEN     – position active.
    PARTIAL  – T1 hit and 50 % closed.
    CLOSED   – fully closed.
    """

    PENDING = "PENDING"
    OPEN = "OPEN"
    PARTIAL = "PARTIAL"
    CLOSED = "CLOSED"


class ExitReason(str, Enum):
    """Reason a position was closed."""

    T1 = "T1"
    T2 = "T2"
    STOP_LOSS = "STOP_LOSS"
    EMA9_CROSS = "EMA9_CROSS"
    CANDLE_8 = "CANDLE_8"
    CANDLE_16 = "CANDLE_16"
    GEO_SPIKE = "GEO_SPIKE"
    KILL_SWITCH = "KILL_SWITCH"
    MANUAL = "MANUAL"
    EXPIRED = "EXPIRED"


class SignalStatus(str, Enum):
    """Status of a queued bot signal."""

    PENDING = "PENDING"
    CONFIRMED = "CONFIRMED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"


class BrokerMode(str, Enum):
    """Active broker execution mode."""

    PAPER = "PAPER"
    DEMO = "DEMO"
    LIVE = "LIVE"
