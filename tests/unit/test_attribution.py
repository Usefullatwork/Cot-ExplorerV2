"""Unit tests for src.analysis.attribution — Brinson-style return decomposition."""

from __future__ import annotations

import pytest

from src.analysis.attribution import (
    Attribution,
    RegimeAttribution,
    SignalAttribution,
    SizingAttribution,
    TimingAttribution,
    attribute_by_regime,
    attribute_by_signal,
    attribute_by_sizing,
    attribute_by_timing,
    compute_full_attribution,
)

# ---------------------------------------------------------------------------
# Fixture: realistic trade dataset (~20 trades)
# ---------------------------------------------------------------------------

_SIGNAL_KEYS = ["sma200", "momentum_20d", "cot_confirms", "cot_strong", "at_level_now"]


def _make_trade(
    instrument: str,
    direction: str,
    entry: float,
    exit_: float,
    pnl_pips: float,
    pnl_usd: float,
    lot_size: float,
    regime: str,
    flags: dict[str, bool],
) -> dict:
    return {
        "instrument": instrument,
        "direction": direction,
        "entry_price": entry,
        "exit_price": exit_,
        "pnl_pips": pnl_pips,
        "pnl_usd": pnl_usd,
        "lot_size": lot_size,
        "regime": regime,
        "grade": "A" if pnl_usd > 0 else "C",
        "score": 12,
        "signal_flags": flags,
    }


def _flags(**overrides: bool) -> dict[str, bool]:
    base = {k: False for k in _SIGNAL_KEYS}
    base.update(overrides)
    return base


@pytest.fixture()
def sample_trades() -> list[dict]:
    """20 trades across 3 instruments, 3 regimes, varying lot sizes."""
    return [
        # Winners with sma200 + momentum active
        _make_trade("EURUSD", "long", 1.0950, 1.0985, 35.0, 350.0, 0.10, "normal", _flags(sma200=True, momentum_20d=True)),
        _make_trade("EURUSD", "long", 1.0900, 1.0960, 60.0, 600.0, 0.10, "normal", _flags(sma200=True, momentum_20d=True, cot_confirms=True)),
        _make_trade("Gold", "long", 2350.0, 2375.0, 250.0, 500.0, 0.20, "normal", _flags(sma200=True, at_level_now=True)),
        _make_trade("SPX", "long", 5200.0, 5250.0, 50.0, 500.0, 0.50, "normal", _flags(sma200=True, momentum_20d=True, cot_confirms=True)),
        # Winners with cot_strong active (big lots)
        _make_trade("EURUSD", "long", 1.0880, 1.0930, 50.0, 750.0, 0.15, "normal", _flags(cot_strong=True, cot_confirms=True)),
        _make_trade("Gold", "long", 2300.0, 2340.0, 400.0, 800.0, 0.20, "risk_off", _flags(cot_strong=True, sma200=True)),
        # Losers with sma200 only (no momentum)
        _make_trade("EURUSD", "long", 1.1000, 1.0970, -30.0, -300.0, 0.10, "normal", _flags(sma200=True)),
        _make_trade("SPX", "short", 5300.0, 5320.0, -20.0, -200.0, 0.10, "normal", _flags(sma200=True)),
        # Losers with momentum only
        _make_trade("Gold", "long", 2400.0, 2380.0, -200.0, -400.0, 0.20, "crisis", _flags(momentum_20d=True)),
        _make_trade("EURUSD", "short", 1.1050, 1.1080, -30.0, -300.0, 0.10, "crisis", _flags(momentum_20d=True)),
        # Winners in risk_off regime
        _make_trade("Gold", "long", 2320.0, 2360.0, 400.0, 800.0, 0.20, "risk_off", _flags(sma200=True, cot_confirms=True, at_level_now=True)),
        _make_trade("EURUSD", "long", 1.0850, 1.0890, 40.0, 400.0, 0.10, "risk_off", _flags(sma200=True, momentum_20d=True)),
        # Losers in crisis regime (small lots)
        _make_trade("SPX", "long", 5100.0, 5060.0, -40.0, -200.0, 0.05, "crisis", _flags(at_level_now=True)),
        _make_trade("Gold", "short", 2420.0, 2450.0, -300.0, -150.0, 0.05, "crisis", _flags()),
        # Mixed — no signals active (losers)
        _make_trade("EURUSD", "long", 1.1020, 1.0990, -30.0, -300.0, 0.10, "normal", _flags()),
        _make_trade("SPX", "short", 5250.0, 5270.0, -20.0, -100.0, 0.05, "normal", _flags()),
        # Big winner with large lot in normal
        _make_trade("Gold", "long", 2280.0, 2330.0, 500.0, 2500.0, 0.50, "normal", _flags(sma200=True, momentum_20d=True, cot_confirms=True, cot_strong=True, at_level_now=True)),
        # Small winner in risk_off
        _make_trade("EURUSD", "long", 1.0820, 1.0835, 15.0, 150.0, 0.10, "risk_off", _flags(sma200=True)),
        # Loser with all signals (crisis)
        _make_trade("EURUSD", "short", 1.1100, 1.1140, -40.0, -400.0, 0.10, "crisis", _flags(sma200=True, momentum_20d=True, cot_confirms=True, cot_strong=True, at_level_now=True)),
        # Break-even trade
        _make_trade("SPX", "long", 5200.0, 5200.0, 0.0, 0.0, 0.10, "normal", _flags(sma200=True)),
    ]


