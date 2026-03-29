"""Geo-event classifier — keyword-based event typing with confidence scoring.

Classifies news article titles into tradeable geopolitical event types using
weighted keyword matching.  Pure functions, no side effects, no external deps.
"""

from __future__ import annotations

from enum import Enum


class GeoEventType(str, Enum):
    """Tradeable geopolitical event categories."""

    ARMED_CONFLICT = "armed_conflict"
    SANCTIONS = "sanctions"
    SUPPLY_DISRUPTION = "supply_disruption"
    MARITIME_THREAT = "maritime_threat"
    NATURAL_DISASTER = "natural_disaster"
    POLITICAL_CRISIS = "political_crisis"
    TRADE_WAR = "trade_war"
    ENERGY_CRISIS = "energy_crisis"


# ---------------------------------------------------------------------------
# Keyword maps — each entry is (substring, weight).
# Weights: 3 = strong signal, 2 = moderate, 1 = weak/ambiguous.
# Substrings are lowercased; partial matching (e.g. "escalat" matches
# "escalation", "escalating").
# ---------------------------------------------------------------------------

EVENT_KEYWORDS: dict[GeoEventType, list[tuple[str, int]]] = {
    GeoEventType.ARMED_CONFLICT: [
        ("war ", 3), ("warfare", 3), ("military", 2), ("strike", 1),
        ("airstrike", 3), ("bomb", 2), ("missile", 3), ("troops", 2),
        ("invasion", 3), ("invade", 3), ("escalat", 2), ("conflict", 2),
        ("attack", 2), ("offensive", 2), ("deploy", 1), ("ceasefire", 2),
        ("artillery", 3), ("frontline", 2), ("casualties", 2), ("nato", 1),
        ("drone strike", 3), ("shelling", 3),
    ],
    GeoEventType.SANCTIONS: [
        ("sanction", 3), ("embargo", 3), ("freeze", 2), ("ban ", 2),
        ("restrict", 2), ("blacklist", 3), ("ofac", 3), ("penalt", 2),
        ("designation", 1), ("asset freeze", 3), ("export control", 2),
        ("secondary sanction", 3), ("financial restrict", 2),
        ("trade ban", 3), ("import ban", 3),
    ],
    GeoEventType.SUPPLY_DISRUPTION: [
        ("shutdown", 3), ("halt", 2), ("suspend", 2), ("disrupt", 3),
        ("outage", 3), ("shortage", 3), ("closure", 2), ("strike ", 1),
        ("walkout", 2), ("force majeure", 3), ("production cut", 3),
        ("maintenance", 1), ("idle", 1), ("curtail", 2), ("offline", 2),
        ("mine closur", 3), ("refinery", 2), ("smelter", 2),
    ],
    GeoEventType.MARITIME_THREAT: [
        ("strait", 2), ("blockade", 3), ("seize", 2), ("tanker", 2),
        ("navy", 1), ("piracy", 3), ("detained", 2), ("houthi", 3),
        ("shipping", 1), ("maritime", 2), ("chokepoint", 3), ("convoy", 2),
        ("vessel seized", 3), ("red sea", 2), ("hormuz", 3), ("suez", 2),
        ("malacca", 2), ("bab el-mandeb", 3), ("bosphor", 2),
        ("naval", 2), ("warship", 2),
    ],
    GeoEventType.NATURAL_DISASTER: [
        ("earthquake", 3), ("flood", 2), ("hurricane", 3), ("typhoon", 3),
        ("wildfire", 2), ("drought", 2), ("tsunami", 3), ("volcano", 2),
        ("landslide", 2), ("cyclone", 3), ("storm", 1), ("devastat", 2),
        ("natural disaster", 3), ("evacuate", 1), ("seismic", 2),
    ],
    GeoEventType.POLITICAL_CRISIS: [
        ("coup", 3), ("protest", 2), ("resign", 2), ("impeach", 3),
        ("overthrow", 3), ("unrest", 3), ("martial law", 3), ("riot", 2),
        ("revolution", 3), ("election crisis", 3), ("contested", 1),
        ("political crisis", 3), ("instability", 2), ("dissolve parliament", 3),
        ("state of emergency", 3), ("assassination", 3),
    ],
    GeoEventType.TRADE_WAR: [
        ("tariff", 3), ("export ban", 3), ("trade war", 3), ("retaliatory", 3),
        ("duties", 2), ("quota", 2), ("trade restrict", 2), ("countervailing", 2),
        ("anti-dumping", 2), ("trade dispute", 2), ("trade tension", 2),
        ("import duty", 2), ("reciprocal", 1), ("protectionist", 2),
        ("trade barrier", 2), ("decoupl", 2),
    ],
    GeoEventType.ENERGY_CRISIS: [
        ("gas shutoff", 3), ("pipeline", 2), ("opec", 2), ("opec+", 3),
        ("production cut", 2), ("blackout", 3), ("rationing", 3),
        ("lng", 1), ("energy crisis", 3), ("power outage", 3),
        ("gas crisis", 3), ("oil cut", 3), ("supply cut", 2),
        ("energy shortage", 3), ("grid failure", 3), ("fuel shortage", 3),
        ("gas curtail", 3), ("nord stream", 2),
    ],
}


