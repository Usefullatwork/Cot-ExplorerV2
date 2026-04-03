"""Integration tests for /api/v1/intelligence/* endpoints.

Verifies that wired endpoints return computed data (not hardcoded)
and handle empty-DB gracefully.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from src.db.models import (
    GeoIntelArticle,
    Instrument,
    PipelineState,
    PriceDaily,
)


# ── Helpers ──────────────────────────────────────────────────────────────────


def _seed_instruments(session):
    """Seed a minimal set of instruments for propagation tests."""
    for key in ("EURUSD", "GBPUSD", "Gold"):
        session.add(
            Instrument(
                key=key,
                name=key,
                symbol=f"{key}=X",
                label="Test",
                category="test",
                class_="A",
                session="London",
                active=True,
            )
        )
    session.commit()


def _seed_prices(session, instrument: str, n_days: int = 60):
    """Seed n_days of daily close prices with small random walk."""
    import math

    base = 1.1000 if instrument.startswith("EUR") else 1.3000
    if instrument == "Gold":
        base = 2000.0
    for i in range(n_days):
        date = (
            datetime.now(timezone.utc) - timedelta(days=n_days - i)
        ).strftime("%Y-%m-%d")
        # Deterministic pseudo-random walk
        change = math.sin(i * 0.5 + hash(instrument) % 100) * 0.005
        base *= 1.0 + change
        session.add(
            PriceDaily(
                instrument=instrument,
                date=date,
                high=base * 1.005,
                low=base * 0.995,
                close=base,
            )
        )
    session.commit()


def _seed_articles(session, n: int = 10):
    """Seed geo-intel articles for sentiment analysis."""
    now = datetime.now(timezone.utc)
    titles = [
        "Gold rally continues as dollar weakens",
        "ECB signals dovish rate path for eurozone",
        "Oil prices plunge on OPEC disagreement",
        "Strong US jobs data boosts USDJPY",
        "Silver surge follows gold breakout",
        "Bearish outlook for crude oil markets",
        "EURUSD gains on weak dollar sentiment",
        "Sterling decline accelerates on Brexit fears",
        "Gold bullion hits new record high",
        "Nasdaq tech stocks rally on earnings optimism",
    ]
    for i in range(min(n, len(titles))):
        session.add(
            GeoIntelArticle(
                title=titles[i],
                url=f"https://example.com/article-{i}",
                source="test",
                published_at=(now - timedelta(hours=i * 6)).isoformat(),
                category="gold" if "gold" in titles[i].lower() else "general",
                fetched_at=now - timedelta(hours=i * 6),
            )
        )
    session.commit()


# ── Sentiment ────────────────────────────────────────────────────────────────


async def test_sentiment_empty_db(app_client):
    """GET /sentiment returns scores with 0 sources when no articles exist."""
    r = await app_client.get("/api/v1/intelligence/sentiment")
    assert r.status_code == 200
    body = r.json()
    assert "scores" in body
    assert len(body["scores"]) == 14
    assert all(s["sources"] == 0 for s in body["scores"])
    assert body["is_live"] is False
    await app_client.aclose()


async def test_sentiment_with_articles(app_client, db_session):
    """GET /sentiment returns non-zero scores when articles exist."""
    _seed_articles(db_session)
    r = await app_client.get("/api/v1/intelligence/sentiment")
    assert r.status_code == 200
    body = r.json()
    assert body["is_live"] is True
    # Gold should have relevant sources (articles mention gold)
    gold = next(s for s in body["scores"] if s["instrument"] == "Gold")
    assert gold["sources"] > 0
    assert -1.0 <= gold["score"] <= 1.0
    await app_client.aclose()


async def test_sentiment_response_shape(app_client, db_session):
    """Response matches expected schema for all instruments."""
    _seed_articles(db_session)
    r = await app_client.get("/api/v1/intelligence/sentiment")
    body = r.json()
    assert "model" in body
    assert "timestamp" in body
    for s in body["scores"]:
        assert "instrument" in s
        assert "score" in s
        assert "label" in s
        assert "sources" in s
        assert s["label"] in ("bullish", "bearish", "neutral")
    await app_client.aclose()


# ── Propagation ──────────────────────────────────────────────────────────────


async def test_propagation_empty_db(app_client):
    """GET /propagation returns empty graph when no price data exists."""
    r = await app_client.get("/api/v1/intelligence/propagation")
    assert r.status_code == 200
    body = r.json()
    assert body["edges"] == []
    assert body["total_nodes"] == 0
    assert body["is_live"] is False
    await app_client.aclose()


async def test_propagation_with_prices(app_client, db_session):
    """GET /propagation returns edges when price data exists."""
    _seed_instruments(db_session)
    _seed_prices(db_session, "EURUSD", 60)
    _seed_prices(db_session, "GBPUSD", 60)
    _seed_prices(db_session, "Gold", 60)
    r = await app_client.get("/api/v1/intelligence/propagation")
    assert r.status_code == 200
    body = r.json()
    assert body["total_nodes"] >= 2
    assert body["is_live"] is True
    for edge in body["edges"]:
        assert "source" in edge
        assert "target" in edge
        assert "lag_hours" in edge
        assert "strength" in edge
        assert "direction" in edge
        assert edge["direction"] in ("direct", "inverse")
        assert 0 <= edge["strength"] <= 1.0
    await app_client.aclose()


# ── Attribution ──────────────────────────────────────────────────────────────


async def test_attribution_empty_db(app_client):
    """GET /attribution returns empty report when no trades exist."""
    r = await app_client.get("/api/v1/intelligence/attribution")
    assert r.status_code == 200
    body = r.json()
    assert body["total_trades"] == 0
    assert body["no_data"] is True
    assert body["is_live"] is True
    assert body["signal_pnl"] == []
    assert body["regime_performance"] == []
    await app_client.aclose()


async def test_attribution_response_shape(app_client):
    """Attribution response has all required sections."""
    r = await app_client.get("/api/v1/intelligence/attribution")
    body = r.json()
    assert "signal_pnl" in body
    assert "regime_performance" in body
    assert "sizing_alpha" in body
    assert "total_pnl_r" in body
    assert "total_trades" in body
    await app_client.aclose()


# ── Microstructure ───────────────────────────────────────────────────────────


async def test_microstructure_returns_all_instruments(app_client):
    """GET /microstructure returns liquidity for all 14 instruments."""
    r = await app_client.get("/api/v1/intelligence/microstructure")
    assert r.status_code == 200
    body = r.json()
    assert len(body["instruments"]) == 14
    assert body["is_live"] is True
    await app_client.aclose()


async def test_microstructure_response_shape(app_client):
    """Each instrument has correct fields and valid ranges."""
    r = await app_client.get("/api/v1/intelligence/microstructure")
    body = r.json()
    for item in body["instruments"]:
        assert "instrument" in item
        assert "liquidity_score" in item
        assert "spread_bps" in item
        assert "optimal_window" in item
        assert "depth_rank" in item
        assert 0.0 <= item["liquidity_score"] <= 1.0
        assert item["spread_bps"] > 0
        assert 1 <= item["depth_rank"] <= 14
    await app_client.aclose()


async def test_microstructure_ranking(app_client):
    """Depth ranks are unique and sequential (1 to 14)."""
    r = await app_client.get("/api/v1/intelligence/microstructure")
    body = r.json()
    ranks = [item["depth_rank"] for item in body["instruments"]]
    assert sorted(ranks) == list(range(1, 15))
    await app_client.aclose()
