"""Confluence scoring — pure function, no side effects.

Extracted from v1 fetch_all.py lines 987-1014.
"""

from __future__ import annotations

from src.core.models import ScoreDetail, ScoringInput, ScoringResult


def calculate_confluence(inp: ScoringInput) -> ScoringResult:
    """Calculate the 12-criteria confluence score.

    Grade thresholds:
      A+  >= 11
      A   >= 9
      B   >= 6
      C   <  6

    Timeframe bias:
      MAKRO     — score >= 6 AND cot_confirms AND htf_level_nearby
      SWING     — score >= 4 AND htf_level_nearby
      SCALP     — score >= 2 AND at_level_now AND (session active — caller must
                   set at_level_now accordingly; the pure function trusts the flag)
      WATCHLIST — otherwise
    """
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
    ]

    score = sum(1 for d in details if d.passes)
    max_score = len(details)

    # Grade
    if score >= 11:
        grade = "A+"
    elif score >= 9:
        grade = "A"
    elif score >= 6:
        grade = "B"
    else:
        grade = "C"

    grade_color = "bull" if score >= 11 else "warn" if score >= 9 else "bear"

    # Timeframe bias
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
