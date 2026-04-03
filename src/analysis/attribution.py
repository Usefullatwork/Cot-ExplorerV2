"""Performance attribution — Brinson-style return decomposition.

Decomposes trading PnL into four dimensions:
  1. Signal attribution: which of the 19 scoring signals drive profits
  2. Timing attribution: entry/exit quality vs random
  3. Sizing attribution: position sizing alpha vs equal-weight
  4. Regime attribution: per-regime performance breakdown

All functions are pure: no DB, no HTTP, no side effects.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SignalAttribution:
    """PnL contribution of a single signal criterion."""

    signal_id: str
    trades_with_signal: int
    trades_without_signal: int
    avg_pnl_with: float
    avg_pnl_without: float
    marginal_contribution: float
    total_contribution: float


@dataclass(frozen=True)
class TimingAttribution:
    """Entry timing quality analysis."""

    avg_entry_efficiency: float
    avg_exit_efficiency: float
    timing_alpha_pips: float


@dataclass(frozen=True)
class SizingAttribution:
    """Position sizing contribution analysis."""

    actual_total_pnl: float
    equal_size_pnl: float
    sizing_alpha: float
    sizing_alpha_pct: float


@dataclass(frozen=True)
class RegimeAttribution:
    """Per-regime performance breakdown."""

    regime: str
    n_trades: int
    total_pnl: float
    avg_pnl: float
    win_rate: float
    pnl_contribution_pct: float


@dataclass(frozen=True)
class Attribution:
    """Complete performance attribution report."""

    total_pnl: float
    total_trades: int
    signal_attributions: list[SignalAttribution]
    timing: TimingAttribution
    sizing: SizingAttribution
    regime_attributions: list[RegimeAttribution]
    top_signal: str
    worst_signal: str
    best_regime: str


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _require_trades(trades: Sequence[dict]) -> None:
    """Raise ValueError if trades is empty."""
    if not trades:
        raise ValueError("trades must not be empty")


def _safe_mean(values: Sequence[float]) -> float:
    """Return mean of values, or 0.0 if empty."""
    if not values:
        return 0.0
    return sum(values) / len(values)


def _get_pnl(trade: dict) -> float:
    """Extract PnL from trade dict, preferring pnl_usd then pnl_pips."""
    if "pnl_usd" in trade:
        return float(trade["pnl_usd"])
    if "pnl_pips" in trade:
        return float(trade["pnl_pips"])
    raise KeyError("trade must have 'pnl_usd' or 'pnl_pips'")


# ---------------------------------------------------------------------------
# Signal attribution
# ---------------------------------------------------------------------------


def attribute_by_signal(
    trades: Sequence[dict],
    signal_ids: Sequence[str] | None = None,
) -> list[SignalAttribution]:
    """Compute per-signal PnL contribution.

    For each signal criterion:
    1. Split trades into "signal active" vs "signal inactive" groups
    2. Compare average PnL in each group
    3. marginal_contribution = avg_pnl_with - avg_pnl_without
    4. total_contribution = sum of PnL on trades where signal active

    Args:
        trades: Sequence of trade dicts with 'pnl_usd' (or 'pnl_pips')
            and 'signal_flags' dict.
        signal_ids: Signals to analyze. Defaults to all keys found in the
            first trade's signal_flags.

    Returns:
        List of SignalAttribution, one per signal, sorted by marginal
        contribution descending.

    Raises:
        ValueError: If trades is empty.
        KeyError: If a trade lacks 'signal_flags'.
    """
    _require_trades(trades)

    if signal_ids is None:
        first_flags = trades[0].get("signal_flags")
        if not first_flags:
            raise KeyError("first trade must have 'signal_flags'")
        signal_ids = list(first_flags.keys())

    results: list[SignalAttribution] = []
    for sig_id in signal_ids:
        pnl_with: list[float] = []
        pnl_without: list[float] = []

        for trade in trades:
            flags = trade.get("signal_flags", {})
            pnl = _get_pnl(trade)
            if flags.get(sig_id, False):
                pnl_with.append(pnl)
            else:
                pnl_without.append(pnl)

        avg_with = _safe_mean(pnl_with)
        avg_without = _safe_mean(pnl_without)

        results.append(SignalAttribution(
            signal_id=sig_id,
            trades_with_signal=len(pnl_with),
            trades_without_signal=len(pnl_without),
            avg_pnl_with=avg_with,
            avg_pnl_without=avg_without,
            marginal_contribution=avg_with - avg_without,
            total_contribution=sum(pnl_with),
        ))

    results.sort(key=lambda s: s.marginal_contribution, reverse=True)
    return results


# ---------------------------------------------------------------------------
# Timing attribution
# ---------------------------------------------------------------------------


def _compute_entry_efficiency(trade: dict) -> float:
    """Compute entry efficiency for a single trade (0-1).

    With bar data: measures how close entry was to optimal within the bar.
    Without bar data: simplified measure based on direction and price move.
    """
    direction = trade.get("direction", "long").lower()
    entry = float(trade["entry_price"])
    exit_ = float(trade["exit_price"])

    # With bar data
    bar_high = trade.get("entry_bar_high")
    bar_low = trade.get("entry_bar_low")
    if bar_high is not None and bar_low is not None:
        bar_high = float(bar_high)
        bar_low = float(bar_low)
        bar_range = bar_high - bar_low
        if bar_range <= 0:
            return 0.5
        if direction in ("long", "bull", "bullish"):
            return 1.0 - (entry - bar_low) / bar_range
        return (entry - bar_low) / bar_range

    # Simplified: ratio of favorable entry within total move
    move = abs(exit_ - entry)
    if move == 0:
        return 0.5
    return min(1.0, max(0.0, move / (move + move * 0.5)))


def _compute_exit_efficiency(trade: dict) -> float:
    """Compute exit efficiency for a single trade (0-1).

    With bar data: measures how close exit was to optimal within the bar.
    Without bar data: simplified using PnL direction.
    """
    direction = trade.get("direction", "long").lower()
    exit_ = float(trade["exit_price"])

    bar_high = trade.get("exit_bar_high")
    bar_low = trade.get("exit_bar_low")
    if bar_high is not None and bar_low is not None:
        bar_high = float(bar_high)
        bar_low = float(bar_low)
        bar_range = bar_high - bar_low
        if bar_range <= 0:
            return 0.5
        if direction in ("long", "bull", "bullish"):
            return (exit_ - bar_low) / bar_range
        return 1.0 - (exit_ - bar_low) / bar_range

    # Simplified: positive PnL implies decent exit
    pnl_pips = float(trade.get("pnl_pips", 0))
    if pnl_pips == 0:
        return 0.5
    # Normalize: bigger win = better exit, capped at 1.0
    entry = float(trade["entry_price"])
    move = abs(float(trade["exit_price"]) - entry)
    if move == 0:
        return 0.5
    if pnl_pips > 0:
        return min(1.0, max(0.0, abs(pnl_pips) / (abs(pnl_pips) * 1.5)))
    return max(0.0, 0.5 - abs(pnl_pips) / (abs(pnl_pips) * 4))


def attribute_by_timing(
    trades: Sequence[dict],
) -> TimingAttribution:
    """Analyze entry/exit timing quality.

    For each trade computes entry and exit efficiency (0-1) and estimates
    timing alpha in pips (actual PnL vs midpoint-entry PnL).

    Args:
        trades: Sequence of trade dicts with entry_price, exit_price,
            direction, pnl_pips. Optional: entry_bar_high, entry_bar_low,
            exit_bar_high, exit_bar_low.

    Returns:
        TimingAttribution with averaged efficiencies and total timing alpha.

    Raises:
        ValueError: If trades is empty.
    """
    _require_trades(trades)

    entry_effs: list[float] = []
    exit_effs: list[float] = []
    alpha_pips: list[float] = []

    for trade in trades:
        entry_effs.append(_compute_entry_efficiency(trade))
        exit_effs.append(_compute_exit_efficiency(trade))

        pnl = float(trade.get("pnl_pips", 0))
        entry = float(trade["entry_price"])
        exit_ = float(trade["exit_price"])
        direction = trade.get("direction", "long").lower()

        # Timing alpha: actual pips vs random-entry pips (midpoint estimate)
        midpoint = (entry + exit_) / 2
        if direction in ("long", "bull", "bullish"):
            random_pnl = exit_ - midpoint
        else:
            random_pnl = midpoint - exit_

        alpha_pips.append(pnl - random_pnl)

    return TimingAttribution(
        avg_entry_efficiency=_safe_mean(entry_effs),
        avg_exit_efficiency=_safe_mean(exit_effs),
        timing_alpha_pips=sum(alpha_pips),
    )


# ---------------------------------------------------------------------------
# Sizing attribution
# ---------------------------------------------------------------------------


def attribute_by_sizing(
    trades: Sequence[dict],
) -> SizingAttribution:
    """Compare actual sizing vs equal-weight sizing.

    Computes what PnL would have been if all trades used the average
    lot size, then calculates the alpha from actual position sizing.

    Args:
        trades: Sequence of trade dicts with pnl_usd, pnl_pips, lot_size.

    Returns:
        SizingAttribution comparing actual vs equal-weight PnL.

    Raises:
        ValueError: If trades is empty.
    """
    _require_trades(trades)

    actual_total = 0.0
    lot_sizes: list[float] = []
    pnl_per_pip_list: list[tuple[float, float]] = []  # (pnl_pips, pnl_per_pip)

    for trade in trades:
        pnl_usd = float(trade["pnl_usd"])
        pnl_pips = float(trade["pnl_pips"])
        lot_size = float(trade["lot_size"])

        actual_total += pnl_usd
        lot_sizes.append(lot_size)

        if pnl_pips != 0 and lot_size != 0:
            pnl_per_pip = pnl_usd / pnl_pips
            pip_per_lot = pnl_per_pip / lot_size
            pnl_per_pip_list.append((pnl_pips, pip_per_lot))
        else:
            pnl_per_pip_list.append((pnl_pips, 0.0))

    avg_lot = _safe_mean(lot_sizes)

    equal_pnl = 0.0
    for pnl_pips, pip_per_lot in pnl_per_pip_list:
        equal_pnl += pnl_pips * pip_per_lot * avg_lot

    sizing_alpha = actual_total - equal_pnl
    if abs(equal_pnl) > 1e-10:
        sizing_alpha_pct = sizing_alpha / abs(equal_pnl) * 100
    else:
        sizing_alpha_pct = 0.0

    return SizingAttribution(
        actual_total_pnl=actual_total,
        equal_size_pnl=equal_pnl,
        sizing_alpha=sizing_alpha,
        sizing_alpha_pct=sizing_alpha_pct,
    )


# ---------------------------------------------------------------------------
# Regime attribution
# ---------------------------------------------------------------------------


def attribute_by_regime(
    trades: Sequence[dict],
) -> list[RegimeAttribution]:
    """Per-regime performance breakdown.

    Groups trades by 'regime' field and computes per-group stats
    including total PnL, average PnL, win rate, and PnL contribution %.

    Args:
        trades: Sequence of trade dicts with pnl_usd and regime.

    Returns:
        List of RegimeAttribution sorted by total_pnl descending.

    Raises:
        ValueError: If trades is empty.
    """
    _require_trades(trades)

    groups: dict[str, list[float]] = {}
    for trade in trades:
        regime = trade.get("regime", "unknown")
        pnl = _get_pnl(trade)
        groups.setdefault(regime, []).append(pnl)

    total_pnl = sum(_get_pnl(t) for t in trades)
    abs_total = abs(total_pnl) if abs(total_pnl) > 1e-10 else 1.0

    results: list[RegimeAttribution] = []
    for regime, pnls in groups.items():
        n = len(pnls)
        regime_total = sum(pnls)
        wins = sum(1 for p in pnls if p > 0)

        results.append(RegimeAttribution(
            regime=regime,
            n_trades=n,
            total_pnl=regime_total,
            avg_pnl=regime_total / n,
            win_rate=wins / n,
            pnl_contribution_pct=regime_total / abs_total * 100,
        ))

    results.sort(key=lambda r: r.total_pnl, reverse=True)
    return results


# ---------------------------------------------------------------------------
# Full attribution
# ---------------------------------------------------------------------------


def compute_full_attribution(
    trades: Sequence[dict],
    signal_ids: Sequence[str] | None = None,
) -> Attribution:
    """Complete Brinson-style attribution combining all four dimensions.

    Calls all four attribution functions and assembles the full report
    with identification of top/worst signals and best regime.

    Args:
        trades: Sequence of trade dicts.
        signal_ids: Optional list of signal IDs to analyze.

    Returns:
        Attribution dataclass with all four decompositions.

    Raises:
        ValueError: If trades is empty.
    """
    _require_trades(trades)

    signal_attrs = attribute_by_signal(trades, signal_ids)
    timing = attribute_by_timing(trades)
    sizing = attribute_by_sizing(trades)
    regime_attrs = attribute_by_regime(trades)

    total_pnl = sum(_get_pnl(t) for t in trades)

    # Top and worst signal by marginal contribution (already sorted desc)
    top_signal = signal_attrs[0].signal_id if signal_attrs else ""
    worst_signal = signal_attrs[-1].signal_id if signal_attrs else ""

    # Best regime by avg PnL
    best_regime = max(regime_attrs, key=lambda r: r.avg_pnl).regime

    return Attribution(
        total_pnl=total_pnl,
        total_trades=len(trades),
        signal_attributions=signal_attrs,
        timing=timing,
        sizing=sizing,
        regime_attributions=regime_attrs,
        top_signal=top_signal,
        worst_signal=worst_signal,
        best_regime=best_regime,
    )
