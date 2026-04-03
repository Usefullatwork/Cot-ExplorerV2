"""Tests for shipping intelligence scoring pure functions."""

from __future__ import annotations

from src.trading.scrapers.shipping_intel import (
    RouteRisk,
    classify_overall_risk,
    score_index_signal,
    score_route_risks,
)

# ── score_route_risks ────────────────────────────────────────────────────────

_TEST_ROUTES = [
    {"id": "hormuz", "name": "Hormuz", "keywords": ["hormuz", "persian gulf"]},
    {"id": "suez", "name": "Suez", "keywords": ["suez", "red sea"]},
]


def test_no_articles():
    results = score_route_risks([], _TEST_ROUTES)
    assert all(r.risk == "LOW" for r in results)
    assert all(r.risk_score == 0 for r in results)


def test_matching_articles():
    articles = [
        {"title": "Hormuz strait tension escalates with disruption warning"},
        {"title": "Hormuz attack threat alert issued"},
    ]
    results = score_route_risks(articles, _TEST_ROUTES)
    hormuz = next(r for r in results if r.route_id == "hormuz")
    assert hormuz.risk_score >= 5  # 2 articles + disruption words
    assert hormuz.risk == "HIGH"


def test_medium_risk():
    articles = [
        {"title": "Suez canal congestion delays reported"},
    ]
    results = score_route_risks(articles, _TEST_ROUTES)
    suez = next(r for r in results if r.route_id == "suez")
    assert suez.risk_score >= 2
    assert suez.risk == "MEDIUM"


def test_no_matching_keywords():
    articles = [
        {"title": "Apple stock reaches new high"},
    ]
    results = score_route_risks(articles, _TEST_ROUTES)
    assert all(r.risk == "LOW" for r in results)


def test_sorted_by_risk_score():
    articles = [
        {"title": "Hormuz disruption attack threat"},
        {"title": "Hormuz conflict warning"},
    ]
    results = score_route_risks(articles, _TEST_ROUTES)
    assert results[0].route_id == "hormuz"


# ── classify_overall_risk ────────────────────────────────────────────────────


def test_overall_high():
    risks = [
        RouteRisk("a", "A", "HIGH", 5, 2),
        RouteRisk("b", "B", "HIGH", 6, 3),
    ]
    assert classify_overall_risk(risks) == "HIGH"


def test_overall_medium():
    risks = [
        RouteRisk("a", "A", "MEDIUM", 3, 1),
        RouteRisk("b", "B", "MEDIUM", 2, 1),
        RouteRisk("c", "C", "MEDIUM", 2, 1),
    ]
    assert classify_overall_risk(risks) == "MEDIUM"


def test_overall_low():
    risks = [
        RouteRisk("a", "A", "LOW", 0, 0),
        RouteRisk("b", "B", "LOW", 1, 0),
    ]
    assert classify_overall_risk(risks) == "LOW"


# ── score_index_signal ───────────────────────────────────────────────────────


def test_bull_signal():
    assert score_index_signal(20.0) == "bull"


def test_bear_signal():
    assert score_index_signal(-20.0) == "bear"


def test_neutral_signal():
    assert score_index_signal(5.0) == "neutral"
