"""Market regime detector — crisis-aware trading parameter adjustments.

Detects the current market regime from VIX, oil, DXY, and active
geopolitical events, then returns parameter overrides for the trading
bot (min_score, risk_pct, max_positions, safe_haven filters).

All functions are pure: no DB, no HTTP, no side effects.
"""

from __future__ import annotations

from enum import Enum


class MarketRegime(str, Enum):
    """Market regime classifications for risk management."""

    NORMAL = "normal"
    RISK_OFF = "risk_off"
    CRISIS = "crisis"
    WAR_FOOTING = "war_footing"
    ENERGY_SHOCK = "energy_shock"
    SANCTIONS = "sanctions"


# ---------------------------------------------------------------------------
# Asset classifications
# ---------------------------------------------------------------------------

SAFE_HAVENS: frozenset[str] = frozenset({
    "XAUUSD", "Gold", "XAGUSD", "Silver", "USDJPY", "USDCHF",
})

RISK_ASSETS: frozenset[str] = frozenset({
    "SPX", "NAS100", "AUDUSD", "GBPUSD",
})

ENERGY_INSTRUMENTS: frozenset[str] = frozenset({
    "Brent", "WTI", "NATGAS", "UKOIL", "USOIL",
})

# Geo-event type values that map to conflict/crisis categories.
_CONFLICT_EVENTS: frozenset[str] = frozenset({
    "armed_conflict", "political_crisis",
})

_ENERGY_EVENTS: frozenset[str] = frozenset({
    "energy_crisis", "supply_disruption", "maritime_threat",
})

_SANCTIONS_EVENTS: frozenset[str] = frozenset({
    "sanctions",
})


# ---------------------------------------------------------------------------
# Regime detection
# ---------------------------------------------------------------------------

def detect_regime(
    vix_price: float,
    vix_5d_change: float,
    oil_5d_change: float,
    active_geo_events: list[str],
    dxy_5d_change: float,
) -> MarketRegime:
    """Determine the current market regime from macro indicators.

    Priority order (first match wins):
      1. VIX > 35 AND armed_conflict/political_crisis -> WAR_FOOTING
      2. VIX > 35 -> CRISIS
      3. Oil 5d change > 20% AND energy events -> ENERGY_SHOCK
      4. Active sanctions events -> SANCTIONS
      5. VIX > 25 -> RISK_OFF
      6. Otherwise -> NORMAL

    Args:
        vix_price: Current VIX price.
        vix_5d_change: VIX percentage change over 5 trading days.
        oil_5d_change: Oil (Brent/WTI) percentage change over 5 days.
        active_geo_events: List of GeoEventType string values currently active.
        dxy_5d_change: Dollar Index percentage change over 5 days.

    Returns:
        The detected MarketRegime.
    """
    events_set = set(active_geo_events)

    # 1. WAR_FOOTING: extreme VIX + armed conflict / political crisis
    if vix_price > 35 and events_set & _CONFLICT_EVENTS:
        return MarketRegime.WAR_FOOTING

    # 2. CRISIS: extreme VIX alone
    if vix_price > 35:
        return MarketRegime.CRISIS

    # 3. ENERGY_SHOCK: large oil move + energy-related events
    if abs(oil_5d_change) > 20 and events_set & _ENERGY_EVENTS:
        return MarketRegime.ENERGY_SHOCK

    # 4. SANCTIONS: active sanctions on major producer
    if events_set & _SANCTIONS_EVENTS:
        return MarketRegime.SANCTIONS

    # 5. RISK_OFF: elevated VIX
    if vix_price > 25:
        return MarketRegime.RISK_OFF

    # 6. NORMAL
    return MarketRegime.NORMAL


# ---------------------------------------------------------------------------
# Regime parameter adjustments
# ---------------------------------------------------------------------------

_REGIME_ADJUSTMENTS: dict[MarketRegime, dict] = {
    MarketRegime.NORMAL: {},
    MarketRegime.RISK_OFF: {
        "min_score": 12,
        "risk_pct": 0.5,
        "safe_haven_boost": 2,
        "risk_asset_penalty": -2,
    },
    MarketRegime.CRISIS: {
        "min_score": 14,
        "risk_pct": 0.25,
        "max_positions": 3,
        "safe_haven_only": True,
    },
    MarketRegime.WAR_FOOTING: {
        "min_score": 16,
        "risk_pct": 0.1,
        "max_positions": 2,
        "safe_haven_only": True,
        "energy_boost": 3,
    },
    MarketRegime.ENERGY_SHOCK: {
        "min_score": 12,
        "risk_pct": 0.5,
        "energy_boost": 3,
        "max_positions": 4,
    },
    MarketRegime.SANCTIONS: {
        "min_score": 12,
        "affected_commodity_boost": 3,
    },
}


def get_regime_adjustments(regime: MarketRegime) -> dict:
    """Return parameter overrides for the given regime.

    Args:
        regime: The current market regime.

    Returns:
        Dict of parameter overrides.  Empty dict for NORMAL.
    """
    return dict(_REGIME_ADJUSTMENTS.get(regime, {}))


# ---------------------------------------------------------------------------
# Score application
# ---------------------------------------------------------------------------

_MAX_SCORE = 19


def apply_regime_to_score(
    instrument: str,
    base_score: int,
    regime: MarketRegime,
    adjustments: dict,
) -> int:
    """Apply regime-specific boosts/penalties to an instrument's confluence score.

    - Safe haven instruments receive ``safe_haven_boost`` if present.
    - Risk assets receive ``risk_asset_penalty`` if present.
    - Energy instruments receive ``energy_boost`` if present.
    - Result is clamped to [0, 19].

    Args:
        instrument: Instrument key (e.g. ``"XAUUSD"``).
        base_score: Original confluence score (0-19).
        regime: Current market regime.
        adjustments: Dict from ``get_regime_adjustments``.

    Returns:
        Adjusted score clamped to 0-19.
    """
    score = base_score

    # Safe haven boost
    if instrument in SAFE_HAVENS:
        score += adjustments.get("safe_haven_boost", 0)

    # Risk asset penalty
    if instrument in RISK_ASSETS:
        score += adjustments.get("risk_asset_penalty", 0)

    # Energy boost
    if instrument in ENERGY_INSTRUMENTS:
        score += adjustments.get("energy_boost", 0)

    return max(0, min(score, _MAX_SCORE))
