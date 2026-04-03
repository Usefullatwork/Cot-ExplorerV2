"""Unit tests for src.analysis.nlp_sentiment — lexicon-based NLP sentiment."""

from __future__ import annotations

import math

from src.analysis.nlp_sentiment import (
    HeadlineSentiment,
    SentimentCluster,
    cluster_headlines,
    decay_weight,
    decay_weighted_sentiment,
    headline_relevance,
    score_headline,
    sentiment_score,
)


# ===== score_headline() =====================================================


class TestScoreHeadline:
    """Lexicon-based headline scoring."""

    def test_positive_headline(self):
        """Headline with rally/record keywords scores positive."""
        score = score_headline("Gold rallies to record high")
        assert score > 0.0

    def test_negative_headline(self):
        """Headline with crash/recession keywords scores negative."""
        score = score_headline("Markets crash on recession fears")
        assert score < 0.0

    def test_neutral_headline(self):
        """Headline with no financial keywords scores 0.0."""
        score = score_headline("Weather forecast for tomorrow is sunny")
        assert score == 0.0

    def test_mixed_headline(self):
        """Headline with both positive and negative words returns average."""
        score = score_headline("Recovery amid crisis expectations")
        # recovery (+0.6) and crisis (-0.9) -> average
        assert -1.0 <= score <= 1.0

    def test_clamped_to_range(self):
        """Score is always in [-1.0, 1.0]."""
        score = score_headline("surge soar rally boom breakout")
        assert -1.0 <= score <= 1.0

    def test_empty_string_returns_zero(self):
        """Empty headline returns 0.0."""
        assert score_headline("") == 0.0

    def test_case_insensitive(self):
        """Scoring is case-insensitive."""
        lower = score_headline("rally in gold")
        upper = score_headline("RALLY IN GOLD")
        assert lower == upper

    def test_hyphenated_word(self):
        """Sell-off is recognized as negative."""
        score = score_headline("Major sell-off hits markets")
        assert score < 0.0


# ===== headline_relevance() =================================================


class TestHeadlineRelevance:
    """Instrument-headline relevance matching."""

    def test_gold_headline_gold_instrument(self):
        """Gold headline has high relevance for Gold instrument."""
        rel = headline_relevance("Gold prices surge to new high", "Gold")
        assert rel > 0.0

    def test_unrelated_headline(self):
        """Tech headline has zero relevance for Gold."""
        rel = headline_relevance("Tech stocks lead Nasdaq rally", "Gold")
        assert rel == 0.0

    def test_multiple_keyword_hits(self):
        """Multiple keyword matches increase relevance up to 1.0."""
        rel = headline_relevance("ECB eurozone euro policy shift", "EURUSD")
        assert rel >= 0.5

    def test_unknown_instrument(self):
        """Unknown instrument returns 0.0."""
        rel = headline_relevance("Some headline", "UNKNOWN_INST")
        assert rel == 0.0

    def test_case_insensitive(self):
        """Keyword matching is case-insensitive."""
        rel = headline_relevance("GOLD BULLION PRICES", "Gold")
        assert rel > 0.0

    def test_oil_headline_brent(self):
        """Oil headline is relevant to Brent."""
        rel = headline_relevance("OPEC cuts oil production", "Brent")
        assert rel > 0.0


# ===== decay_weight() =======================================================


class TestDecayWeight:
    """Exponential time-decay weighting."""

    def test_zero_age_returns_one(self):
        """Brand-new headline (0 hours) has weight 1.0."""
        assert decay_weight(0.0) == 1.0

    def test_half_life_returns_half(self):
        """Headline at exactly half-life age has weight 0.5."""
        w = decay_weight(24.0, half_life_hours=24.0)
        assert abs(w - 0.5) < 1e-10

    def test_two_half_lives(self):
        """Headline at 2x half-life has weight 0.25."""
        w = decay_weight(48.0, half_life_hours=24.0)
        assert abs(w - 0.25) < 1e-10

    def test_monotonically_decreasing(self):
        """Older headlines have lower weight."""
        w1 = decay_weight(1.0)
        w6 = decay_weight(6.0)
        w24 = decay_weight(24.0)
        assert w1 > w6 > w24 > 0.0

    def test_zero_half_life_returns_zero(self):
        """Zero half-life returns 0.0 (guard against division by zero)."""
        assert decay_weight(10.0, half_life_hours=0.0) == 0.0


# ===== decay_weighted_sentiment() ==========================================


