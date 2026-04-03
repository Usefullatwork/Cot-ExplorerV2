"""NLP sentiment analysis for financial headlines.

Pure functions using stdlib only — no external NLP libraries.
Provides lexicon-based scoring, decay-weighted aggregation,
headline clustering, and per-instrument relevance filtering.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass
from typing import Sequence

# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class HeadlineSentiment:
    """Sentiment score for a single headline."""

    text: str
    score: float  # -1.0 (bearish) to +1.0 (bullish)
    relevance: float  # 0.0-1.0 (how relevant to financial markets)
    age_hours: float  # how old the headline is


@dataclass(frozen=True)
class SentimentCluster:
    """Group of related headlines."""

    theme: str  # dominant keyword/topic
    headlines: list[str]
    avg_score: float
    count: int


@dataclass(frozen=True)
class NLPSentiment:
    """Complete NLP sentiment analysis result."""

    instrument: str
    aggregate_score: float  # decay-weighted aggregate (-1 to +1)
    confidence: float  # 0-1 based on headline count and agreement
    bias: str  # "BULLISH", "BEARISH", "NEUTRAL"
    clusters: list[SentimentCluster]
    n_headlines: int
    decay_half_life_hours: float


# ---------------------------------------------------------------------------
# Financial sentiment lexicon
# ---------------------------------------------------------------------------

_POSITIVE_WORDS: dict[str, float] = {
    "rally": 0.8,
    "surge": 0.9,
    "gain": 0.6,
    "rise": 0.5,
    "jump": 0.7,
    "bull": 0.7,
    "bullish": 0.8,
    "recovery": 0.6,
    "growth": 0.5,
    "strong": 0.4,
    "upgrade": 0.7,
    "optimism": 0.6,
    "boom": 0.8,
    "profit": 0.5,
    "record": 0.4,
    "breakout": 0.7,
    "soar": 0.9,
    "rebound": 0.6,
    "outperform": 0.7,
    "beat": 0.5,
    "exceed": 0.5,
    "dovish": 0.6,
    "stimulus": 0.5,
    "easing": 0.5,
    "support": 0.3,
}

_NEGATIVE_WORDS: dict[str, float] = {
    "crash": -0.9,
    "plunge": -0.9,
    "drop": -0.6,
    "fall": -0.5,
    "decline": -0.5,
    "bear": -0.7,
    "bearish": -0.8,
    "recession": -0.8,
    "crisis": -0.9,
    "weak": -0.4,
    "downgrade": -0.7,
    "pessimism": -0.6,
    "bust": -0.8,
    "loss": -0.5,
    "selloff": -0.8,
    "sell-off": -0.8,
    "slump": -0.7,
    "collapse": -0.9,
    "underperform": -0.7,
    "miss": -0.5,
    "warning": -0.6,
    "hawkish": -0.5,
    "tightening": -0.4,
    "inflation": -0.3,
    "tariff": -0.5,
    "sanctions": -0.6,
    "war": -0.7,
    "conflict": -0.6,
    "default": -0.8,
}

# Merge into a single lookup for tokenizer
_LEXICON: dict[str, float] = {**_POSITIVE_WORDS, **_NEGATIVE_WORDS}

# ---------------------------------------------------------------------------
# Instrument-relevance keywords
# ---------------------------------------------------------------------------

_INSTRUMENT_KEYWORDS: dict[str, list[str]] = {
    "EURUSD": ["euro", "ecb", "eurozone", "eur/usd", "eurusd"],
    "USDJPY": ["yen", "boj", "japan", "usd/jpy", "usdjpy"],
    "GBPUSD": ["pound", "sterling", "boe", "gbp", "uk economy", "gbpusd"],
    "AUDUSD": ["aussie", "rba", "australia", "aud", "audusd"],
    "USDCHF": ["franc", "snb", "swiss", "switzerland", "usdchf"],
    "Gold": ["gold", "xau", "bullion", "precious metal"],
    "Silver": ["silver", "xag"],
    "Brent": ["brent", "crude", "oil", "opec", "petroleum"],
    "WTI": ["wti", "crude", "oil", "opec"],
    "NATGAS": ["natural gas", "natgas", "lng"],
    "WHEAT": ["wheat", "grain", "agriculture"],
    "CORN": ["corn", "grain", "agriculture"],
    "XPTUSD": ["platinum", "xpt"],
    "XPDUSD": ["palladium", "xpd"],
    "SPX": ["s&p", "sp500", "wall street", "stock market", "equities", "spx"],
    "NAS100": ["nasdaq", "tech stocks", "technology", "nas100"],
}

# Stopwords to exclude from clustering
_STOPWORDS: frozenset[str] = frozenset({
    "the", "and", "for", "that", "this", "with", "from", "have", "will",
    "been", "more", "than", "after", "about", "into", "over", "also",
    "says", "said", "could", "would", "their", "there", "what", "when",
    "which", "while", "other", "some", "them", "they", "were", "your",
    "most", "many", "much", "just", "like", "make", "made", "each",
    "does", "back", "even", "very", "only",
})

# Pre-compiled tokenizer pattern
_TOKEN_RE = re.compile(r"[a-z]+(?:-[a-z]+)*")


# ---------------------------------------------------------------------------
# Core functions
# ---------------------------------------------------------------------------


def _tokenize(text: str) -> list[str]:
    """Lowercase and extract alphabetic tokens (including hyphenated words)."""
    return _TOKEN_RE.findall(text.lower())


def score_headline(text: str) -> float:
    """Score a single headline using lexicon matching.

    Tokenize (lowercase, split on non-alpha), match against lexicon.
    Score = sum of matched word scores / max(1, count of matched words).
    Clamp to [-1.0, 1.0].
    """
    tokens = _tokenize(text)
    total = 0.0
    matches = 0

    for token in tokens:
        if token in _LEXICON:
            total += _LEXICON[token]
            matches += 1

    if matches == 0:
        return 0.0

    raw = total / matches
    return max(-1.0, min(1.0, raw))


def headline_relevance(text: str, instrument: str) -> float:
    """Compute relevance of headline to a specific instrument.

    Returns 0.0-1.0 based on keyword matches from _INSTRUMENT_KEYWORDS.
    Each matched keyword adds 0.5, capped at 1.0.
    """
    keywords = _INSTRUMENT_KEYWORDS.get(instrument, [])
    if not keywords:
        return 0.0

    lower_text = text.lower()
    hit_count = sum(1 for kw in keywords if kw in lower_text)

    if hit_count == 0:
        return 0.0

    return min(1.0, hit_count * 0.5)


def decay_weight(age_hours: float, half_life_hours: float = 24.0) -> float:
    """Exponential decay weight: w = 2^(-age/half_life).

    Returns value in (0, 1]. age_hours=0 returns 1.0.
    """
    if half_life_hours <= 0.0:
        return 0.0
    return math.pow(2.0, -age_hours / half_life_hours)


def decay_weighted_sentiment(
    headlines: Sequence[HeadlineSentiment],
    half_life_hours: float = 24.0,
) -> float:
    """Compute decay-weighted aggregate sentiment.

    aggregate = sum(score * relevance * decay_weight)
              / sum(relevance * decay_weight)

    If no relevant headlines (denominator is zero), return 0.0.
    """
    numerator = 0.0
    denominator = 0.0

    for h in headlines:
        w = decay_weight(h.age_hours, half_life_hours)
        weighted_relevance = h.relevance * w
        numerator += h.score * weighted_relevance
        denominator += weighted_relevance

    if denominator == 0.0:
        return 0.0

    return max(-1.0, min(1.0, numerator / denominator))


def _significant_words(text: str) -> set[str]:
    """Extract significant words (>4 chars, not stopwords) from text."""
    tokens = _tokenize(text)
    return {t for t in tokens if len(t) > 4 and t not in _STOPWORDS}


def _jaccard(a: set[str], b: set[str]) -> float:
    """Jaccard similarity between two sets."""
    if not a or not b:
        return 0.0
    intersection = len(a & b)
    union = len(a | b)
    return intersection / union if union > 0 else 0.0


def cluster_headlines(
    headlines: Sequence[str],
    min_cluster_size: int = 2,
) -> list[SentimentCluster]:
    """Group related headlines by shared keywords.

    1. Extract significant words (>4 chars, not stopwords) from each headline.
    2. For each pair: Jaccard similarity on word sets.
    3. Group headlines with similarity > 0.3 (greedy single-linkage).
    4. Theme = most common significant word in the cluster.

    Returns only clusters with size >= min_cluster_size.
    """
    n = len(headlines)
    if n < min_cluster_size:
        return []

    word_sets = [_significant_words(h) for h in headlines]

    # Greedy single-linkage clustering
    assigned: list[int] = [-1] * n  # cluster assignment, -1 = unassigned
    cluster_id = 0

    for i in range(n):
        if assigned[i] >= 0:
            continue
        # Start a new cluster with headline i
        assigned[i] = cluster_id
        for j in range(i + 1, n):
            if assigned[j] >= 0:
                continue
            # Check similarity against any member of current cluster
            for k in range(n):
                if assigned[k] != cluster_id:
                    continue
                if _jaccard(word_sets[j], word_sets[k]) > 0.3:
                    assigned[j] = cluster_id
                    break
        cluster_id += 1

    # Build cluster objects
    clusters: list[SentimentCluster] = []
    for cid in range(cluster_id):
        members = [i for i in range(n) if assigned[i] == cid]
        if len(members) < min_cluster_size:
            continue

        cluster_texts = [headlines[i] for i in members]

        # Theme = most common significant word across cluster members
        all_words: list[str] = []
        for i in members:
            all_words.extend(word_sets[i])

        if all_words:
            theme = Counter(all_words).most_common(1)[0][0]
        else:
            theme = "unknown"

        # Average score of cluster headlines
        scores = [score_headline(h) for h in cluster_texts]
        avg = math.fsum(scores) / len(scores) if scores else 0.0

        clusters.append(SentimentCluster(
            theme=theme,
            headlines=cluster_texts,
            avg_score=round(avg, 4),
            count=len(members),
        ))

    return clusters


def sentiment_score(
    instrument: str,
    headlines: Sequence[dict],
    half_life_hours: float = 24.0,
) -> NLPSentiment:
    """Complete NLP sentiment for an instrument.

    Args:
        instrument: Instrument name (e.g. "Gold", "EURUSD").
        headlines: List of {"text": str, "age_hours": float}.
        half_life_hours: Decay half-life for weighting recent headlines.

    Steps:
        1. Score each headline.
        2. Compute relevance to instrument.
        3. Build HeadlineSentiment objects.
        4. Compute decay-weighted aggregate.
        5. Cluster headlines.
        6. Classify bias: >0.2 BULLISH, <-0.2 BEARISH, else NEUTRAL.
        7. Confidence = min(1.0, n_relevant / 10) * (1 - std/2).
    """
    scored: list[HeadlineSentiment] = []
    texts: list[str] = []

    for h in headlines:
        text = h.get("text", "")
        age = float(h.get("age_hours", 0.0))
        s = score_headline(text)
        r = headline_relevance(text, instrument)
        scored.append(HeadlineSentiment(
            text=text, score=s, relevance=r, age_hours=age,
        ))
        texts.append(text)

    aggregate = decay_weighted_sentiment(scored, half_life_hours)
    clusters = cluster_headlines(texts)

    # Bias classification
    if aggregate > 0.2:
        bias = "BULLISH"
    elif aggregate < -0.2:
        bias = "BEARISH"
    else:
        bias = "NEUTRAL"

    # Confidence: based on relevant headline count and score agreement
    relevant = [h for h in scored if h.relevance > 0.0]
    n_relevant = len(relevant)
    count_factor = min(1.0, n_relevant / 10.0)

    if n_relevant >= 2:
        scores_list = [h.score for h in relevant]
        mean_s = math.fsum(scores_list) / len(scores_list)
        variance = math.fsum((s - mean_s) ** 2 for s in scores_list) / len(scores_list)
        std = math.sqrt(variance)
        agreement_factor = max(0.0, 1.0 - std / 2.0)
    else:
        agreement_factor = 0.5  # low confidence when few headlines

    confidence = round(count_factor * agreement_factor, 4)

    return NLPSentiment(
        instrument=instrument,
        aggregate_score=round(aggregate, 4),
        confidence=confidence,
        bias=bias,
        clusters=clusters,
        n_headlines=len(headlines),
        decay_half_life_hours=half_life_hours,
    )
