"""Tests for oil & gas intelligence scoring pure functions."""

from __future__ import annotations

import pytest

from src.trading.scrapers.oilgas_intel import (
    SegmentRisk,
    classify_overall_risk,
    combine_energy_signal,
    score_cot,
    score_energy_segments,
    score_price_signal,
)


# ── score_price_signal ───────────────────────────────────────────────────────


def test_price_bull():
    signal, score = score_price_signal(20.0)
    assert signal == "bull"
    assert score == 2


def test_price_bull_mild():
    signal, score = score_price_signal(8.0)
    assert signal == "bull-mild"
    assert score == 1


def test_price_neutral():
    signal, score = score_price_signal(2.0)
    assert signal == "neutral"
    assert score == 0


def test_price_bear_mild():
    signal, score = score_price_signal(-8.0)
    assert signal == "bear-mild"
    assert score == -1


def test_price_bear():
    signal, score = score_price_signal(-20.0)
    assert signal == "bear"
    assert score == -2


# ── score_cot ────────────────────────────────────────────────────────────────


def test_cot_strong_long():
    assert score_cot(20.0) == 2


def test_cot_neutral():
    assert score_cot(0.0) == 0


def test_cot_strong_short():
    assert score_cot(-20.0) == -2


# ── combine_energy_signal ────────────────────────────────────────────────────


def test_combine_sterkt_bullish():
    assert combine_energy_signal(2, 2) == "STERKT BULLISH"


def test_combine_bullish():
    assert combine_energy_signal(1, 0) == "BULLISH"


def test_combine_neutral():
    assert combine_energy_signal(0, 0) == "NØYTRAL"


def test_combine_bearish():
    assert combine_energy_signal(-1, 0) == "BEARISH"


def test_combine_sterkt_bearish():
    assert combine_energy_signal(-2, -2) == "STERKT BEARISH"


# ── score_energy_segments ────────────────────────────────────────────────────

_TEST_SEGMENTS = [
    {"id": "opec", "name": "OPEC", "keywords": ["opec", "saudi", "production cut"]},
    {"id": "lng", "name": "LNG", "keywords": ["lng", "henry hub"]},
]


def test_no_articles():
    results = score_energy_segments([], _TEST_SEGMENTS)
    assert all(s.risk == "LOW" for s in results)


def test_opec_high_risk():
    articles = [
        {"title": "OPEC production cut disruption Saudi embargo"},
        {"title": "Saudi Arabia announces OPEC+ cut"},
        {"title": "OPEC meeting crisis threat"},
    ]
    results = score_energy_segments(articles, _TEST_SEGMENTS)
    opec = next(s for s in results if s.segment_id == "opec")
    assert opec.risk_score >= 5
    assert opec.risk == "HIGH"


def test_medium_risk():
    articles = [
        {"title": "LNG prices surge at henry hub"},
    ]
    results = score_energy_segments(articles, _TEST_SEGMENTS)
    lng = next(s for s in results if s.segment_id == "lng")
    assert lng.risk_score >= 2
    assert lng.risk == "MEDIUM"


# ── classify_overall_risk ────────────────────────────────────────────────────


def test_overall_high():
    risks = [
        SegmentRisk("a", "A", "HIGH", 5, 2),
        SegmentRisk("b", "B", "HIGH", 6, 3),
    ]
    assert classify_overall_risk(risks) == "HIGH"


def test_overall_low():
    risks = [
        SegmentRisk("a", "A", "LOW", 0, 0),
    ]
    assert classify_overall_risk(risks) == "LOW"
