"""Transaction cost modelling -- session-aware spread, lognormal slippage, swap costs.

Pure functions with no I/O or database access.  Config is loaded once
from ``config/transaction_costs.yaml`` and passed around as frozen
dataclasses so every call is deterministic and side-effect-free.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class CostConfig:
    """Per-instrument cost parameters (immutable)."""

    base_spread: float
    spread_multipliers: dict[str, float]
    slippage_mean: float
    slippage_std: float
    swap_long: float
    swap_short: float
    commission_per_lot: float


@dataclass(frozen=True)
class RoundTripCost:
    """Breakdown of a single round-trip trade's transaction costs."""

    spread_pips: float
    slippage_pips: float
    swap_pips: float
    commission_usd: float
    total_pips: float


# ---------------------------------------------------------------------------
# Config loading
# ---------------------------------------------------------------------------

def load_cost_configs(yaml_path: str | Path) -> dict[str, CostConfig]:
    """Load ``config/transaction_costs.yaml`` into a ``{symbol: CostConfig}`` dict.

    The YAML file must contain a top-level ``instruments`` mapping where
    each key is an instrument symbol and each value contains the fields
    required by :class:`CostConfig`.

    Parameters
    ----------
    yaml_path:
        Filesystem path to the YAML config file.

    Returns
    -------
    dict[str, CostConfig]
        Mapping from instrument symbol to its frozen cost configuration.
    """
    path = Path(yaml_path)
    with path.open("r", encoding="utf-8") as fh:
        raw: dict[str, Any] = yaml.safe_load(fh)

    instruments: dict[str, Any] = raw.get("instruments", {})
    result: dict[str, CostConfig] = {}
    for symbol, params in instruments.items():
        result[symbol] = CostConfig(
            base_spread=float(params["base_spread"]),
            spread_multipliers={
                k: float(v) for k, v in params["spread_multipliers"].items()
            },
            slippage_mean=float(params["slippage_mean"]),
            slippage_std=float(params["slippage_std"]),
            swap_long=float(params["swap_long"]),
            swap_short=float(params["swap_short"]),
            commission_per_lot=float(params["commission_per_lot"]),
        )
    return result


# ---------------------------------------------------------------------------
# Session classification
# ---------------------------------------------------------------------------

# Session boundaries in CET hours (start inclusive, end exclusive).
_SESSION_RANGES: list[tuple[str, int, int]] = [
    # Order matters: ny_overlap is a subset of ny, so check it first.
    ("ny_overlap", 13, 17),
    ("london", 7, 13),
    ("ny", 17, 21),
    # Asian wraps midnight -- handled separately in classify_session.
]

_ASIAN_START = 23
_ASIAN_END = 7


def classify_session(hour_cet: int) -> str:
    """Map a CET hour (0-23) to a trading session name.

    Session priority (checked in order):
    1. ``ny_overlap`` -- 13:00-16:59 CET
    2. ``london``     -- 07:00-12:59 CET
    3. ``ny``         -- 17:00-20:59 CET
    4. ``asian``      -- 23:00-06:59 CET (wraps midnight)
    5. ``off_hours``  -- anything else (21:00-22:59 CET)

    Parameters
    ----------
    hour_cet:
        Hour of day in CET (0-23).

    Returns
    -------
    str
        One of ``london``, ``ny_overlap``, ``ny``, ``asian``, ``off_hours``.
    """
    hour = hour_cet % 24

    for name, start, end in _SESSION_RANGES:
        if start <= hour < end:
            return name

    # Asian session wraps midnight: 23 <= hour or hour < 7
    if hour >= _ASIAN_START or hour < _ASIAN_END:
        return "asian"

    return "off_hours"


# ---------------------------------------------------------------------------
# Spread estimation
# ---------------------------------------------------------------------------

def estimate_spread(config: CostConfig, hour_cet: int) -> float:
    """Estimate the effective spread for the given hour.

    ``base_spread * spread_multipliers[session]``.  If the session key
    is missing from the multiplier dict, falls back to ``off_hours``
    (or 1.0 if that is also missing).

    Parameters
    ----------
    config:
        Cost configuration for the instrument.
    hour_cet:
        Hour of day in CET (0-23).

    Returns
    -------
    float
        Estimated spread in pips.
    """
    session = classify_session(hour_cet)
    multiplier = config.spread_multipliers.get(
        session,
        config.spread_multipliers.get("off_hours", 1.0),
    )
    return config.base_spread * multiplier


