"""Geo-signal generator — pre-trade signals from classified geo-events.

Aggregates classified news articles into actionable ``GeoSignal`` objects
with affected instruments, directional bias, confidence, and expiry.

Pure functions, no side effects, no external deps beyond sibling modules.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone

from src.analysis.geo_classifier import (
    GeoEventType,
    classify_and_score,
)
from src.analysis.impact_mapper import TradeImpact, detect_region, map_event_to_trades


# ---------------------------------------------------------------------------
# Expiry rules (hours) per event type
# ---------------------------------------------------------------------------

EXPIRY_HOURS: dict[GeoEventType, int] = {
    GeoEventType.ARMED_CONFLICT: 72,
    GeoEventType.SANCTIONS: 168,
    GeoEventType.SUPPLY_DISRUPTION: 48,
    GeoEventType.MARITIME_THREAT: 24,
    GeoEventType.NATURAL_DISASTER: 48,
    GeoEventType.POLITICAL_CRISIS: 72,
    GeoEventType.TRADE_WAR: 168,
    GeoEventType.ENERGY_CRISIS: 72,
}


@dataclass
class GeoSignal:
    """A pre-trade signal derived from geopolitical events."""

    event_type: GeoEventType
    confidence: float                # 0.0 - 1.0
    impacts: list[TradeImpact]
    source_articles: list[dict]      # [{title, url, source}, ...]
    generated_at: str                # ISO 8601 UTC
    expires_hours: int


def _merge_impacts(impacts: list[TradeImpact]) -> list[TradeImpact]:
    """Deduplicate impacts by instrument+direction, keeping strongest."""
    strength_rank = {"strong": 3, "moderate": 2, "weak": 1}
    best: dict[tuple[str, str], TradeImpact] = {}

    for imp in impacts:
        key = (imp.instrument, imp.direction)
        existing = best.get(key)
        if existing is None:
            best[key] = imp
        else:
            if strength_rank.get(imp.strength, 0) > strength_rank.get(existing.strength, 0):
                best[key] = imp

    return list(best.values())


def generate_geo_signals(articles: list[dict]) -> list[GeoSignal]:
    """Generate pre-trade geo-signals from a list of news articles.

    Articles are classified, grouped by event type, and converted into
    ``GeoSignal`` objects.  Events with 2+ confirming articles get
    higher confidence.

    Args:
        articles: List of article dicts from ``intel_feed.fetch()``.
            Required keys: ``title``.  Optional: ``url``, ``source``.

    Returns:
        List of ``GeoSignal`` objects, sorted by confidence descending.
    """
    if not articles:
        return []

    # Step 1: Classify every article.
    classified: list[tuple[dict, list[tuple[GeoEventType, float]]]] = []
    for article in articles:
        title = article.get("title", "")
        source = article.get("source", "")
        results = classify_and_score(title, source)
        if results:
            classified.append((article, results))

    # Step 2: Group by event type.
    groups: dict[GeoEventType, list[tuple[dict, float]]] = defaultdict(list)
    for article, scored_types in classified:
        for event_type, confidence in scored_types:
            groups[event_type].append((article, confidence))

    # Step 3: Build signals.
    now = datetime.now(timezone.utc).isoformat()
    signals: list[GeoSignal] = []

    for event_type, article_scores in groups.items():
        article_count = len(article_scores)

        # Average confidence across articles.
        avg_confidence = sum(sc for _a, sc in article_scores) / article_count

        # Confirmation bonus: 2+ articles boost confidence.
        if article_count >= 3:
            avg_confidence = min(avg_confidence + 0.15, 1.0)
        elif article_count >= 2:
            avg_confidence = min(avg_confidence + 0.10, 1.0)
        else:
            # Single-article events get a penalty.
            avg_confidence *= 0.7

        avg_confidence = round(avg_confidence, 3)

        # Collect source article summaries.
        source_articles = [
            {
                "title": a.get("title", ""),
                "url": a.get("url", ""),
                "source": a.get("source", ""),
            }
            for a, _sc in article_scores
        ]

        # Build impact list from all articles' regions/keywords.
        all_impacts: list[TradeImpact] = []
        for article, _sc in article_scores:
            title = article.get("title", "")
            region = detect_region(title)
            keywords = title.split()
            impacts = map_event_to_trades(event_type, region=region, keywords=keywords)
            all_impacts.extend(impacts)

        merged_impacts = _merge_impacts(all_impacts)

        if not merged_impacts:
            continue

        signals.append(GeoSignal(
            event_type=event_type,
            confidence=avg_confidence,
            impacts=merged_impacts,
            source_articles=source_articles,
            generated_at=now,
            expires_hours=EXPIRY_HOURS.get(event_type, 48),
        ))

    # Sort by confidence descending.
    signals.sort(key=lambda s: s.confidence, reverse=True)
    return signals
