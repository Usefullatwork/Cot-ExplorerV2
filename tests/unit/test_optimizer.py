"""Unit tests for src.trading.backtesting.optimizer — scoring, windows, strategy build, ranking."""

from __future__ import annotations

from typing import Any

import pytest

from src.trading.backtesting.optimizer import (
    W_DRAWDOWN,
    W_PROFIT_FACTOR,
    W_SHARPE,
    W_WIN_RATE,
    _build_strategy,
    _generate_windows,
    score_result,
)
from src.trading.backtesting.strategies.cot_momentum import COTMomentumStrategy
from src.trading.backtesting.strategies.macro_regime import MacroRegimeStrategy
from src.trading.backtesting.strategies.mean_reversion import MeanReversionStrategy
from src.trading.backtesting.strategies.smc_confluence import SMCConfluenceStrategy
from src.trading.backtesting.wfo_models import WindowResult

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _report(**overrides) -> dict[str, Any]:
    """Build a report dict with sensible defaults for score_result()."""
    base: dict[str, Any] = {
        "risk": {"sharpe_ratio": 0.0, "max_drawdown_pct": 0.0},
        "trades": {"win_rate": 0.0, "profit_factor": 0.0},
    }
    if "sharpe" in overrides:
        base["risk"]["sharpe_ratio"] = overrides.pop("sharpe")
    if "max_dd" in overrides:
        base["risk"]["max_drawdown_pct"] = overrides.pop("max_dd")
    if "win_rate" in overrides:
        base["trades"]["win_rate"] = overrides.pop("win_rate")
    if "profit_factor" in overrides:
        base["trades"]["profit_factor"] = overrides.pop("profit_factor")
    return base


def _monthly_dates(months: int, start_year: int = 2020, start_month: int = 1) -> list[str]:
    """Generate one date per month for the given number of months."""
    dates: list[str] = []
    y, m = start_year, start_month
    for _ in range(months):
        dates.append(f"{y}-{m:02d}-15")
        m += 1
        if m > 12:
            m = 1
            y += 1
    return dates


def _make_window_result(
    strategy: str = "COT Momentum",
    timeframe: str = "D1",
    is_train: bool = True,
    composite_score: float = 0.5,
    **metric_overrides,
) -> WindowResult:
    """Create a WindowResult for ranking/aggregation tests."""
    metrics = {
        "sharpe": 1.0,
        "win_rate": 55.0,
        "max_drawdown": 10.0,
        "profit_factor": 1.5,
        "total_trades": 20,
        "total_return_pct": 5.0,
    }
    metrics.update(metric_overrides)
    return WindowResult(
        window_start="2020-01-15",
        window_end="2020-08-15",
        is_train=is_train,
        strategy=strategy,
        timeframe=timeframe,
        params={"sl_atr_multiplier": 2.0, "tp_rr_ratio": 2.0},
        metrics=metrics,
        composite_score=composite_score,
    )


# ===========================================================================
# score_result tests
# ===========================================================================


class TestScoreResult:
    """Tests for the composite scoring function."""

    def test_score_result_all_zeros(self):
        """All metrics zero -> baseline score (not zero, because normalization shifts)."""
        report = _report(sharpe=0.0, win_rate=0.0, max_dd=0.0, profit_factor=0.0)
        score = score_result(report)
        # sharpe=0 -> norm=(0+2)/6=0.333; wr=0; dd=0->norm_dd=1.0; pf=0
        expected = W_SHARPE * (2.0 / 6.0) + W_WIN_RATE * 0.0 + W_DRAWDOWN * 1.0 + W_PROFIT_FACTOR * 0.0
        assert abs(score - expected) < 1e-9

    def test_score_result_perfect(self):
        """Sharpe=4, win_rate=100, dd=0, pf=5 -> max possible score ~1.0."""
        report = _report(sharpe=4.0, win_rate=100.0, max_dd=0.0, profit_factor=5.0)
        score = score_result(report)
        # All normalized components = 1.0
        expected = W_SHARPE * 1.0 + W_WIN_RATE * 1.0 + W_DRAWDOWN * 1.0 + W_PROFIT_FACTOR * 1.0
        assert abs(score - expected) < 1e-9
        assert abs(score - 1.0) < 1e-9

    def test_score_result_negative_sharpe(self):
        """Sharpe=-2 -> norm_sharpe=0 (bottom of range)."""
        report = _report(sharpe=-2.0, win_rate=50.0, max_dd=25.0, profit_factor=1.0)
        score = score_result(report)
        # norm_sharpe = (-2+2)/6 = 0.0
        norm_wr = 50.0 / 100.0
        norm_dd = 1.0 - 25.0 / 50.0
        norm_pf = 1.0 / 5.0
        expected = W_SHARPE * 0.0 + W_WIN_RATE * norm_wr + W_DRAWDOWN * norm_dd + W_PROFIT_FACTOR * norm_pf
        assert abs(score - expected) < 1e-9

    def test_score_result_clipping(self):
        """Sharpe > 4 clipped to 4; dd > 50 clipped to 50."""
        report = _report(sharpe=10.0, win_rate=200.0, max_dd=80.0, profit_factor=20.0)
        score = score_result(report)
        # All components clipped to their max then normalized to 1.0
        # sharpe=10 -> clipped 4 -> norm=1.0
        # win_rate=200 -> clipped 100 -> norm=1.0
        # dd=80 -> clipped 50 -> norm_dd=0.0
        # pf=20 -> clipped 5 -> norm=1.0
        expected = W_SHARPE * 1.0 + W_WIN_RATE * 1.0 + W_DRAWDOWN * 0.0 + W_PROFIT_FACTOR * 1.0
        assert abs(score - expected) < 1e-9

    def test_score_result_weights_sum_to_one(self):
        """Verify W_SHARPE + W_WIN_RATE + W_DRAWDOWN + W_PROFIT_FACTOR == 1.0."""
        total = W_SHARPE + W_WIN_RATE + W_DRAWDOWN + W_PROFIT_FACTOR
        assert abs(total - 1.0) < 1e-9