# ===== Signal attribution ====================================================


class TestAttributeBySignal:
    """attribute_by_signal splits trades and computes marginal contribution."""

    def test_sma200_positive_marginal(self, sample_trades):
        """sma200 is active mostly on winners -> positive marginal contribution."""
        attrs = attribute_by_signal(sample_trades)
        sma = next(a for a in attrs if a.signal_id == "sma200")
        assert sma.trades_with_signal > 0
        assert sma.trades_without_signal > 0
        # sma200 active on many winners + the big lot winner
        assert sma.trades_with_signal + sma.trades_without_signal == 20

    def test_no_signal_flags_trades_counted_in_without(self, sample_trades):
        """Trades with all signals False are counted in 'without' group."""
        attrs = attribute_by_signal(sample_trades)
        cot_strong = next(a for a in attrs if a.signal_id == "cot_strong")
        # cot_strong is True on only a few trades
        assert cot_strong.trades_with_signal < cot_strong.trades_without_signal

    def test_uniform_signals_zero_marginal(self):
        """If all trades have the same signal state, marginal contribution ~0."""
        trades = [
            _make_trade("EURUSD", "long", 1.09, 1.10, 100, 100, 0.1, "normal", _flags(sma200=True)),
            _make_trade("EURUSD", "long", 1.09, 1.08, -100, -100, 0.1, "normal", _flags(sma200=True)),
        ]
        attrs = attribute_by_signal(trades)
        sma = next(a for a in attrs if a.signal_id == "sma200")
        # All trades have sma200=True, so avg_without = 0 (no trades), marginal = avg_with - 0
        assert sma.trades_without_signal == 0

    def test_custom_signal_ids(self, sample_trades):
        """signal_ids parameter filters to requested signals only."""
        attrs = attribute_by_signal(sample_trades, signal_ids=["sma200", "cot_strong"])
        assert len(attrs) == 2
        ids = {a.signal_id for a in attrs}
        assert ids == {"sma200", "cot_strong"}

    def test_sorted_by_marginal_desc(self, sample_trades):
        """Results are sorted by marginal_contribution descending."""
        attrs = attribute_by_signal(sample_trades)
        marginals = [a.marginal_contribution for a in attrs]
        assert marginals == sorted(marginals, reverse=True)

    def test_total_contribution_sums_pnl_with(self, sample_trades):
        """total_contribution equals the sum of PnL for trades where signal active."""
        attrs = attribute_by_signal(sample_trades, signal_ids=["cot_strong"])
        cot = attrs[0]
        expected = sum(
            t["pnl_usd"]
            for t in sample_trades
            if t["signal_flags"].get("cot_strong", False)
        )
        assert abs(cot.total_contribution - expected) < 1e-6


class TestAttributeBySignalEdgeCases:
    """Edge cases for attribute_by_signal."""

    def test_empty_trades_raises(self):
        """Empty trade list raises ValueError."""
        with pytest.raises(ValueError, match="must not be empty"):
            attribute_by_signal([])

    def test_single_trade(self):
        """Single trade produces valid attribution."""
        trade = _make_trade("EURUSD", "long", 1.09, 1.10, 100, 1000, 0.1, "normal", _flags(sma200=True))
        attrs = attribute_by_signal([trade])
        sma = next(a for a in attrs if a.signal_id == "sma200")
        assert sma.trades_with_signal == 1
        assert sma.trades_without_signal == 0
        assert sma.avg_pnl_with == 1000.0

    def test_missing_signal_flags_raises(self):
        """Trade without signal_flags raises KeyError."""
        trade = {"pnl_usd": 100}
        with pytest.raises(KeyError):
            attribute_by_signal([trade])


# ===== Timing attribution =====================================================


