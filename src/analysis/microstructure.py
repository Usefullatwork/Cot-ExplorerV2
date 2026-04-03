"""Market microstructure analysis -- liquidity scoring, spread quality, execution windows.

Pure functions with no I/O or database access.  Every function is
deterministic and side-effect-free.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Sequence

# ---------------------------------------------------------------------------
# Enums & data classes
# ---------------------------------------------------------------------------


class SpreadQuality(str, Enum):
    """Spread quality classification."""

    EXCELLENT = "excellent"   # < 0.5x typical
    GOOD = "good"             # 0.5-0.8x typical
    NORMAL = "normal"         # 0.8-1.2x typical
    WIDE = "wide"             # 1.2-2.0x typical
    VERY_WIDE = "very_wide"   # > 2.0x typical


@dataclass(frozen=True)
class LiquidityScore:
    """Liquidity assessment for an instrument at a point in time."""

    instrument: str
    score: float              # 0.0-1.0 (1=most liquid)
    session: str              # current session name
    hour_cet: int
    vix_adjustment: float     # negative when VIX is high
    reason: str


@dataclass(frozen=True)
class ExecutionWindow:
    """Optimal execution timing recommendation."""

    instrument: str
    best_start_cet: int
    best_end_cet: int
    session: str
    expected_spread_quality: SpreadQuality


@dataclass(frozen=True)
class ExecutionQualityMetrics:
    """Aggregate execution quality from a set of fills."""

    n_fills: int
    avg_slippage_pips: float
    max_slippage_pips: float
    avg_spread_quality: float      # 0-1 (1=best)
    fill_rate: float               # fraction of orders that filled
    cost_vs_mid_pips: float        # average cost relative to mid price


# ---------------------------------------------------------------------------
# Base liquidity tables
# ---------------------------------------------------------------------------

# Higher = more liquid.  Keyed by instrument category then session.
_BASE_LIQUIDITY: dict[str, dict[str, float]] = {
    "forex_major": {
        "london": 0.95, "ny_overlap": 0.98, "ny": 0.85,
        "asian": 0.60, "off_hours": 0.30,
    },
    "forex_safe": {
        "london": 0.90, "ny_overlap": 0.95, "ny": 0.80,
        "asian": 0.70, "off_hours": 0.25,
    },
    "commodity_precious": {
        "london": 0.85, "ny_overlap": 0.90, "ny": 0.80,
        "asian": 0.50, "off_hours": 0.20,
    },
    "commodity_energy": {
        "london": 0.70, "ny_overlap": 0.80, "ny": 0.85,
        "asian": 0.40, "off_hours": 0.15,
    },
    "commodity_agriculture": {
        "london": 0.50, "ny_overlap": 0.60, "ny": 0.70,
        "asian": 0.20, "off_hours": 0.10,
    },
    "index": {
        "london": 0.70, "ny_overlap": 0.85, "ny": 0.90,
        "asian": 0.40, "off_hours": 0.15,
    },
    "pgm": {
        "london": 0.60, "ny_overlap": 0.70, "ny": 0.65,
        "asian": 0.30, "off_hours": 0.10,
    },
}

# Map instrument symbols to microstructure classes.
_INSTRUMENT_CLASS: dict[str, str] = {
    "EURUSD": "forex_major", "GBPUSD": "forex_major", "AUDUSD": "forex_major",
    "USDJPY": "forex_safe", "USDCHF": "forex_safe",
    "Gold": "commodity_precious", "Silver": "commodity_precious",
    "Brent": "commodity_energy", "WTI": "commodity_energy", "NATGAS": "commodity_energy",
    "WHEAT": "commodity_agriculture", "CORN": "commodity_agriculture",
    "SPX": "index", "NAS100": "index",
    "XPTUSD": "pgm", "XPDUSD": "pgm",
}

# Default liquidity for unknown instruments (conservative).
_DEFAULT_LIQUIDITY: dict[str, float] = {
    "london": 0.30, "ny_overlap": 0.35, "ny": 0.30,
    "asian": 0.15, "off_hours": 0.05,
}

# Session CET hour ranges for execution window recommendations.
_SESSION_HOURS: dict[str, tuple[int, int]] = {
    "ny_overlap": (13, 17),
    "london": (7, 13),
    "ny": (17, 21),
    "asian": (23, 7),
    "off_hours": (21, 23),
}


# ---------------------------------------------------------------------------
# Session classification (mirrors transaction_costs.classify_session)
# ---------------------------------------------------------------------------

_SESSION_RANGES: list[tuple[str, int, int]] = [
    ("ny_overlap", 13, 17),
    ("london", 7, 13),
    ("ny", 17, 21),
]

_ASIAN_START = 23
_ASIAN_END = 7


def classify_session(hour_cet: int) -> str:
    """Map a CET hour (0-23) to a trading session name.

    Uses the same logic as ``transaction_costs.classify_session``:
    ny_overlap (13-16), london (7-12), ny (17-20),
    asian (23-06 wrapping midnight), off_hours otherwise.
    """
    hour = hour_cet % 24

    for name, start, end in _SESSION_RANGES:
        if start <= hour < end:
            return name

    if hour >= _ASIAN_START or hour < _ASIAN_END:
        return "asian"

    return "off_hours"


# ---------------------------------------------------------------------------
# Core functions
# ---------------------------------------------------------------------------


def liquidity_score(
    instrument: str,
    hour_cet: int,
    vix: float = 15.0,
    vix_threshold: float = 25.0,
) -> LiquidityScore:
    """Compute liquidity score for an instrument at a given time.

    Base score comes from ``_BASE_LIQUIDITY`` by instrument class and
    session.  When ``vix > vix_threshold`` the score is reduced by
    ``(vix - threshold) * 0.01``.  Result is clamped to [0.0, 1.0].

    Parameters
    ----------
    instrument:
        Instrument symbol (e.g. ``"EURUSD"``).
    hour_cet:
        Hour of day in CET (0-23).
    vix:
        Current VIX level (default 15.0 = calm market).
    vix_threshold:
        VIX level above which liquidity is penalised (default 25.0).

    Returns
    -------
    LiquidityScore
        Frozen dataclass with score and metadata.
    """
    session = classify_session(hour_cet)
    inst_class = _INSTRUMENT_CLASS.get(instrument)

    if inst_class is not None:
        session_map = _BASE_LIQUIDITY[inst_class]
        reason = f"{inst_class} in {session}"
    else:
        session_map = _DEFAULT_LIQUIDITY
        reason = f"unknown instrument '{instrument}' — using default"

    base = session_map.get(session, session_map.get("off_hours", 0.10))

    vix_adj = 0.0
    if vix > vix_threshold:
        vix_adj = -(vix - vix_threshold) * 0.01

    score = max(0.0, min(1.0, base + vix_adj))

    return LiquidityScore(
        instrument=instrument,
        score=score,
        session=session,
        hour_cet=hour_cet % 24,
        vix_adjustment=vix_adj,
        reason=reason,
    )


def optimal_execution_window(
    instrument: str,
) -> ExecutionWindow:
    """Recommend the best execution window for an instrument.

    Finds the session with the highest base liquidity for the
    instrument's class and maps it to a CET hour range.

    Parameters
    ----------
    instrument:
        Instrument symbol (e.g. ``"EURUSD"``).

    Returns
    -------
    ExecutionWindow
        Frozen dataclass with session and hour range.
    """
    inst_class = _INSTRUMENT_CLASS.get(instrument)
    session_map = (
        _BASE_LIQUIDITY[inst_class] if inst_class else _DEFAULT_LIQUIDITY
    )

    best_session = max(session_map, key=session_map.get)  # type: ignore[arg-type]
    start, end = _SESSION_HOURS.get(best_session, (0, 24))

    return ExecutionWindow(
        instrument=instrument,
        best_start_cet=start,
        best_end_cet=end,
        session=best_session,
        expected_spread_quality=SpreadQuality.EXCELLENT,
    )


def classify_spread_quality(
    actual_spread: float,
    typical_spread: float,
) -> SpreadQuality:
    """Classify spread quality relative to the typical spread.

    Parameters
    ----------
    actual_spread:
        Observed spread in pips.
    typical_spread:
        Normal/expected spread in pips.  If zero or negative, returns
        ``VERY_WIDE`` to avoid division by zero.

    Returns
    -------
    SpreadQuality
        Classification from EXCELLENT to VERY_WIDE.
    """
    if typical_spread <= 0:
        return SpreadQuality.VERY_WIDE

    ratio = actual_spread / typical_spread

    if ratio < 0.5:
        return SpreadQuality.EXCELLENT
    if ratio < 0.8:
        return SpreadQuality.GOOD
    if ratio < 1.2:
        return SpreadQuality.NORMAL
    if ratio < 2.0:
        return SpreadQuality.WIDE
    return SpreadQuality.VERY_WIDE


def execution_quality_report(
    execution_log: Sequence[dict],
) -> ExecutionQualityMetrics:
    """Aggregate execution quality from a sequence of fill records.

    Each entry in *execution_log* must contain:

    - ``slippage_pips`` (float)
    - ``spread_pips`` (float)
    - ``typical_spread`` (float)
    - ``filled`` (bool)
    - ``cost_vs_mid_pips`` (float)

    Parameters
    ----------
    execution_log:
        List of fill dictionaries.

    Returns
    -------
    ExecutionQualityMetrics
        Aggregate metrics.  Returns zeroed metrics for an empty log.
    """
    if not execution_log:
        return ExecutionQualityMetrics(
            n_fills=0,
            avg_slippage_pips=0.0,
            max_slippage_pips=0.0,
            avg_spread_quality=0.0,
            fill_rate=0.0,
            cost_vs_mid_pips=0.0,
        )

    n = len(execution_log)
    total_slippage = 0.0
    max_slip = 0.0
    total_spread_quality = 0.0
    filled_count = 0
    total_cost_mid = 0.0

    for entry in execution_log:
        slip = entry.get("slippage_pips", 0.0)
        total_slippage += slip
        if slip > max_slip:
            max_slip = slip

        typical = entry.get("typical_spread", 0.0)
        actual = entry.get("spread_pips", 0.0)
        if typical > 0:
            ratio = actual / typical
            # quality: 1.0 = perfect (ratio=0), 0.0 = 2x typical or worse
            quality = max(0.0, min(1.0, 1.0 - ratio / 2.0))
        else:
            quality = 0.0
        total_spread_quality += quality

        if entry.get("filled", False):
            filled_count += 1

        total_cost_mid += entry.get("cost_vs_mid_pips", 0.0)

    return ExecutionQualityMetrics(
        n_fills=n,
        avg_slippage_pips=total_slippage / n,
        max_slippage_pips=max_slip,
        avg_spread_quality=total_spread_quality / n,
        fill_rate=filled_count / n,
        cost_vs_mid_pips=total_cost_mid / n,
    )
