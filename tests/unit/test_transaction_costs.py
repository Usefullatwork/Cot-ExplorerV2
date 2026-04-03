"""Unit tests for src.analysis.transaction_costs — session-aware cost model."""

from __future__ import annotations

import math
from pathlib import Path

import pytest

from src.analysis.transaction_costs import (
    CostConfig,
    RoundTripCost,
    classify_session,
    estimate_round_trip_cost,
    estimate_slippage,
    estimate_spread,
    estimate_swap_cost,
    load_cost_configs,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_EURUSD_CONFIG = CostConfig(
    base_spread=1.2,
    spread_multipliers={
        "asian": 1.8,
        "london": 0.7,
        "ny_overlap": 0.75,
        "ny": 0.85,
        "off_hours": 2.5,
    },
    slippage_mean=0.3,
    slippage_std=0.15,
    swap_long=-0.6,
    swap_short=0.1,
    commission_per_lot=0.0,
)

_GOLD_CONFIG = CostConfig(
    base_spread=3.0,
    spread_multipliers={
        "asian": 1.8,
        "london": 0.7,
        "ny_overlap": 0.75,
        "ny": 0.85,
        "off_hours": 2.5,
    },
    slippage_mean=0.8,
    slippage_std=0.4,
    swap_long=-2.5,
    swap_short=0.5,
    commission_per_lot=0.0,
)


# ===========================================================================
# classify_session
# ===========================================================================


def test_classify_london_morning():
    """07:00 CET is London session."""
    assert classify_session(7) == "london"


def test_classify_london_midday():
    """12:00 CET is still London session."""
    assert classify_session(12) == "london"


def test_classify_ny_overlap():
    """14:00 CET is NY overlap."""
    assert classify_session(14) == "ny_overlap"


def test_classify_ny_overlap_boundary():
    """13:00 CET is the start of NY overlap."""
    assert classify_session(13) == "ny_overlap"


def test_classify_ny_overlap_end():
    """16:00 CET is still NY overlap."""
    assert classify_session(16) == "ny_overlap"


def test_classify_ny_session():
    """18:00 CET is NY session (post-overlap)."""
    assert classify_session(18) == "ny"


def test_classify_ny_start():
    """17:00 CET is NY session start."""
    assert classify_session(17) == "ny"


def test_classify_asian_midnight():
    """00:00 CET (midnight) is Asian session."""
    assert classify_session(0) == "asian"


def test_classify_asian_late_night():
    """23:00 CET is Asian session start."""
    assert classify_session(23) == "asian"


def test_classify_asian_early_morning():
    """05:00 CET is still Asian session."""
    assert classify_session(5) == "asian"


def test_classify_asian_boundary():
    """06:00 CET is still Asian (ends at 7)."""
    assert classify_session(6) == "asian"


def test_classify_off_hours():
    """21:00 CET is off-hours (between NY close and Asian open)."""
    assert classify_session(21) == "off_hours"


def test_classify_off_hours_22():
    """22:00 CET is off-hours."""
    assert classify_session(22) == "off_hours"


def test_classify_wraps_at_24():
    """Hour 24 wraps to 0 (midnight -> asian)."""
    assert classify_session(24) == "asian"


def test_classify_all_hours_return_valid_session():
    """Every hour from 0-23 maps to a known session."""
    valid = {"london", "ny_overlap", "ny", "asian", "off_hours"}
    for h in range(24):
        assert classify_session(h) in valid, f"hour {h}"


# ===========================================================================
# estimate_spread
# ===========================================================================


def test_spread_london_cheaper_than_asian():
    """London spread should be lower than Asian spread."""
    london = estimate_spread(_EURUSD_CONFIG, 9)
    asian = estimate_spread(_EURUSD_CONFIG, 3)
    assert london < asian


def test_spread_london_multiplier():
    """London spread = base * 0.7."""
    result = estimate_spread(_EURUSD_CONFIG, 10)
    assert result == pytest.approx(1.2 * 0.7)


def test_spread_asian_multiplier():
    """Asian spread = base * 1.8."""
    result = estimate_spread(_EURUSD_CONFIG, 2)
    assert result == pytest.approx(1.2 * 1.8)


def test_spread_ny_overlap_multiplier():
    """NY overlap spread = base * 0.75."""
    result = estimate_spread(_EURUSD_CONFIG, 15)
    assert result == pytest.approx(1.2 * 0.75)


def test_spread_ny_multiplier():
    """NY session spread = base * 0.85."""
    result = estimate_spread(_EURUSD_CONFIG, 19)
    assert result == pytest.approx(1.2 * 0.85)


def test_spread_off_hours_multiplier():
    """Off-hours spread = base * 2.5."""
    result = estimate_spread(_EURUSD_CONFIG, 22)
    assert result == pytest.approx(1.2 * 2.5)


def test_spread_gold_london():
    """Gold base_spread=3.0, London multiplier should apply."""
    result = estimate_spread(_GOLD_CONFIG, 10)
    assert result == pytest.approx(3.0 * 0.7)


def test_spread_missing_session_falls_back_to_off_hours():
    """If a session key is missing, fall back to off_hours multiplier."""
    config = CostConfig(
        base_spread=2.0,
        spread_multipliers={"off_hours": 3.0},
        slippage_mean=0.5,
        slippage_std=0.2,
        swap_long=-1.0,
        swap_short=0.5,
        commission_per_lot=0.0,
    )
    # London session key is missing -> falls back to off_hours=3.0
    result = estimate_spread(config, 10)
    assert result == pytest.approx(2.0 * 3.0)


# ===========================================================================
# estimate_slippage
# ===========================================================================


def test_slippage_deterministic_with_seed():
    """Same seed produces same slippage."""
    a = estimate_slippage(_EURUSD_CONFIG, 1.0, seed=42)
    b = estimate_slippage(_EURUSD_CONFIG, 1.0, seed=42)
    assert a == b


def test_slippage_different_seeds_differ():
    """Different seeds produce different slippage."""
    a = estimate_slippage(_EURUSD_CONFIG, 1.0, seed=42)
    b = estimate_slippage(_EURUSD_CONFIG, 1.0, seed=99)
    assert a != b


def test_slippage_increases_with_lots():
    """Larger lot sizes produce higher average slippage (sqrt scaling)."""
    # Use same seed for comparable draws; the mean scales with sqrt(lots).
    small = estimate_slippage(_EURUSD_CONFIG, 0.1, seed=42)
    large = estimate_slippage(_EURUSD_CONFIG, 10.0, seed=42)
    assert large > small


def test_slippage_sqrt_scaling():
    """Slippage mean scales as sqrt(lots)."""
    # With std=0 (no randomness), output = mean * sqrt(lots) * vol_factor.
    config = CostConfig(
        base_spread=1.0,
        spread_multipliers={},
        slippage_mean=1.0,
        slippage_std=0.0,
        swap_long=0.0,
        swap_short=0.0,
        commission_per_lot=0.0,
    )
    result = estimate_slippage(config, 4.0, volatility_factor=1.0)
    assert result == pytest.approx(1.0 * math.sqrt(4.0))


def test_slippage_zero_lots():
    """Zero lots returns zero slippage."""
    result = estimate_slippage(_EURUSD_CONFIG, 0.0, seed=42)
    assert result == 0.0


def test_slippage_negative_lots():
    """Negative lots returns zero slippage."""
    result = estimate_slippage(_EURUSD_CONFIG, -1.0, seed=42)
    assert result == 0.0


def test_slippage_always_non_negative():
    """Slippage is never negative (lognormal is always positive)."""
    for s in range(100):
        slip = estimate_slippage(_EURUSD_CONFIG, 1.0, seed=s)
        assert slip >= 0.0


def test_slippage_volatility_factor():
    """Higher volatility factor increases slippage (with zero std)."""
    config = CostConfig(
        base_spread=1.0,
        spread_multipliers={},
        slippage_mean=1.0,
        slippage_std=0.0,
        swap_long=0.0,
        swap_short=0.0,
        commission_per_lot=0.0,
    )
    normal = estimate_slippage(config, 1.0, volatility_factor=1.0)
    high = estimate_slippage(config, 1.0, volatility_factor=2.0)
    assert high == pytest.approx(normal * 2.0)


# ===========================================================================
# estimate_swap_cost
# ===========================================================================


def test_swap_long_single_day():
    """Long swap for 1 day = swap_long * 1."""
    result = estimate_swap_cost(_EURUSD_CONFIG, "long", 1)
    assert result == pytest.approx(-0.6)


def test_swap_short_single_day():
    """Short swap for 1 day = swap_short * 1."""
    result = estimate_swap_cost(_EURUSD_CONFIG, "short", 1)
    assert result == pytest.approx(0.1)


def test_swap_multi_day():
    """Multi-day swap accumulates linearly."""
    result = estimate_swap_cost(_EURUSD_CONFIG, "long", 5)
    assert result == pytest.approx(-0.6 * 5)


def test_swap_zero_days():
    """Zero holding days returns zero swap."""
    result = estimate_swap_cost(_EURUSD_CONFIG, "long", 0)
    assert result == 0.0


def test_swap_negative_days_treated_as_zero():
    """Negative holding days are clamped to zero."""
    result = estimate_swap_cost(_EURUSD_CONFIG, "long", -3)
    assert result == 0.0


def test_swap_invalid_direction():
    """Unknown direction returns zero swap."""
    result = estimate_swap_cost(_EURUSD_CONFIG, "sideways", 5)
    assert result == 0.0


def test_swap_gold_long():
    """Gold long swap = -2.5 * days."""
    result = estimate_swap_cost(_GOLD_CONFIG, "long", 3)
    assert result == pytest.approx(-2.5 * 3)


# ===========================================================================
# estimate_round_trip_cost
# ===========================================================================


def test_round_trip_total_equals_components():
    """total_pips = spread + slippage (2x) + swap."""
    cost = estimate_round_trip_cost(
        _EURUSD_CONFIG,
        lots=1.0,
        hour_cet=10,
        direction="long",
        holding_days=0,
        seed=42,
    )
    expected_total = cost.spread_pips + cost.slippage_pips + cost.swap_pips
    assert cost.total_pips == pytest.approx(expected_total)


def test_round_trip_intraday_no_swap():
    """Intraday trade (holding_days=0) has zero swap cost."""
    cost = estimate_round_trip_cost(
        _EURUSD_CONFIG,
        lots=1.0,
        hour_cet=10,
        direction="long",
        holding_days=0,
        seed=42,
    )
    assert cost.swap_pips == 0.0


def test_round_trip_with_holding_days():
    """Multi-day hold accumulates swap cost."""
    cost = estimate_round_trip_cost(
        _EURUSD_CONFIG,
        lots=1.0,
        hour_cet=10,
        direction="long",
        holding_days=3,
        seed=42,
    )
    assert cost.swap_pips == pytest.approx(-0.6 * 3)


def test_round_trip_slippage_is_two_legs():
    """Slippage should be entry + exit (two independent draws)."""
    cost = estimate_round_trip_cost(
        _EURUSD_CONFIG,
        lots=1.0,
        hour_cet=10,
        direction="long",
        holding_days=0,
        seed=42,
    )
    # Verify slippage is sum of two independent draws
    entry_slip = estimate_slippage(_EURUSD_CONFIG, 1.0, seed=42)
    exit_slip = estimate_slippage(_EURUSD_CONFIG, 1.0, seed=43)
    assert cost.slippage_pips == pytest.approx(entry_slip + exit_slip)


def test_round_trip_commission_zero_for_spread_account():
    """EURUSD has commission_per_lot=0 -> commission_usd=0."""
    cost = estimate_round_trip_cost(
        _EURUSD_CONFIG,
        lots=2.0,
        hour_cet=10,
        direction="long",
        seed=42,
    )
    assert cost.commission_usd == 0.0


def test_round_trip_commission_with_per_lot_charge():
    """Commission = commission_per_lot * lots."""
    config = CostConfig(
        base_spread=1.0,
        spread_multipliers={"london": 1.0, "off_hours": 1.0},
        slippage_mean=0.0,
        slippage_std=0.0,
        swap_long=0.0,
        swap_short=0.0,
        commission_per_lot=7.0,
    )
    cost = estimate_round_trip_cost(
        config, lots=2.5, hour_cet=10, direction="long", seed=42,
    )
    assert cost.commission_usd == pytest.approx(7.0 * 2.5)


def test_round_trip_deterministic_with_seed():
    """Same inputs + seed produce identical results."""
    a = estimate_round_trip_cost(
        _EURUSD_CONFIG, lots=1.0, hour_cet=10, direction="long", seed=42,
    )
    b = estimate_round_trip_cost(
        _EURUSD_CONFIG, lots=1.0, hour_cet=10, direction="long", seed=42,
    )
    assert a == b


def test_round_trip_frozen_dataclass():
    """RoundTripCost is immutable."""
    cost = estimate_round_trip_cost(
        _EURUSD_CONFIG, lots=1.0, hour_cet=10, direction="long", seed=42,
    )
    with pytest.raises(AttributeError):
        cost.total_pips = 999.0  # type: ignore[misc]


# ===========================================================================
# load_cost_configs (integration with YAML file)
# ===========================================================================


def test_load_cost_configs_from_file():
    """Load the actual config/transaction_costs.yaml and verify structure."""
    yaml_path = Path(__file__).resolve().parents[2] / "config" / "transaction_costs.yaml"
    if not yaml_path.exists():
        pytest.skip("config/transaction_costs.yaml not found")

    configs = load_cost_configs(yaml_path)

    assert "EURUSD" in configs
    assert "XAUUSD" in configs
    assert "NAS100" in configs
    assert len(configs) == 16

    eurusd = configs["EURUSD"]
    assert eurusd.base_spread == pytest.approx(0.77)
    assert "london" in eurusd.spread_multipliers
    assert eurusd.spread_multipliers["london"] == pytest.approx(0.8)


def test_load_cost_configs_all_instruments_present():
    """All 16 instruments are present in Pepperstone config."""
    yaml_path = Path(__file__).resolve().parents[2] / "config" / "transaction_costs.yaml"
    if not yaml_path.exists():
        pytest.skip("config/transaction_costs.yaml not found")

    configs = load_cost_configs(yaml_path)
    expected = {
        "EURUSD", "USDJPY", "GBPUSD", "AUDUSD", "USDCHF",
        "XAUUSD", "XAGUSD", "USOIL", "UKOIL", "NATGAS",
        "WHEAT", "CORN", "XPTUSD", "XPDUSD", "SPX500", "NAS100",
    }
    assert set(configs.keys()) == expected