class TestAttributeByTiming:
    """attribute_by_timing computes entry/exit efficiency."""

    def test_efficiency_in_range(self, sample_trades):
        """Entry and exit efficiency are both between 0 and 1."""
        timing = attribute_by_timing(sample_trades)
        assert 0.0 <= timing.avg_entry_efficiency <= 1.0
        assert 0.0 <= timing.avg_exit_efficiency <= 1.0

    def test_with_bar_data(self):
        """Bar data produces meaningful efficiency values."""
        trade = {
            "instrument": "EURUSD",
            "direction": "long",
            "entry_price": 1.0910,
            "exit_price": 1.0960,
            "pnl_pips": 50.0,
            "pnl_usd": 500.0,
            "lot_size": 0.1,
            "regime": "normal",
            "signal_flags": _flags(sma200=True),
            "entry_bar_high": 1.0950,
            "entry_bar_low": 1.0900,
            "exit_bar_high": 1.0970,
            "exit_bar_low": 1.0940,
        }
        timing = attribute_by_timing([trade])
        # Entry at 1.0910, bar low=1.0900, range=0.005
        # Long entry efficiency = 1 - (1.0910 - 1.0900) / 0.005 = 1 - 0.2 = 0.8
        assert abs(timing.avg_entry_efficiency - 0.8) < 0.01
        # Exit at 1.0960, bar low=1.0940, range=0.003
        # Long exit efficiency = (1.0960 - 1.0940) / 0.003 = 0.667
        assert abs(timing.avg_exit_efficiency - 0.667) < 0.01

    def test_empty_raises(self):
        """Empty trade list raises ValueError."""
        with pytest.raises(ValueError, match="must not be empty"):
            attribute_by_timing([])

    def test_breakeven_trade(self):
        """Zero-move trade returns 0.5 efficiency (neutral)."""
        trade = _make_trade("SPX", "long", 5200.0, 5200.0, 0.0, 0.0, 0.1, "normal", _flags())
        timing = attribute_by_timing([trade])
        assert timing.avg_entry_efficiency == 0.5


# ===== Sizing attribution =====================================================


class TestAttributeBySizing:
    """attribute_by_sizing compares actual vs equal-weight."""

    def test_large_lots_on_winners_positive_alpha(self):
        """Big lots on winners + small lots on losers -> positive sizing alpha."""
        trades = [
            _make_trade("EURUSD", "long", 1.09, 1.10, 100, 1000, 0.50, "normal", _flags()),
            _make_trade("EURUSD", "long", 1.10, 1.09, -100, -100, 0.05, "normal", _flags()),
        ]
        sizing = attribute_by_sizing(trades)
        assert sizing.actual_total_pnl == 900.0
        assert sizing.sizing_alpha > 0

    def test_equal_lots_zero_alpha(self):
        """All trades with same lot size -> sizing alpha = 0."""
        trades = [
            _make_trade("EURUSD", "long", 1.09, 1.10, 100, 1000, 0.10, "normal", _flags()),
            _make_trade("EURUSD", "long", 1.10, 1.09, -100, -1000, 0.10, "normal", _flags()),
        ]
        sizing = attribute_by_sizing(trades)
        assert abs(sizing.sizing_alpha) < 1e-6
        assert abs(sizing.sizing_alpha_pct) < 1e-6

    def test_sizing_alpha_pct_computed(self):
        """sizing_alpha_pct = sizing_alpha / abs(equal_size_pnl) * 100."""
        trades = [
            _make_trade("EURUSD", "long", 1.09, 1.10, 100, 2000, 0.20, "normal", _flags()),
            _make_trade("EURUSD", "long", 1.10, 1.09, -100, -500, 0.05, "normal", _flags()),
        ]
        sizing = attribute_by_sizing(trades)
        if abs(sizing.equal_size_pnl) > 1e-10:
            expected_pct = sizing.sizing_alpha / abs(sizing.equal_size_pnl) * 100
            assert abs(sizing.sizing_alpha_pct - expected_pct) < 1e-6

    def test_empty_raises(self):
        """Empty trade list raises ValueError."""
        with pytest.raises(ValueError, match="must not be empty"):
            attribute_by_sizing([])

    def test_single_trade_zero_alpha(self):
        """Single trade: equal lot = actual lot, so alpha = 0."""
        trade = _make_trade("EURUSD", "long", 1.09, 1.10, 100, 1000, 0.10, "normal", _flags())
        sizing = attribute_by_sizing([trade])
        assert abs(sizing.sizing_alpha) < 1e-6


# ===== Regime attribution =====================================================


