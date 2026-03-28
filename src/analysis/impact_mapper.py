"""Impact mapper — maps geo-events to affected instruments with directional bias.

Given a classified geopolitical event (and optional region/keyword context),
returns a list of ``TradeImpact`` objects describing which instruments are
affected, the expected direction, strength, and a one-line reasoning.

Pure functions, no side effects, no external deps.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.analysis.geo_classifier import GeoEventType


@dataclass(frozen=True)
class TradeImpact:
    """A single instrument impact from a geopolitical event."""

    instrument: str
    direction: str   # "bull" or "bear"
    strength: str    # "strong", "moderate", "weak"
    reasoning: str


# ---------------------------------------------------------------------------
# Region detection — country/keyword -> region string
# ---------------------------------------------------------------------------

_COUNTRY_TO_REGION: dict[str, str] = {
    # Middle East / Eastern Europe
    "russia": "eastern_europe", "ukraine": "eastern_europe",
    "iran": "middle_east", "iraq": "middle_east", "syria": "middle_east",
    "yemen": "middle_east", "saudi": "middle_east", "qatar": "middle_east",
    "kuwait": "middle_east", "uae": "middle_east", "libya": "africa",
    "israel": "middle_east", "lebanon": "middle_east", "palestine": "middle_east",
    # Asia-Pacific
    "china": "asia_pacific", "taiwan": "asia_pacific", "japan": "asia_pacific",
    "korea": "asia_pacific", "philippines": "asia_pacific",
    "india": "asia_pacific", "myanmar": "asia_pacific",
    # Latin America
    "venezuela": "latin_america", "brazil": "latin_america",
    "argentina": "latin_america", "chile": "latin_america",
    "peru": "latin_america", "colombia": "latin_america",
    "mexico": "latin_america", "ecuador": "latin_america",
    # Africa
    "nigeria": "africa", "south africa": "africa", "drc": "africa",
    "congo": "africa", "zambia": "africa", "sudan": "africa",
    "ethiopia": "africa", "niger": "africa", "mali": "africa",
    # Europe
    "germany": "europe", "france": "europe", "uk": "europe",
    "britain": "europe", "poland": "europe", "turkey": "europe",
    # North America
    "united states": "north_america", "u.s.": "north_america",
    "us ": "north_america", "canada": "north_america",
}

# Mining region -> primary commodity (aligns with seismic.py MINING_REGIONS).
_REGION_COMMODITY: dict[str, list[str]] = {
    "Chile/Peru": ["COPPER"],
    "DRC/Zambia": ["COPPER", "COBALT"],
    "Indonesia/Papua": ["COPPER", "XAUUSD"],
    "Australia": ["XAUUSD", "IRON_ORE"],
    "South Africa": ["XAUUSD", "PLATINUM"],
    "Canada": ["XAUUSD", "COPPER"],
    "Russia/Siberia": ["XAUUSD", "PALLADIUM"],
    "Brazil": ["IRON_ORE", "COPPER"],
    "Philippines": ["COPPER", "XAUUSD"],
    "Mexico": ["XAGUSD", "COPPER"],
}


def detect_region(title: str) -> str | None:
    """Scan title for country/region keywords and return a region string.

    Args:
        title: Article headline.

    Returns:
        Region identifier string or None.
    """
    title_lower = title.lower()
    for country, region in _COUNTRY_TO_REGION.items():
        if country in title_lower:
            return region
    return None


def _detect_mining_region(title: str) -> str | None:
    """Detect a mining region name from title (for commodity mapping)."""
    title_lower = title.lower()
    mapping = {
        "chile": "Chile/Peru", "peru": "Chile/Peru",
        "congo": "DRC/Zambia", "drc": "DRC/Zambia", "zambia": "DRC/Zambia",
        "indonesia": "Indonesia/Papua", "papua": "Indonesia/Papua",
        "australia": "Australia",
        "south africa": "South Africa",
        "canada": "Canada",
        "russia": "Russia/Siberia", "siberia": "Russia/Siberia",
        "brazil": "Brazil",
        "philippines": "Philippines",
        "mexico": "Mexico",
    }
    for keyword, region_name in mapping.items():
        if keyword in title_lower:
            return region_name
    return None


# ---------------------------------------------------------------------------
# Impact rule tables per event type
# ---------------------------------------------------------------------------

_ARMED_CONFLICT_IMPACTS: list[TradeImpact] = [
    TradeImpact("XAUUSD", "bull", "strong", "Safe haven demand in conflict"),
    TradeImpact("USOIL", "bull", "moderate", "Supply risk premium"),
    TradeImpact("UKOIL", "bull", "moderate", "Supply risk premium"),
    TradeImpact("USDJPY", "bear", "moderate", "JPY safe haven bid"),
    TradeImpact("SPX", "bear", "weak", "Risk-off sentiment"),
    TradeImpact("NAS100", "bear", "weak", "Risk-off sentiment"),
]

_SANCTIONS_BASE: list[TradeImpact] = [
    TradeImpact("XAUUSD", "bull", "moderate", "Sanctions drive de-dollarization"),
    TradeImpact("DXY", "bull", "weak", "Dollar weaponization reinforces dominance short-term"),
]

_SUPPLY_DISRUPTION_BASE: list[TradeImpact] = [
    TradeImpact("XAUUSD", "bull", "moderate", "Supply uncertainty lifts safe havens"),
]

_MARITIME_THREAT_IMPACTS: list[TradeImpact] = [
    TradeImpact("UKOIL", "bull", "strong", "Chokepoint risk premium"),
    TradeImpact("USOIL", "bull", "strong", "Chokepoint risk premium"),
    TradeImpact("XAUUSD", "bull", "moderate", "Geopolitical uncertainty"),
    TradeImpact("XAGUSD", "bull", "weak", "Shipping-dependent commodity risk"),
]

_POLITICAL_CRISIS_IMPACTS: list[TradeImpact] = [
    TradeImpact("XAUUSD", "bull", "moderate", "Political uncertainty safe haven"),
    TradeImpact("SPX", "bear", "weak", "Risk-off on political instability"),
]

_TRADE_WAR_BASE: list[TradeImpact] = [
    TradeImpact("XAUUSD", "bull", "weak", "Uncertainty premium"),
    TradeImpact("SPX", "bear", "weak", "Trade friction dampens growth outlook"),
]

_ENERGY_CRISIS_IMPACTS: list[TradeImpact] = [
    TradeImpact("USOIL", "bull", "strong", "Energy supply crunch"),
    TradeImpact("UKOIL", "bull", "strong", "Energy supply crunch"),
    TradeImpact("EURUSD", "bear", "moderate", "Europe gas-dependent, EUR weakens"),
    TradeImpact("XAUUSD", "bull", "weak", "Energy uncertainty premium"),
]

# Sanctions — commodity affected by sanctioned country.
_SANCTIONS_COMMODITY: dict[str, list[TradeImpact]] = {
    "eastern_europe": [
        TradeImpact("USOIL", "bull", "strong", "Russia sanctions restrict oil supply"),
        TradeImpact("UKOIL", "bull", "strong", "Russia sanctions restrict oil supply"),
    ],
    "middle_east": [
        TradeImpact("USOIL", "bull", "strong", "Iran/ME sanctions restrict oil supply"),
        TradeImpact("UKOIL", "bull", "strong", "Iran/ME sanctions restrict oil supply"),
    ],
    "asia_pacific": [
        TradeImpact("COPPER", "bull", "strong", "China sanctions affect rare earths/metals"),
    ],
}

# Armed conflict — DXY direction depends on region.
_CONFLICT_DXY: dict[str, TradeImpact] = {
    "middle_east": TradeImpact("DXY", "bull", "moderate", "USD bid on ME conflict"),
    "eastern_europe": TradeImpact("DXY", "bull", "moderate", "USD bid on EU-adjacent conflict"),
    "north_america": TradeImpact("DXY", "bear", "moderate", "USD risk if US directly involved"),
}

# Trade war — retaliating country currency impact.
_TRADE_WAR_CURRENCY: dict[str, list[TradeImpact]] = {
    "asia_pacific": [
        TradeImpact("AUDUSD", "bear", "moderate", "China trade war hits AUD"),
    ],
    "europe": [
        TradeImpact("EURUSD", "bear", "moderate", "EU trade tensions weaken EUR"),
    ],
    "latin_america": [
        TradeImpact("USOIL", "bull", "weak", "LatAm trade disruption, oil bid"),
    ],
}


def map_event_to_trades(
    event_type: GeoEventType,
    region: str | None = None,
    keywords: list[str] | None = None,
) -> list[TradeImpact]:
    """Map a classified geo-event to affected instruments with direction.

    Args:
        event_type: The classified event type.
        region: Detected region string (from ``detect_region``).
        keywords: Additional keywords from the article (optional).

    Returns:
        List of ``TradeImpact`` objects.
    """
    impacts: list[TradeImpact] = []

    if event_type == GeoEventType.ARMED_CONFLICT:
        impacts.extend(_ARMED_CONFLICT_IMPACTS)
        if region and region in _CONFLICT_DXY:
            impacts.append(_CONFLICT_DXY[region])

    elif event_type == GeoEventType.SANCTIONS:
        impacts.extend(_SANCTIONS_BASE)
        if region and region in _SANCTIONS_COMMODITY:
            impacts.extend(_SANCTIONS_COMMODITY[region])

    elif event_type == GeoEventType.SUPPLY_DISRUPTION:
        impacts.extend(_SUPPLY_DISRUPTION_BASE)
        # Try to identify affected commodity from keywords or region.
        title_text = " ".join(keywords) if keywords else ""
        mining_region = _detect_mining_region(title_text)
        if mining_region and mining_region in _REGION_COMMODITY:
            for commodity in _REGION_COMMODITY[mining_region]:
                impacts.append(TradeImpact(
                    commodity, "bull", "strong",
                    f"Supply disruption in {mining_region} affects {commodity}",
                ))
                # Add substitute commodity at moderate.
                substitute = _get_substitute(commodity)
                if substitute:
                    impacts.append(TradeImpact(
                        substitute, "bull", "moderate",
                        f"Substitute demand as {commodity} supply disrupted",
                    ))

    elif event_type == GeoEventType.MARITIME_THREAT:
        impacts.extend(_MARITIME_THREAT_IMPACTS)

    elif event_type == GeoEventType.NATURAL_DISASTER:
        title_text = " ".join(keywords) if keywords else ""
        mining_region = _detect_mining_region(title_text)
        if mining_region and mining_region in _REGION_COMMODITY:
            for commodity in _REGION_COMMODITY[mining_region]:
                impacts.append(TradeImpact(
                    commodity, "bull", "strong",
                    f"Natural disaster in {mining_region} disrupts {commodity} production",
                ))
        else:
            # Fallback: generic safe haven bid.
            impacts.append(TradeImpact(
                "XAUUSD", "bull", "weak", "Natural disaster uncertainty",
            ))

    elif event_type == GeoEventType.POLITICAL_CRISIS:
        impacts.extend(_POLITICAL_CRISIS_IMPACTS)

    elif event_type == GeoEventType.TRADE_WAR:
        impacts.extend(_TRADE_WAR_BASE)
        if region and region in _TRADE_WAR_CURRENCY:
            impacts.extend(_TRADE_WAR_CURRENCY[region])

    elif event_type == GeoEventType.ENERGY_CRISIS:
        impacts.extend(_ENERGY_CRISIS_IMPACTS)

    return impacts


def _get_substitute(commodity: str) -> str | None:
    """Return a substitute commodity for supply-disruption scenarios."""
    subs: dict[str, str] = {
        "XAUUSD": "XAGUSD",
        "XAGUSD": "XAUUSD",
        "COPPER": "XAGUSD",
        "PLATINUM": "PALLADIUM",
        "PALLADIUM": "PLATINUM",
    }
    return subs.get(commodity)