# ===========================================================================
# _generate_windows tests
# ===========================================================================


class TestGenerateWindows:
    """Tests for rolling window generation."""

    def test_generate_windows_normal(self):
        """24+ months of data -> multiple windows with train=6, test=2."""
        dates = _monthly_dates(36)  # 3 years
        windows = _generate_windows(dates, train_months=6, test_months=2)
        assert len(windows) >= 2
        for tr_s, tr_e, te_s, te_e in windows:
            assert tr_s < tr_e
            assert te_s == tr_e  # test starts where train ends
            assert te_s < te_e

    def test_generate_windows_too_short(self):
        """Data shorter than train+test -> empty list."""
        dates = _monthly_dates(5)  # 5 months < 6+2
        windows = _generate_windows(dates, train_months=6, test_months=2)
        assert windows == []

    def test_generate_windows_empty_dates(self):
        """Empty dates list -> empty output."""
        windows = _generate_windows([], train_months=6, test_months=2)
        assert windows == []

    def test_generate_windows_exact_fit(self):
        """Data exactly train+test months -> one window."""
        # 8 months = 6 train + 2 test exactly
        dates = _monthly_dates(9)  # 9 months gives enough span for 8-month window
        windows = _generate_windows(dates, train_months=6, test_months=2)
        assert len(windows) >= 1

    def test_generate_windows_all_dates_ordered(self):
        """All window boundaries are valid ISO date strings in chronological order."""
        dates = _monthly_dates(24)
        windows = _generate_windows(dates, train_months=6, test_months=2)
        for tr_s, tr_e, te_s, te_e in windows:
            assert tr_s < tr_e <= te_s < te_e


# ===========================================================================
# _build_strategy tests
# ===========================================================================


class TestBuildStrategy:
    """Tests for strategy instantiation from name + params."""

    def test_build_cot_momentum(self):
        """'COT Momentum' returns COTMomentumStrategy instance."""
        strat = _build_strategy("COT Momentum", {"sl_atr_multiplier": 2.0, "tp_rr_ratio": 1.5})
        assert isinstance(strat, COTMomentumStrategy)

    def test_build_smc_confluence(self):
        """'SMC Confluence' returns SMCConfluenceStrategy instance."""
        strat = _build_strategy("SMC Confluence", {"min_score": 6, "tp_rr_ratio": 2.0})
        assert isinstance(strat, SMCConfluenceStrategy)

    def test_build_mean_reversion(self):
        """'Mean Reversion' returns MeanReversionStrategy instance."""
        strat = _build_strategy("Mean Reversion", {"sl_atr_multiplier": 2.0, "candle_exit_bars": 8})
        assert isinstance(strat, MeanReversionStrategy)

    def test_build_macro_regime(self):
        """'Macro Regime' returns MacroRegimeStrategy instance."""
        strat = _build_strategy("Macro Regime", {"sl_atr_multiplier": 3.0})
        assert isinstance(strat, MacroRegimeStrategy)

    def test_build_unknown_raises_value_error(self):
        """Unknown strategy name raises ValueError."""
        with pytest.raises(ValueError, match="Unknown strategy"):
            _build_strategy("Nonexistent Strategy", {})


# ===========================================================================
# _aggregate_ranking tests
# ===========================================================================


