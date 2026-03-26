"""Confluence scoring — pure function, no side effects.

16-point system: original 12 criteria + 4 institutional-grade factors
(Order Block, FVG, Session Alignment, Correlation Clear).
"""

from __future__ import annotations

from src.core.models import ScoreDetail, ScoringInput, ScoringResult

# Correlated instrument groups — any open signal on a peer = conflict.
_CORRELATION_MAP: dict[str, list[str]] = {
    "EURUSD": ["GBPUSD", "EURGBP"], "GBPUSD": ["EURUSD", "EURGBP"],
    "EURGBP": ["EURUSD", "GBPUSD"], "AUDUSD": ["NZDUSD"],
    "NZDUSD": ["AUDUSD"], "USDJPY": ["EURJPY", "GBPJPY"],
    "EURJPY": ["USDJPY", "GBPJPY"], "GBPJPY": ["USDJPY", "EURJPY"],
    "XAUUSD": ["XAGUSD"], "XAGUSD": ["XAUUSD"],
    "US30": ["US500", "US100"], "US500": ["US30", "US100"],
    "US100": ["US30", "US500"],
}

# Optimal session windows per instrument class (CET hours, inclusive).
_SESSION_WINDOWS: dict[str, list[tuple[int, int]]] = {
    "A": [(7, 11), (13, 17)],   # Forex: London 07-11, NY overlap 13-17
    "B": [(7, 17)],             # Commodities: London + NY
    "C": [(14, 21)],            # Indices: NY session
}

_BULL_ALIASES = ("bull", "long", "bullish", "demand")


def _check_order_block(
    direction: str, current_price: float, order_blocks: list[dict], atr: float,
) -> bool:
    """True if price is within 1x ATR of an unmitigated OB aligned with direction."""
    if not order_blocks or atr <= 0:
        return False
    is_bull = direction.lower() in _BULL_ALIASES
    for ob in order_blocks:
        if ob.get("mitigated"):
            continue
        ob_dir = ob.get("direction", ob.get("type", "")).lower()
        if (ob_dir in _BULL_ALIASES) != is_bull:
            continue
        ob_top = float(ob.get("top", ob.get("high", 0)))
        ob_bot = float(ob.get("bottom", ob.get("low", 0)))
        if ob_top == 0 and ob_bot == 0:
            continue
        if min(abs(current_price - ob_top), abs(current_price - ob_bot)) <= atr:
            return True
    return False


def _check_fvg(
    direction: str, current_price: float, fvgs: list[dict], atr: float,
) -> bool:
    """True if an unmitigated FVG midpoint is within 1x ATR, aligned with direction."""
    if not fvgs or atr <= 0:
        return False
    is_bull = direction.lower() in _BULL_ALIASES
    for fvg in fvgs:
        if fvg.get("mitigated"):
            continue
        fvg_dir = fvg.get("direction", fvg.get("type", "")).lower()
        if (fvg_dir in ("bull", "long", "bullish")) != is_bull:
            continue
        fvg_top = float(fvg.get("top", fvg.get("high", 0)))
        fvg_bot = float(fvg.get("bottom", fvg.get("low", 0)))
        if fvg_top == 0 and fvg_bot == 0:
            continue
        if abs(current_price - (fvg_top + fvg_bot) / 2) <= atr:
            return True
    return False


def _check_session_alignment(instrument_class: str, current_hour_cet: int) -> bool:
    """True if current CET hour is within the optimal session for this class.

    Unknown instrument class defaults to True (no penalty).
    """
    windows = _SESSION_WINDOWS.get(instrument_class.upper())
    if windows is None:
        return True
    return any(start <= current_hour_cet <= end for start, end in windows)


def _check_correlation_clear(instrument: str, open_signals: list[dict]) -> bool:
    """True if no correlated instrument has an active signal (conservative)."""
    correlated = _CORRELATION_MAP.get(instrument.upper(), [])
    if not correlated or not open_signals:
        return True
    for sig in open_signals:
        if sig.get("instrument", "").upper() in correlated and sig.get("direction"):
            return False
    return True


def calculate_confluence(inp: ScoringInput) -> ScoringResult:
    """Calculate the 16-criteria confluence score.

    Grade thresholds: A+ >= 14, A >= 12, B >= 8, C < 8.
    Timeframe bias: MAKRO (>=6+cot+htf), SWING (>=4+htf), SCALP (>=2+at_level), WATCHLIST.
    """
    ob_pass = _check_order_block(inp.direction, inp.current_price, inp.order_blocks, inp.atr)
    fvg_pass = _check_fvg(inp.direction, inp.current_price, inp.fvgs, inp.atr)
    session_pass = _check_session_alignment(inp.instrument_class, inp.current_hour_cet)
    corr_pass = _check_correlation_clear(inp.instrument, inp.open_signals)

    details: list[ScoreDetail] = [
        ScoreDetail(label="Over SMA200 (D1 trend)", passes=inp.above_sma200),
        ScoreDetail(label="Momentum 20d bekrefter", passes=inp.momentum_confirms),
        ScoreDetail(label="COT bekrefter retning", passes=inp.cot_confirms),
        ScoreDetail(label="COT sterk posisjonering (>10%)", passes=inp.cot_strong),
        ScoreDetail(label="Pris VED HTF-nivå nå", passes=inp.at_level_now),
        ScoreDetail(label="HTF-nivå D1/Ukentlig", passes=inp.htf_level_nearby),
        ScoreDetail(label="D1 + 4H trend kongruent", passes=inp.trend_congruent),
        ScoreDetail(label="Ingen event-risiko (4t)", passes=inp.no_event_risk),
        ScoreDetail(label="Nyhetssentiment bekrefter", passes=inp.news_confirms),
        ScoreDetail(label="Fundamental bekrefter", passes=inp.fund_confirms),
        ScoreDetail(label="BOS 1H/4H bekrefter retning", passes=inp.bos_confirms),
        ScoreDetail(label="SMC 1H struktur bekrefter", passes=inp.smc_struct_confirms),
        ScoreDetail(label="Ordre-blokk bekrefter", passes=ob_pass),
        ScoreDetail(label="FVG i nærheten", passes=fvg_pass),
        ScoreDetail(label="Riktig handelssesjon", passes=session_pass),
        ScoreDetail(label="Ingen korrelert konflikt", passes=corr_pass),
    ]

    score = sum(1 for d in details if d.passes)
    max_score = len(details)

    if score >= 14:
        grade = "A+"
    elif score >= 12:
        grade = "A"
    elif score >= 8:
        grade = "B"
    else:
        grade = "C"

    grade_color = "bull" if score >= 14 else "warn" if score >= 12 else "bear"

    if score >= 6 and inp.cot_confirms and inp.htf_level_nearby:
        timeframe_bias = "MAKRO"
    elif score >= 4 and inp.htf_level_nearby:
        timeframe_bias = "SWING"
    elif score >= 2 and inp.at_level_now:
        timeframe_bias = "SCALP"
    else:
        timeframe_bias = "WATCHLIST"

    return ScoringResult(
        score=score,
        max_score=max_score,
        grade=grade,
        grade_color=grade_color,
        timeframe_bias=timeframe_bias,
        details=details,
    )