class TestAttributeByRegime:
    """attribute_by_regime groups trades by regime."""

    def test_regime_count(self, sample_trades):
        """Sample data has 3 distinct regimes."""
        attrs = attribute_by_regime(sample_trades)
        regimes = {a.regime for a in attrs}
        assert regimes == {"normal", "risk_off", "crisis"}

    def test_n_trades_sum(self, sample_trades):
        """Total n_trades across regimes equals total trade count."""
        attrs = attribute_by_regime(sample_trades)
        total = sum(a.n_trades for a in attrs)
        assert total == len(sample_trades)

    def test_pnl_contribution_sums_near_100(self, sample_trades):
        """pnl_contribution_pct across all regimes sums to ~100%."""
        attrs = attribute_by_regime(sample_trades)
        total_pct = sum(a.pnl_contribution_pct for a in attrs)
        assert abs(total_pct - 100.0) < 0.01

    def test_win_rate_in_range(self, sample_trades):
        """Win rate is between 0 and 1 for all regimes."""
        attrs = attribute_by_regime(sample_trades)
        for attr in attrs:
            assert 0.0 <= attr.win_rate <= 1.0

    def test_avg_pnl_correct(self, sample_trades):
        """avg_pnl = total_pnl / n_trades for each regime."""
        attrs = attribute_by_regime(sample_trades)
        for attr in attrs:
            assert abs(attr.avg_pnl - attr.total_pnl / attr.n_trades) < 1e-6

    def test_sorted_by_total_pnl_desc(self, sample_trades):
        """Results sorted by total_pnl descending."""
        attrs = attribute_by_regime(sample_trades)
        totals = [a.total_pnl for a in attrs]
        assert totals == sorted(totals, reverse=True)

    def test_empty_raises(self):
        """Empty trade list raises ValueError."""
        with pytest.raises(ValueError, match="must not be empty"):
            attribute_by_regime([])

    def test_all_winners_win_rate_one(self):
        """All winning trades -> win_rate = 1.0."""
        trades = [
            _make_trade("EURUSD", "long", 1.09, 1.10, 100, 1000, 0.1, "normal", _flags()),
            _make_trade("EURUSD", "long", 1.09, 1.10, 100, 1000, 0.1, "normal", _flags()),
        ]
        attrs = attribute_by_regime(trades)
        assert attrs[0].win_rate == 1.0

    def test_all_losers_win_rate_zero(self):
        """All losing trades -> win_rate = 0.0."""
        trades = [
            _make_trade("EURUSD", "long", 1.10, 1.09, -100, -1000, 0.1, "normal", _flags()),
            _make_trade("EURUSD", "long", 1.10, 1.09, -100, -1000, 0.1, "normal", _flags()),
        ]
        attrs = attribute_by_regime(trades)
        assert attrs[0].win_rate == 0.0


# ===== Full attribution =======================================================


class TestComputeFullAttribution:
    """compute_full_attribution integration test."""

    def test_all_fields_populated(self, sample_trades):
        """Full attribution has all fields set with correct types."""
        result = compute_full_attribution(sample_trades)
        assert isinstance(result, Attribution)
        assert isinstance(result.total_pnl, float)
        assert result.total_trades == 20
        assert len(result.signal_attributions) == len(_SIGNAL_KEYS)
        assert isinstance(result.timing, TimingAttribution)
        assert isinstance(result.sizing, SizingAttribution)
        assert len(result.regime_attributions) >= 1
        assert isinstance(result.top_signal, str)
        assert isinstance(result.worst_signal, str)
        assert isinstance(result.best_regime, str)

    def test_total_pnl_matches(self, sample_trades):
        """total_pnl matches sum of all trade pnl_usd."""
        result = compute_full_attribution(sample_trades)
        expected = sum(t["pnl_usd"] for t in sample_trades)
        assert abs(result.total_pnl - expected) < 1e-6

    def test_top_signal_has_highest_marginal(self, sample_trades):
        """top_signal is the one with highest marginal contribution."""
        result = compute_full_attribution(sample_trades)
        marginals = {a.signal_id: a.marginal_contribution for a in result.signal_attributions}
        best_id = max(marginals, key=marginals.get)
        assert result.top_signal == best_id

    def test_worst_signal_has_lowest_marginal(self, sample_trades):
        """worst_signal is the one with lowest marginal contribution."""
        result = compute_full_attribution(sample_trades)
        marginals = {a.signal_id: a.marginal_contribution for a in result.signal_attributions}
        worst_id = min(marginals, key=marginals.get)
        assert result.worst_signal == worst_id

    def test_best_regime_has_highest_avg_pnl(self, sample_trades):
        """best_regime is the one with highest avg_pnl."""
        result = compute_full_attribution(sample_trades)
        best = max(result.regime_attributions, key=lambda r: r.avg_pnl)
        assert result.best_regime == best.regime

    def test_empty_raises(self):
        """Empty trade list raises ValueError."""
        with pytest.raises(ValueError, match="must not be empty"):
            compute_full_attribution([])

    def test_custom_signal_ids_passed_through(self, sample_trades):
        """signal_ids parameter is forwarded to attribute_by_signal."""
        result = compute_full_attribution(sample_trades, signal_ids=["sma200"])
        assert len(result.signal_attributions) == 1
        assert result.signal_attributions[0].signal_id == "sma200"
        assert result.top_signal == "sma200"
        assert result.worst_signal == "sma200"
