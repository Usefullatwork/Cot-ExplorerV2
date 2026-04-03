"""Risk-parity portfolio allocation: inverse-vol weights, target-vol sizing.

Pure functions for distributing risk budget across instruments using
inverse-volatility weighting and target-volatility position sizing.
No I/O, no DB, no side effects.
"""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class RiskParityAllocation:
    """Per-instrument allocation from risk parity."""

    instrument: str
    volatility: float           # annualized vol or ATR-based
    raw_weight: float           # 1/vol normalized
    clamped_weight: float       # clamped to [min_weight, max_weight]
    target_risk_usd: float      # equity * clamped_weight


@dataclass(frozen=True)
class RiskParityResult:
    """Full risk parity allocation result."""

    allocations: list[RiskParityAllocation]
    total_weight: float         # should sum to ~1.0 after clamping
    hhi: float                  # Herfindahl-Hirschman Index (concentration)


# ---------------------------------------------------------------------------
# Inverse-volatility weights
# ---------------------------------------------------------------------------


def inverse_vol_weights(
    volatilities: dict[str, float],
    min_weight: float = 0.02,
    max_weight: float = 0.30,
    equity: float = 0.0,
) -> RiskParityResult:
    """Compute inverse-volatility weights.

    weight_i = (1/vol_i) / sum(1/vol_j for all j)
    Then clamp each weight to [min_weight, max_weight] and re-normalize.

    HHI = sum(w_i^2) -- lower is more diversified. HHI=1/n is perfectly equal.

    Args:
        volatilities: Mapping of instrument -> annualized volatility.
            Instruments with vol <= 0 are excluded.
        min_weight: Minimum weight per instrument (default 2 %).
        max_weight: Maximum weight per instrument (default 30 %).
        equity: Account equity for computing target_risk_usd (default 0).

    Returns:
        RiskParityResult with allocations, total_weight, and HHI.
    """
    # Filter out zero/negative volatilities
    valid = {k: v for k, v in volatilities.items() if v > 0.0}
    if not valid:
        return RiskParityResult(allocations=[], total_weight=0.0, hhi=0.0)

    # Raw inverse-vol weights
    inv_vols = {k: 1.0 / v for k, v in valid.items()}
    total_inv = sum(inv_vols.values())

    raw_weights = {k: iv / total_inv for k, iv in inv_vols.items()}

    # Clamp and re-normalize (iterate twice to stabilize)
    clamped = dict(raw_weights)
    for _ in range(3):
        for k in clamped:
            clamped[k] = max(min_weight, min(clamped[k], max_weight))
        total_clamped = sum(clamped.values())
        if total_clamped > 0.0:
            clamped = {k: v / total_clamped for k, v in clamped.items()}

    total_weight = sum(clamped.values())
    hhi = sum(w * w for w in clamped.values())

    allocations = [
        RiskParityAllocation(
            instrument=k,
            volatility=valid[k],
            raw_weight=round(raw_weights[k], 6),
            clamped_weight=round(clamped[k], 6),
            target_risk_usd=round(equity * clamped[k], 2),
        )
        for k in sorted(valid.keys())
    ]

    return RiskParityResult(
        allocations=allocations,
        total_weight=round(total_weight, 6),
        hhi=round(hhi, 6),
    )


# ---------------------------------------------------------------------------
# Target-volatility position sizing
# ---------------------------------------------------------------------------


def target_vol_position_size(
    equity: float,
    instrument_vol: float,
    target_portfolio_vol: float = 0.10,
    n_instruments: int = 1,
    pip_size: float = 0.0001,
    pip_value_per_lot: float = 10.0,
    current_price: float = 1.0,
) -> float:
    """Compute lot size to achieve target volatility contribution.

    per_instrument_vol = target_portfolio_vol / sqrt(n_instruments)
    risk_usd = equity * per_instrument_vol
    lots = risk_usd / (instrument_vol * current_price / pip_size * pip_value_per_lot)

    Args:
        equity: Account equity in USD.
        instrument_vol: Annualized volatility of the instrument (decimal).
        target_portfolio_vol: Target portfolio volatility (default 10 %).
        n_instruments: Number of instruments in portfolio (default 1).
        pip_size: Value of one pip in price terms.
        pip_value_per_lot: Dollar value of one pip per standard lot.
        current_price: Current instrument price.

    Returns:
        Lot size (>= 0.0).  Returns 0.0 on invalid inputs.
    """
    if (
        equity <= 0.0
        or instrument_vol <= 0.0
        or n_instruments < 1
        or pip_size <= 0.0
        or pip_value_per_lot <= 0.0
        or current_price <= 0.0
    ):
        return 0.0

    per_inst_vol = target_portfolio_vol / math.sqrt(n_instruments)
    risk_usd = equity * per_inst_vol

    # Risk per lot = vol * price expressed in pips * pip_value
    risk_per_lot = instrument_vol * (current_price / pip_size) * pip_value_per_lot
    if risk_per_lot <= 0.0:
        return 0.0

    return risk_usd / risk_per_lot


# ---------------------------------------------------------------------------
# Equal risk contribution (approximate)
# ---------------------------------------------------------------------------


def equal_risk_contribution(
    volatilities: dict[str, float],
    correlations: dict[tuple[str, str], float] | None = None,
) -> dict[str, float]:
    """Approximate equal risk contribution weights.

    Simple version (no correlation): same as inverse_vol.
    With correlation: iterative adjustment (3 iterations of:
      marginal_risk_i = w_i * vol_i * sum(w_j * vol_j * corr_ij)
      adjust w_i to equalize marginal_risk across instruments).

    Args:
        volatilities: Mapping of instrument -> annualized volatility.
        correlations: Optional mapping of (inst_a, inst_b) -> correlation.
            Pairs stored alphabetically.

    Returns:
        Dict of instrument -> weight.  Empty dict on invalid input.
    """
    valid = {k: v for k, v in volatilities.items() if v > 0.0}
    if not valid:
        return {}

    instruments = sorted(valid.keys())
    n = len(instruments)

    # Start with inverse-vol weights
    inv_vols = {k: 1.0 / valid[k] for k in instruments}
    total_inv = sum(inv_vols.values())
    weights = {k: inv_vols[k] / total_inv for k in instruments}

    if correlations is None or n < 2:
        return weights

    def _get_corr(a: str, b: str) -> float:
        if a == b:
            return 1.0
        pair = (a, b) if a < b else (b, a)
        return correlations.get(pair, 0.0)

    # Iterative ERC adjustment (3 rounds)
    for _ in range(3):
        marginal_risks: dict[str, float] = {}
        for i_inst in instruments:
            mr = 0.0
            for j_inst in instruments:
                mr += (
                    weights[j_inst]
                    * valid[j_inst]
                    * _get_corr(i_inst, j_inst)
                )
            marginal_risks[i_inst] = weights[i_inst] * valid[i_inst] * mr

        total_mr = sum(marginal_risks.values())
        if total_mr <= 0.0:
            break

        target_mr = total_mr / n
        for inst in instruments:
            if marginal_risks[inst] > 0.0:
                weights[inst] *= target_mr / marginal_risks[inst]

        # Re-normalize
        total_w = sum(weights.values())
        if total_w > 0.0:
            weights = {k: v / total_w for k, v in weights.items()}

    return weights