# Credible sources that boost confidence.
_CREDIBLE_SOURCES: set[str] = {
    "reuters", "bloomberg", "ap", "bbc", "financial times", "ft",
    "wall street journal", "wsj", "cnbc", "economist", "al jazeera",
    "associated press", "nytimes", "new york times", "guardian",
}

_SOURCE_BOOST: float = 0.15


def classify_event(title: str, source: str = "") -> list[GeoEventType]:
    """Classify a news headline into zero or more geo-event types.

    Args:
        title: Article headline (case-insensitive matching).
        source: Publisher name (optional, not used for classification).

    Returns:
        List of matching ``GeoEventType`` values.  May be empty.
    """
    title_lower = title.lower()
    matches: list[GeoEventType] = []

    for event_type, keywords in EVENT_KEYWORDS.items():
        if any(kw in title_lower for kw, _weight in keywords):
            matches.append(event_type)

    return matches


def score_event(title: str, event_type: GeoEventType, source: str = "") -> float:
    """Score confidence that *title* belongs to *event_type*.

    Confidence is based on the number and weight of matching keywords,
    normalized to 0.0-1.0, with a boost for credible sources.

    Args:
        title: Article headline.
        event_type: The event type to score against.
        source: Publisher name (optional).

    Returns:
        Confidence float in [0.0, 1.0].
    """
    title_lower = title.lower()
    keywords = EVENT_KEYWORDS.get(event_type, [])

    if not keywords:
        return 0.0

    total_weight = 0
    max_possible = sum(w for _kw, w in keywords)

    for kw, weight in keywords:
        if kw in title_lower:
            total_weight += weight

    if total_weight == 0:
        return 0.0

    # Normalize: a single strong keyword (weight 3) gives ~0.3 base,
    # multiple matches push higher.  Cap raw at 0.85 before source boost.
    raw = min(total_weight / max(max_possible * 0.4, 1), 0.85)

    # Source credibility boost.
    if source:
        source_lower = source.lower()
        if any(cs in source_lower for cs in _CREDIBLE_SOURCES):
            raw = min(raw + _SOURCE_BOOST, 1.0)

    return round(raw, 3)


def classify_and_score(
    title: str, source: str = "",
) -> list[tuple[GeoEventType, float]]:
    """Classify a headline and return (event_type, confidence) pairs.

    Convenience wrapper combining ``classify_event`` and ``score_event``.

    Args:
        title: Article headline.
        source: Publisher name (optional).

    Returns:
        List of (GeoEventType, confidence) tuples, sorted by confidence desc.
    """
    event_types = classify_event(title, source)
    scored = [(et, score_event(title, et, source)) for et in event_types]
    scored.sort(key=lambda x: x[1], reverse=True)
    return scored