class TestAggregateRanking:
    """Tests for ranking/aggregation via WalkForwardOptimizer._aggregate_ranking."""

    def test_aggregate_ranking_sorted_desc(self):
        """Results sorted by avg_test_score descending."""
        from src.trading.backtesting.optimizer import WalkForwardOptimizer

        opt = WalkForwardOptimizer(strategies=["COT Momentum"], timeframes=["D1"])

        test_results = [
            _make_window_result(strategy="COT Momentum", timeframe="D1", is_train=False, composite_score=0.8),
            _make_window_result(strategy="COT Momentum", timeframe="D1", is_train=False, composite_score=0.9),
            _make_window_result(strategy="SMC Confluence", timeframe="D1", is_train=False, composite_score=0.3),
        ]

        ranking = opt._aggregate_ranking(test_results)
        assert len(ranking) >= 1
        # Verify descending order
        for i in range(len(ranking) - 1):
            assert ranking[i]["avg_test_score"] >= ranking[i + 1]["avg_test_score"]

    def test_aggregate_ranking_empty_input(self):
        """Empty test results -> empty ranking."""
        from src.trading.backtesting.optimizer import WalkForwardOptimizer

        opt = WalkForwardOptimizer()
        ranking = opt._aggregate_ranking([])
        assert ranking == []

    def test_aggregate_ranking_avg_computed(self):
        """Multiple windows for same combo -> avg_test_score is the mean."""
        from src.trading.backtesting.optimizer import WalkForwardOptimizer

        opt = WalkForwardOptimizer()
        wr1 = _make_window_result(strategy="COT Momentum", timeframe="D1", is_train=False, composite_score=0.6)
        wr2 = _make_window_result(strategy="COT Momentum", timeframe="D1", is_train=False, composite_score=0.8)
        ranking = opt._aggregate_ranking([wr1, wr2])
        assert len(ranking) == 1
        assert abs(ranking[0]["avg_test_score"] - 0.7) < 1e-5


# ===========================================================================
# _detect_overfitting tests
# ===========================================================================


class TestDetectOverfitting:
    """Tests for overfitting detection between train and test scores."""

    def test_detect_overfitting_no_warning(self):
        """Train and test scores close (ratio <= 1.5) -> no warnings."""
        from src.trading.backtesting.optimizer import WalkForwardOptimizer

        opt = WalkForwardOptimizer()
        train = [
            _make_window_result(strategy="COT Momentum", timeframe="D1", is_train=True, composite_score=0.6),
        ]
        test = [
            _make_window_result(strategy="COT Momentum", timeframe="D1", is_train=False, composite_score=0.5),
        ]
        warnings = opt._detect_overfitting(train, test)
        assert warnings == []

    def test_detect_overfitting_high_ratio(self):
        """Train 2x test -> warning generated."""
        from src.trading.backtesting.optimizer import WalkForwardOptimizer

        opt = WalkForwardOptimizer()
        train = [
            _make_window_result(strategy="COT Momentum", timeframe="D1", is_train=True, composite_score=0.8),
        ]
        test = [
            _make_window_result(strategy="COT Momentum", timeframe="D1", is_train=False, composite_score=0.4),
        ]
        # ratio = 0.8 / 0.4 = 2.0 > 1.5
        warnings = opt._detect_overfitting(train, test)
        assert len(warnings) == 1
        assert "Potential overfitting" in warnings[0]
        assert "COT Momentum" in warnings[0]
        assert "D1" in warnings[0]
        assert "2.00" in warnings[0]

    def test_detect_overfitting_negative_test(self):
        """Positive train, negative test -> curve-fit warning."""
        from src.trading.backtesting.optimizer import WalkForwardOptimizer

        opt = WalkForwardOptimizer()
        train = [
            _make_window_result(strategy="SMC Confluence", timeframe="4H", is_train=True, composite_score=0.7),
        ]
        test = [
            _make_window_result(strategy="SMC Confluence", timeframe="4H", is_train=False, composite_score=-0.1),
        ]
        warnings = opt._detect_overfitting(train, test)
        curve_fit_warnings = [w for w in warnings if "Curve-fit detected" in w]
        assert len(curve_fit_warnings) == 1
        assert "SMC Confluence" in curve_fit_warnings[0]
        assert "4H" in curve_fit_warnings[0]

    def test_detect_overfitting_no_test_results(self):
        """Train results exist but no matching test results -> no warnings."""
        from src.trading.backtesting.optimizer import WalkForwardOptimizer

        opt = WalkForwardOptimizer()
        train = [
            _make_window_result(strategy="COT Momentum", timeframe="D1", is_train=True, composite_score=0.8),
        ]
        warnings = opt._detect_overfitting(train, [])
        assert warnings == []

    def test_detect_overfitting_multiple_combos(self):
        """Multiple strategy/timeframe combos, only one overfitting -> one warning."""
        from src.trading.backtesting.optimizer import WalkForwardOptimizer

        opt = WalkForwardOptimizer()
        train = [
            _make_window_result(strategy="COT Momentum", timeframe="D1", is_train=True, composite_score=0.5),
            _make_window_result(strategy="Mean Reversion", timeframe="1H", is_train=True, composite_score=0.9),
        ]
        test = [
            _make_window_result(strategy="COT Momentum", timeframe="D1", is_train=False, composite_score=0.45),
            _make_window_result(strategy="Mean Reversion", timeframe="1H", is_train=False, composite_score=0.3),
        ]
        warnings = opt._detect_overfitting(train, test)
        # COT: 0.5/0.45 = 1.11 -> no warning
        # MeanRev: 0.9/0.3 = 3.0 -> warning
        assert len(warnings) == 1
        assert "Mean Reversion" in warnings[0]