# ---------------------------------------------------------------------------
# Slippage estimation
# ---------------------------------------------------------------------------

def estimate_slippage(
    config: CostConfig,
    lots: float,
    volatility_factor: float = 1.0,
    seed: int | None = None,
) -> float:
    """Estimate one-way slippage using a lognormal distribution.

    Slippage scales with ``sqrt(lots)`` to model the impact of larger
    order sizes on market depth.  A ``volatility_factor`` > 1 increases
    slippage during high-volatility regimes.

    Uses ``random.Random(seed)`` for deterministic results in tests,
    matching the pattern used by ``monte_carlo.py``.

    Parameters
    ----------
    config:
        Cost configuration for the instrument.
    lots:
        Trade size in lots.  Zero or negative returns 0.0.
    volatility_factor:
        Multiplier for volatility conditions (default 1.0 = normal).
    seed:
        Optional RNG seed for deterministic output.

    Returns
    -------
    float
        Estimated slippage in pips (always >= 0).
    """
    if lots <= 0:
        return 0.0

    rng = random.Random(seed)

    lot_scaling = math.sqrt(max(lots, 0.01))
    mean = config.slippage_mean * lot_scaling * volatility_factor

    if config.slippage_std <= 0 or mean <= 0:
        return max(mean, 0.0)

    # Convert mean/std to lognormal mu/sigma parameters.
    variance = config.slippage_std ** 2
    mu = math.log(mean ** 2 / math.sqrt(variance + mean ** 2))
    sigma = math.sqrt(math.log(1 + variance / mean ** 2))

    return rng.lognormvariate(mu, sigma)


# ---------------------------------------------------------------------------
# Swap cost estimation
# ---------------------------------------------------------------------------

def estimate_swap_cost(
    config: CostConfig,
    direction: str,
    holding_days: int,
) -> float:
    """Calculate accumulated swap cost for holding a position overnight.

    Parameters
    ----------
    config:
        Cost configuration for the instrument.
    direction:
        ``"long"`` or ``"short"``.
    holding_days:
        Number of overnight rollovers.  Negative values are treated as 0.

    Returns
    -------
    float
        Total swap cost in pips (positive = cost to trader).
    """
    days = max(holding_days, 0)
    if days == 0:
        return 0.0

    if direction == "long":
        return config.swap_long * days
    if direction == "short":
        return config.swap_short * days

    return 0.0


# ---------------------------------------------------------------------------
# Round-trip cost estimation
# ---------------------------------------------------------------------------

def estimate_round_trip_cost(
    config: CostConfig,
    lots: float,
    hour_cet: int,
    direction: str,
    holding_days: int = 0,
    volatility_factor: float = 1.0,
    seed: int | None = None,
) -> RoundTripCost:
    """Estimate the full round-trip cost of a trade.

    Components:
    - **Spread**: paid once at entry (session-dependent).
    - **Slippage**: paid twice (entry + exit), each independently sampled.
    - **Swap**: accumulated per holding day.
    - **Commission**: per-lot charge in USD.

    Parameters
    ----------
    config:
        Cost configuration for the instrument.
    lots:
        Trade size in lots.
    hour_cet:
        Hour of day in CET (0-23) for session-dependent spread.
    direction:
        ``"long"`` or ``"short"``.
    holding_days:
        Number of overnight rollovers (default 0 = intraday).
    volatility_factor:
        Multiplier for volatility conditions (default 1.0).
    seed:
        Optional RNG seed for deterministic slippage.

    Returns
    -------
    RoundTripCost
        Frozen dataclass with per-component and total pip costs.
    """
    spread = estimate_spread(config, hour_cet)

    # Two independent slippage draws (entry + exit).
    # Use sequential seeds derived from base seed for reproducibility.
    seed_entry = seed
    seed_exit = (seed + 1) if seed is not None else None
    slip_entry = estimate_slippage(config, lots, volatility_factor, seed_entry)
    slip_exit = estimate_slippage(config, lots, volatility_factor, seed_exit)
    total_slippage = slip_entry + slip_exit

    swap = estimate_swap_cost(config, direction, holding_days)
    commission = config.commission_per_lot * max(lots, 0)

    total_pips = spread + total_slippage + swap

    return RoundTripCost(
        spread_pips=spread,
        slippage_pips=total_slippage,
        swap_pips=swap,
        commission_usd=commission,
        total_pips=total_pips,
    )
