"""Tests for the trade reasoning engine."""

import pytest

from src.analysis.reasoning import (
    CriterionReasoning,
    SignalReasoning,
    generate_reasoning,
    reasoning_to_dict,
)
from src.core.models import ScoreDetail, ScoringResult


# ── Fixtures ──────────────────────────────────────────────────────────────────


def _make_scoring_result(
    score: int = 15,
    grade: str = "A",
    passes: list[bool] | None = None,
) -> ScoringResult:
    """Build a ScoringResult with the given score and detail pattern."""
    labels = [
        "Over SMA200 (D1 trend)",
        "Momentum 20d bekrefter",
        "COT bekrefter retning",
        "COT sterk posisjonering (>10%)",
        "Pris VED HTF-nivå nå",
        "HTF-nivå D1/Ukentlig",
        "D1 + 4H trend kongruent",
        "Ingen event-risiko (4t)",
        "Nyhetssentiment bekrefter",
        "Fundamental bekrefter",
        "BOS 1H/4H bekrefter retning",
        "SMC 1H struktur bekrefter",
        "Ordre-blokk bekrefter",
        "FVG i nærheten",
        "Riktig handelssesjon",
        "Ingen korrelert konflikt",
        "COMEX stress bekrefter",
        "Ingen seismisk risiko",
        "Chokepoint klar",
    ]
    if passes is None:
        passes = [True] * score + [False] * (19 - score)
    details = [ScoreDetail(label=l, passes=p) for l, p in zip(labels, passes)]
    return ScoringResult(
        score=score,
        max_score=19,
        grade=grade,
        grade_color="bull" if grade == "A+" else "warn",
        timeframe_bias="SWING",
        details=details,
    )


# ── Unit tests ────────────────────────────────────────────────────────────────


class TestGenerateReasoning:
    """Test reasoning generation for various signal profiles."""

    def test_high_score_a_plus(self):
        result = _make_scoring_result(score=17, grade="A+")
        reasoning = generate_reasoning("EURUSD", "bull", result)

        assert reasoning.instrument == "EURUSD"
        assert reasoning.direction == "Long"
        assert reasoning.grade == "A+"
        assert reasoning.score == 17
        assert reasoning.max_score == 19
        assert reasoning.confidence == "very high"
        assert reasoning.timeframe_bias == "SWING"
        assert len(reasoning.criteria_met) == 17
        assert len(reasoning.criteria_missed) == 2
        assert "EURUSD Long" in reasoning.narrative
        assert "A+ grade" in reasoning.narrative
        assert "17/19" in reasoning.narrative

    def test_low_score_c_grade(self):
        result = _make_scoring_result(score=5, grade="C")
        reasoning = generate_reasoning("XAUUSD", "bear", result)

        assert reasoning.direction == "Short"
        assert reasoning.grade == "C"
        assert reasoning.confidence == "low"
        assert len(reasoning.criteria_met) == 5
        assert len(reasoning.criteria_missed) == 14
        assert "XAUUSD Short" in reasoning.narrative

    def test_b_grade_moderate(self):
        result = _make_scoring_result(score=11, grade="B")
        reasoning = generate_reasoning("GBPUSD", "bull", result)

        assert reasoning.confidence == "moderate"
        assert len(reasoning.criteria_met) == 11

    def test_zero_score(self):
        result = _make_scoring_result(score=0, grade="C")
        reasoning = generate_reasoning("USDJPY", "bear", result)

        assert reasoning.score == 0
        assert len(reasoning.criteria_met) == 0
        assert len(reasoning.criteria_missed) == 19
        assert "none" in reasoning.strengths_summary

    def test_perfect_score(self):
        result = _make_scoring_result(score=19, grade="A+")
        reasoning = generate_reasoning("EURUSD", "bull", result)

        assert reasoning.score == 19
        assert len(reasoning.criteria_met) == 19
        assert len(reasoning.criteria_missed) == 0
        assert "none" in reasoning.risks_summary

    def test_rsi_overbought_risk(self):
        # Use perfect score so no missed criteria compete with RSI in the summary
        result = _make_scoring_result(score=19, grade="A+")
        reasoning = generate_reasoning("EURUSD", "bull", result, rsi_value=72.0)

        assert "RSI approaching overbought (72)" in reasoning.risks_summary

    def test_rsi_oversold_risk(self):
        result = _make_scoring_result(score=19, grade="A+")
        reasoning = generate_reasoning("EURUSD", "bear", result, rsi_value=28.0)

        assert "RSI approaching oversold (28)" in reasoning.risks_summary

    def test_rsi_normal_no_extra_risk(self):
        result = _make_scoring_result(score=19, grade="A+")
        reasoning = generate_reasoning("EURUSD", "bull", result, rsi_value=50.0)

        assert "RSI" not in reasoning.risks_summary

    def test_news_event_risk(self):
        result = _make_scoring_result(score=19, grade="A+")
        reasoning = generate_reasoning(
            "EURUSD", "bull", result, news_event="NFP in 2h",
        )

        assert "upcoming: NFP in 2h" in reasoning.risks_summary

    def test_direction_aliases(self):
        result = _make_scoring_result(score=10, grade="B")

        for alias in ("bull", "long", "bullish"):
            r = generate_reasoning("EURUSD", alias, result)
            assert r.direction == "Long"

        for alias in ("bear", "short", "bearish"):
            r = generate_reasoning("EURUSD", alias, result)
            assert r.direction == "Short"

    def test_criteria_narratives_english(self):
        """Ensure Norwegian labels are mapped to English narratives."""
        result = _make_scoring_result(score=3, grade="C")
        reasoning = generate_reasoning("EURUSD", "bull", result)

        # First 3 criteria pass
        narratives = [c.narrative for c in reasoning.criteria_met]
        assert "D1 trend above SMA200" in narratives
        assert "20d momentum confirms" in narratives
        assert "COT net positioning confirms" in narratives


class TestReasoningToDict:
    """Test serialization to JSON-compatible dict."""

    def test_round_trip(self):
        result = _make_scoring_result(score=14, grade="A")
        reasoning = generate_reasoning("EURUSD", "bull", result)
        d = reasoning_to_dict(reasoning)

        assert d["instrument"] == "EURUSD"
        assert d["direction"] == "Long"
        assert d["grade"] == "A"
        assert d["score"] == 14
        assert d["max_score"] == 19
        assert d["confidence"] == "high"
        assert isinstance(d["criteria_met"], list)
        assert isinstance(d["criteria_missed"], list)
        assert len(d["criteria_met"]) == 14
        assert len(d["criteria_missed"]) == 5
        assert isinstance(d["narrative"], str)

    def test_dict_keys(self):
        result = _make_scoring_result(score=10, grade="B")
        reasoning = generate_reasoning("Gold", "bull", result)
        d = reasoning_to_dict(reasoning)

        expected_keys = {
            "instrument", "direction", "grade", "score", "max_score",
            "timeframe_bias", "confidence", "narrative",
            "strengths_summary", "risks_summary",
            "criteria_met", "criteria_missed",
        }
        assert set(d.keys()) == expected_keys

    def test_criterion_dict_shape(self):
        result = _make_scoring_result(score=1, grade="C")
        reasoning = generate_reasoning("EURUSD", "bull", result)
        d = reasoning_to_dict(reasoning)

        for c in d["criteria_met"]:
            assert "label" in c
            assert "passed" in c
            assert "narrative" in c
            assert c["passed"] is True

        for c in d["criteria_missed"]:
            assert c["passed"] is False