class TestDecayWeightedSentiment:
    """Decay-weighted aggregate sentiment computation."""

    def test_recent_positive_old_negative(self):
        """Recent positive + old negative -> aggregate > 0."""
        headlines = [
            HeadlineSentiment(text="rally", score=0.8, relevance=1.0, age_hours=1.0),
            HeadlineSentiment(text="crash", score=-0.8, relevance=1.0, age_hours=72.0),
        ]
        agg = decay_weighted_sentiment(headlines, half_life_hours=24.0)
        assert agg > 0.0

    def test_all_negative(self):
        """All negative headlines produce negative aggregate."""
        headlines = [
            HeadlineSentiment(text="crash", score=-0.9, relevance=1.0, age_hours=2.0),
            HeadlineSentiment(text="plunge", score=-0.8, relevance=1.0, age_hours=4.0),
        ]
        agg = decay_weighted_sentiment(headlines, half_life_hours=24.0)
        assert agg < 0.0

    def test_zero_relevance_ignored(self):
        """Headlines with zero relevance don't affect aggregate."""
        headlines = [
            HeadlineSentiment(text="crash", score=-0.9, relevance=0.0, age_hours=1.0),
            HeadlineSentiment(text="rally", score=0.8, relevance=1.0, age_hours=1.0),
        ]
        agg = decay_weighted_sentiment(headlines, half_life_hours=24.0)
        # Only the positive headline counts
        assert agg > 0.0

    def test_empty_headlines_returns_zero(self):
        """No headlines returns 0.0."""
        assert decay_weighted_sentiment([], half_life_hours=24.0) == 0.0

    def test_clamped_to_range(self):
        """Aggregate is always in [-1.0, 1.0]."""
        headlines = [
            HeadlineSentiment(text="x", score=1.0, relevance=1.0, age_hours=0.0),
        ]
        agg = decay_weighted_sentiment(headlines)
        assert -1.0 <= agg <= 1.0


# ===== cluster_headlines() ==================================================


class TestClusterHeadlines:
    """Headline clustering by shared keywords."""

    def test_similar_headlines_grouped(self):
        """Headlines about the same topic cluster together."""
        headlines = [
            "Gold prices surge higher after record breaking rally continues",
            "Gold prices continue record breaking surge amid strong demand",
            "Nasdaq technology earnings report beats expectations today",
        ]
        clusters = cluster_headlines(headlines, min_cluster_size=2)
        # Gold headlines share many significant words and should cluster
        assert len(clusters) >= 1
        assert clusters[0].count >= 2

    def test_all_different_no_clusters(self):
        """Completely different headlines produce no clusters."""
        headlines = [
            "Weather report for Tuesday",
            "Basketball finals tonight at arena",
            "New restaurant opens downtown center",
        ]
        clusters = cluster_headlines(headlines, min_cluster_size=2)
        assert len(clusters) == 0

    def test_empty_headlines(self):
        """Empty list returns no clusters."""
        assert cluster_headlines([], min_cluster_size=2) == []

    def test_single_headline_no_cluster(self):
        """Single headline cannot form a cluster."""
        assert cluster_headlines(["Gold surges"], min_cluster_size=2) == []

    def test_cluster_has_theme(self):
        """Each cluster has a non-empty theme string."""
        headlines = [
            "Oil prices crash after OPEC meeting fails",
            "OPEC meeting failure causes oil price crash",
        ]
        clusters = cluster_headlines(headlines, min_cluster_size=2)
        for c in clusters:
            assert len(c.theme) > 0


# ===== sentiment_score() (integration) =====================================


class TestSentimentScore:
    """Full NLP sentiment pipeline integration test."""

    def test_bullish_headlines(self):
        """Predominantly bullish headlines produce BULLISH bias."""
        headlines = [
            {"text": "Gold rallies to record high on dovish Fed", "age_hours": 2.0},
            {"text": "Bullion surge continues as gold demand soars", "age_hours": 4.0},
            {"text": "Gold breaks out amid strong precious metal bid", "age_hours": 6.0},
        ]
        result = sentiment_score("Gold", headlines)
        assert result.bias == "BULLISH"
        assert result.aggregate_score > 0.2
        assert result.n_headlines == 3
        assert result.instrument == "Gold"

    def test_bearish_headlines(self):
        """Predominantly bearish headlines produce BEARISH bias."""
        headlines = [
            {"text": "Markets crash on recession fears worldwide", "age_hours": 1.0},
            {"text": "S&P 500 plunges in worst selloff this year", "age_hours": 2.0},
            {"text": "Wall Street collapse deepens crisis", "age_hours": 3.0},
        ]
        result = sentiment_score("SPX", headlines)
        assert result.bias == "BEARISH"
        assert result.aggregate_score < -0.2

    def test_empty_headlines_neutral(self):
        """No headlines produce NEUTRAL with zero confidence."""
        result = sentiment_score("Gold", [])
        assert result.bias == "NEUTRAL"
        assert result.aggregate_score == 0.0
        assert result.confidence == 0.0

    def test_no_relevant_headlines(self):
        """Headlines unrelated to instrument produce NEUTRAL."""
        headlines = [
            {"text": "Nasdaq tech stocks lead the rally", "age_hours": 1.0},
            {"text": "Tesla reports record quarterly profit", "age_hours": 2.0},
        ]
        result = sentiment_score("Gold", headlines)
        assert result.bias == "NEUTRAL"

    def test_confidence_increases_with_count(self):
        """More relevant headlines increase confidence."""
        few = [
            {"text": "Gold rallies higher", "age_hours": 1.0},
        ]
        many = [
            {"text": f"Gold surges to {i}-year high", "age_hours": float(i)}
            for i in range(1, 11)
        ]
        result_few = sentiment_score("Gold", few)
        result_many = sentiment_score("Gold", many)
        assert result_many.confidence >= result_few.confidence

    def test_decay_half_life_passed_through(self):
        """Custom half-life is reflected in result."""
        result = sentiment_score("Gold", [], half_life_hours=12.0)
        assert result.decay_half_life_hours == 12.0
