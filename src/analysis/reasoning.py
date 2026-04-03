"""Trade reasoning engine — template-based narrative generation.

Pure function: takes scoring result + signal context, returns structured
reasoning with criteria breakdown and human-readable narrative.
No LLM calls — deterministic template output for audit trails.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from src.core.models import ScoringResult

# Map Norwegian criterion labels → English narrative fragments.
_CRITERIA_NARRATIVES: dict[str, tuple[str, str]] = {
    "Over SMA200 (D1 trend)": ("D1 trend above SMA200", "D1 trend below SMA200"),
    "Momentum 20d bekrefter": ("20d momentum confirms", "20d momentum diverges"),
    "COT bekrefter retning": ("COT net positioning confirms", "COT positioning opposes"),
    "COT sterk posisjonering (>10%)": ("COT strong positioning (>10%)", "COT weak positioning"),
    "Pris VED HTF-nivå nå": ("price at HTF level now", "price not at HTF level"),
    "Pris VED HTF-niva na": ("price at HTF level now", "price not at HTF level"),
    "HTF-nivå D1/Ukentlig": ("D1/Weekly HTF level nearby", "no HTF level nearby"),
    "HTF-niva D1/Ukentlig": ("D1/Weekly HTF level nearby", "no HTF level nearby"),
    "D1 + 4H trend kongruent": ("D1+4H trend congruent", "D1/4H trend divergence"),
    "Ingen event-risiko (4t)": ("no event risk within 4h", "event risk within 4h"),
    "Nyhetssentiment bekrefter": ("news sentiment confirms", "news sentiment opposes"),
    "Fundamental bekrefter": ("fundamentals confirm", "fundamentals oppose"),
    "BOS 1H/4H bekrefter retning": ("BOS 1H/4H confirms direction", "no BOS confirmation"),
    "SMC 1H struktur bekrefter": ("SMC 1H structure confirms", "SMC structure unclear"),
    "Ordre-blokk bekrefter": ("at unmitigated order block", "no order block nearby"),
    "FVG i nærheten": ("FVG nearby", "no FVG nearby"),
    "FVG i naerheten": ("FVG nearby", "no FVG nearby"),
    "Riktig handelssesjon": ("optimal trading session", "outside optimal session"),
    "Ingen korrelert konflikt": ("no correlated conflict", "correlated instrument open"),
    "COMEX stress bekrefter": ("COMEX stress confirms", "COMEX stress neutral"),
    "Ingen seismisk risiko": ("no seismic risk", "seismic risk detected"),
    "Chokepoint klar": ("chokepoint clear", "chokepoint disruption"),
}

# Direction label mapping.
_DIR_LABELS: dict[str, str] = {
    "bull": "Long", "bear": "Short",
    "bullish": "Long", "bearish": "Short",
    "long": "Long", "short": "Short",
}

# Grade → confidence label.
_GRADE_CONFIDENCE: dict[str, str] = {
    "A+": "very high", "A": "high", "B": "moderate", "C": "low",
}


@dataclass(frozen=True)
class CriterionReasoning:
    """Single criterion with pass/fail and narrative."""

    label: str
    passed: bool
    narrative: str


@dataclass(frozen=True)
class SignalReasoning:
    """Complete reasoning output for a scored signal."""

    instrument: str
    direction: str
    grade: str
    score: int
    max_score: int
    timeframe_bias: str
    confidence: str
    criteria_met: list[CriterionReasoning] = field(default_factory=list)
    criteria_missed: list[CriterionReasoning] = field(default_factory=list)
    narrative: str = ""
    strengths_summary: str = ""
    risks_summary: str = ""


def generate_reasoning(
    instrument: str,
    direction: str,
    scoring_result: ScoringResult,
    *,
    rsi_value: float | None = None,
    news_event: str | None = None,
) -> SignalReasoning:
    """Generate structured reasoning from a scoring result.

    Args:
        instrument: Instrument key (e.g. "EURUSD").
        direction: Signal direction ("bull" or "bear").
        scoring_result: Output of calculate_confluence().
        rsi_value: Optional current RSI for risk note.
        news_event: Optional upcoming news event name for risk note.

    Returns:
        SignalReasoning with criteria breakdown and narrative.
    """
    dir_label = _DIR_LABELS.get(direction.lower(), direction.upper())
    confidence = _GRADE_CONFIDENCE.get(scoring_result.grade, "unknown")

    criteria_met: list[CriterionReasoning] = []
    criteria_missed: list[CriterionReasoning] = []

    for detail in scoring_result.details:
        pass_text, fail_text = _CRITERIA_NARRATIVES.get(
            detail.label, (detail.label, f"not: {detail.label}"),
        )
        cr = CriterionReasoning(
            label=detail.label,
            passed=detail.passes,
            narrative=pass_text if detail.passes else fail_text,
        )
        if detail.passes:
            criteria_met.append(cr)
        else:
            criteria_missed.append(cr)

    # Build narrative
    strengths = [c.narrative for c in criteria_met]
    risks = [c.narrative for c in criteria_missed]

    # Add contextual risk notes
    if rsi_value is not None:
        if direction.lower() in ("bull", "long") and rsi_value >= 65:
            risks.append(f"RSI approaching overbought ({rsi_value:.0f})")
        elif direction.lower() in ("bear", "short") and rsi_value <= 35:
            risks.append(f"RSI approaching oversold ({rsi_value:.0f})")

    if news_event:
        risks.append(f"upcoming: {news_event}")

    strengths_str = ", ".join(strengths[:5]) if strengths else "none"
    risks_str = ", ".join(risks[:4]) if risks else "none"

    narrative = (
        f"{instrument} {dir_label} — {scoring_result.grade} grade "
        f"({scoring_result.score}/{scoring_result.max_score}). "
        f"Strengths: {strengths_str}. "
        f"Risks: {risks_str}. "
        f"Timeframe: {scoring_result.timeframe_bias}."
    )

    return SignalReasoning(
        instrument=instrument,
        direction=dir_label,
        grade=scoring_result.grade,
        score=scoring_result.score,
        max_score=scoring_result.max_score,
        timeframe_bias=scoring_result.timeframe_bias,
        confidence=confidence,
        criteria_met=criteria_met,
        criteria_missed=criteria_missed,
        narrative=narrative,
        strengths_summary=strengths_str,
        risks_summary=risks_str,
    )


def reasoning_to_dict(reasoning: SignalReasoning) -> dict:
    """Convert SignalReasoning to a JSON-serializable dict."""
    return {
        "instrument": reasoning.instrument,
        "direction": reasoning.direction,
        "grade": reasoning.grade,
        "score": reasoning.score,
        "max_score": reasoning.max_score,
        "timeframe_bias": reasoning.timeframe_bias,
        "confidence": reasoning.confidence,
        "narrative": reasoning.narrative,
        "strengths_summary": reasoning.strengths_summary,
        "risks_summary": reasoning.risks_summary,
        "criteria_met": [
            {"label": c.label, "passed": c.passed, "narrative": c.narrative}
            for c in reasoning.criteria_met
        ],
        "criteria_missed": [
            {"label": c.label, "passed": c.passed, "narrative": c.narrative}
            for c in reasoning.criteria_missed
        ],
    }
