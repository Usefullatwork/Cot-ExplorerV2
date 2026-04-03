"""Stress testing: historical scenario replay on a portfolio.

Applies predefined sensitivity shocks (GFC 2008, COVID 2020, Rate Shock
2022, Flash Crash) to each position in a portfolio and reports total
expected loss as a percentage of equity.

All functions are pure -- no I/O, no DB, no side effects.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ScenarioImpact:
    """Impact on a single instrument from a stress scenario."""

    instrument: str
    price_change_pct: float
    position_loss_pct: float  # loss as % of position value


@dataclass(frozen=True)
class StressResult:
    """Result of a stress test scenario."""

    scenario_name: str
    description: str
    total_loss_pct: float
    worst_instrument: str
    worst_loss_pct: float
    impacts: list[ScenarioImpact]
    survives: bool


@dataclass(frozen=True)
class Position:
    """A portfolio position for stress testing."""

    instrument: str
    direction: str  # "long" or "short"
    value_usd: float


# ---------------------------------------------------------------------------
# Sensitivity coefficients per scenario and instrument class
# Positive = price increase, negative = price decrease
# ---------------------------------------------------------------------------

SCENARIO_SENSITIVITIES: dict[str, dict[str, float]] = {
    "2008_gfc": {
        "forex_major": -0.05,
        "forex_safe": 0.10,
        "gold": 0.15,
        "silver": -0.10,
        "oil": -0.55,
        "natgas": -0.30,
        "indices": -0.40,
        "agriculture": -0.15,
        "platinum_group": -0.35,
    },
    "2020_covid": {
        "forex_major": -0.03,
        "forex_safe": 0.08,
        "gold": 0.10,
        "silver": -0.20,
        "oil": -0.65,
        "natgas": -0.25,
        "indices": -0.35,
        "agriculture": -0.10,
        "platinum_group": -0.30,
    },
    "2022_rate_shock": {
        "forex_major": -0.08,
        "forex_safe": -0.05,
        "gold": -0.10,
        "silver": -0.15,
        "oil": 0.20,
        "natgas": 0.40,
        "indices": -0.20,
        "agriculture": 0.10,
        "platinum_group": -0.10,
    },
    "flash_crash": {
        "forex_major": -0.03,
        "forex_safe": 0.05,
        "gold": 0.05,
        "silver": -0.05,
        "oil": -0.10,
        "natgas": -0.08,
        "indices": -0.10,
        "agriculture": -0.03,
        "platinum_group": -0.08,
    },
}

SCENARIO_DESCRIPTIONS: dict[str, str] = {
    "2008_gfc": "2008 Global Financial Crisis — equity/commodity crash, safe-haven bid",
    "2020_covid": "2020 COVID-19 pandemic — oil collapse, equity crash, gold bid",
    "2022_rate_shock": "2022 rate shock — DXY strong, gold/equities down, energy up",
    "flash_crash": "Flash crash — rapid 5-10% drawdown across risk assets",
}

# ---------------------------------------------------------------------------
# Instrument -> sensitivity class mapping
# ---------------------------------------------------------------------------

INSTRUMENT_CLASS: dict[str, str] = {
    "EURUSD": "forex_major",
    "GBPUSD": "forex_major",
    "AUDUSD": "forex_major",
    "USDJPY": "forex_safe",
    "USDCHF": "forex_safe",
    "Gold": "gold",
    "Silver": "silver",
    "Brent": "oil",
    "WTI": "oil",
    "NATGAS": "natgas",
    "SPX": "indices",
    "NAS100": "indices",
    "WHEAT": "agriculture",
    "CORN": "agriculture",
    "XPTUSD": "platinum_group",
    "XPDUSD": "platinum_group",
}

_DEFAULT_SENSITIVITY = -0.02  # unknown instruments get a small adverse move


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def classify_instrument(instrument: str) -> str:
    """Map an instrument name to its sensitivity class.

    Args:
        instrument: Instrument key (e.g. ``"EURUSD"``, ``"Gold"``).

    Returns:
        Sensitivity class string.  Falls back to ``"unknown"`` when not
        found in the mapping.
    """
    return INSTRUMENT_CLASS.get(instrument, "unknown")


def _direction_sign(direction: str) -> float:
    """Return +1 for long, -1 for short."""
    return 1.0 if direction == "long" else -1.0


# ---------------------------------------------------------------------------
# Core stress testing
# ---------------------------------------------------------------------------


def stress_test_portfolio(
    positions: list[Position],
    equity: float,
    scenario: str,
    sensitivities: dict[str, dict[str, float]] | None = None,
) -> StressResult:
    """Run a single stress scenario on a portfolio.

    For each position the function:
      1. Looks up the instrument's sensitivity class.
      2. Reads the scenario sensitivity for that class.
      3. Applies direction: longs lose on price drops, shorts gain.
      4. Sums total loss as a percentage of equity.

    Args:
        positions: List of portfolio positions.
        equity: Total account equity in USD.
        scenario: Scenario key (e.g. ``"2008_gfc"``).
        sensitivities: Optional override for the sensitivity table.

    Returns:
        StressResult for this scenario.
    """
    sens_table = sensitivities if sensitivities is not None else SCENARIO_SENSITIVITIES
    scenario_sens = sens_table.get(scenario, {})
    description = SCENARIO_DESCRIPTIONS.get(scenario, scenario)

    if not positions or equity <= 0.0:
        return StressResult(
            scenario_name=scenario,
            description=description,
            total_loss_pct=0.0,
            worst_instrument="",
            worst_loss_pct=0.0,
            impacts=[],
            survives=True,
        )

    impacts: list[ScenarioImpact] = []
    total_loss = 0.0
    worst_instrument = ""
    worst_loss = 0.0

    for pos in positions:
        asset_class = classify_instrument(pos.instrument)
        price_change = scenario_sens.get(asset_class, _DEFAULT_SENSITIVITY)

        # P&L for the position: price goes up -> long profits, short loses
        # position_pnl = value * price_change * direction_sign
        # A negative pnl is a loss.
        dir_sign = _direction_sign(pos.direction)
        position_pnl = pos.value_usd * price_change * dir_sign

        # Loss as % of position value (positive = loss)
        loss_pct = -(price_change * dir_sign) * 100.0

        impacts.append(ScenarioImpact(
            instrument=pos.instrument,
            price_change_pct=price_change * 100.0,
            position_loss_pct=loss_pct,
        ))

        total_loss -= position_pnl  # positive total_loss = bad

        if loss_pct > worst_loss:
            worst_loss = loss_pct
            worst_instrument = pos.instrument

    total_loss_pct = (total_loss / equity) * 100.0

    return StressResult(
        scenario_name=scenario,
        description=description,
        total_loss_pct=total_loss_pct,
        worst_instrument=worst_instrument,
        worst_loss_pct=worst_loss,
        impacts=impacts,
        survives=total_loss_pct < 15.0,
    )


# ---------------------------------------------------------------------------
# Gate checks
# ---------------------------------------------------------------------------


def check_stress_gate(
    results: list[StressResult],
    max_loss_pct: float = 15.0,
) -> tuple[bool, str]:
    """Gate check: block new positions if ANY scenario exceeds *max_loss_pct*.

    Args:
        results: List of StressResult from all scenarios.
        max_loss_pct: Maximum tolerable loss as a percentage of equity.

    Returns:
        (allowed, reason) tuple.
    """
    for r in results:
        if r.total_loss_pct >= max_loss_pct:
            return (
                False,
                f"stress gate: {r.scenario_name} loss {r.total_loss_pct:.1f}% "
                f">= {max_loss_pct:.1f}%",
            )
    return (True, "all stress scenarios within limits")


def run_all_stress_tests(
    positions: list[Position],
    equity: float,
    max_loss_pct: float = 15.0,
) -> tuple[list[StressResult], bool, str]:
    """Run all four built-in stress scenarios and return gate decision.

    Args:
        positions: List of portfolio positions.
        equity: Total account equity in USD.
        max_loss_pct: Maximum tolerable loss as a percentage of equity.

    Returns:
        (results, allowed, reason) tuple.
    """
    results = [
        stress_test_portfolio(positions, equity, scenario)
        for scenario in SCENARIO_SENSITIVITIES
    ]

    allowed, reason = check_stress_gate(results, max_loss_pct)
    return results, allowed, reason
