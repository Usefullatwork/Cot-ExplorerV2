"""
Walk-forward optimizer for Cot-ExplorerV2 backtesting strategies.

Usage: python -m src.trading.backtesting.optimizer --instrument eurusd
"""

from __future__ import annotations

import argparse
import time
from datetime import datetime, timedelta
from typing import Any, Optional

from .data_loader import DataLoader
from .engine import BacktestEngine, Strategy
from .models import Bar
from .param_grid import DEFAULT_PARAM_GRID, TIMEFRAMES, generate_combinations
from .report_generator import OptimizationReport
from .strategies import (
    COTMomentumStrategy,
    MacroRegimeStrategy,
    MeanReversionStrategy,
    SMCConfluenceStrategy,
)
from .wfo_models import OptimizationResult, WindowResult

# Composite scoring weights
W_SHARPE = 0.30
W_WIN_RATE = 0.25
W_DRAWDOWN = 0.25
W_PROFIT_FACTOR = 0.20


def _build_strategy(name: str, params: dict[str, Any]) -> Strategy:
    """Instantiate a strategy with optimizer-level parameter overrides."""
    if name == "COT Momentum":
        return COTMomentumStrategy(
            sl_atr_mult=params.get("sl_atr_multiplier", 2.0),
            tp_atr_mult=params.get("sl_atr_multiplier", 2.0) * params.get("tp_rr_ratio", 1.5),
        )
    elif name == "SMC Confluence":
        return SMCConfluenceStrategy(
            min_confluence=params.get("min_score", 6),
            tp_rr=params.get("tp_rr_ratio", 2.0),
        )
    elif name == "Mean Reversion":
        return MeanReversionStrategy(
            sl_buffer_atr=params.get("sl_atr_multiplier", 2.0) * 0.15,
            max_hold_bars=params.get("candle_exit_bars", 8),
        )
    elif name == "Macro Regime":
        return MacroRegimeStrategy(
            sl_atr_mult=params.get("sl_atr_multiplier", 3.0),
        )
    raise ValueError(f"Unknown strategy: {name}")


def _generate_windows(
    dates: list[str], train_months: int, test_months: int,
) -> list[tuple[str, str, str, str]]:
    """Generate rolling (train_start, train_end, test_start, test_end) tuples."""
    if not dates:
        return []
    first = datetime.strptime(dates[0], "%Y-%m-%d")
    last = datetime.strptime(dates[-1], "%Y-%m-%d")
    if (last - first).days < (train_months + test_months) * 30:
        return []
    windows, cursor = [], first
    while True:
        tr_end = cursor + timedelta(days=train_months * 30)
        te_end = tr_end + timedelta(days=test_months * 30)
        if te_end > last:
            break
        windows.append((
            cursor.strftime("%Y-%m-%d"), tr_end.strftime("%Y-%m-%d"),
            tr_end.strftime("%Y-%m-%d"), te_end.strftime("%Y-%m-%d"),
        ))
        cursor = tr_end  # slide forward by test_months
    return windows


def score_result(report: dict[str, Any]) -> float:
    """Composite score: 0.30*sharpe + 0.25*win_rate + 0.25*(1-dd) + 0.20*pf.

    All components normalized to [0, 1]. Higher is better.
    """
    risk = report.get("risk", {})
    trades = report.get("trades", {})
    sharpe = risk.get("sharpe_ratio", 0.0)
    win_rate = trades.get("win_rate", 0.0)
    max_dd = risk.get("max_drawdown_pct", 0.0)
    pf = trades.get("profit_factor", 0.0)

    norm_sharpe = (min(max(sharpe, -2.0), 4.0) + 2.0) / 6.0
    norm_wr = min(max(win_rate, 0.0), 100.0) / 100.0
    norm_dd = 1.0 - min(max(max_dd, 0.0), 50.0) / 50.0
    norm_pf = min(max(pf, 0.0), 5.0) / 5.0

    return W_SHARPE * norm_sharpe + W_WIN_RATE * norm_wr + W_DRAWDOWN * norm_dd + W_PROFIT_FACTOR * norm_pf


class WalkForwardOptimizer:
    """Walk-forward optimization across strategies x timeframes x parameters.

    Process per window: grid-search on train, validate best on test, slide forward.
    """

    STRATEGY_NAMES = ["COT Momentum", "SMC Confluence", "Mean Reversion", "Macro Regime"]

    def __init__(
        self,
        strategies: Optional[list[str]] = None,
        timeframes: Optional[list[str]] = None,
        param_grid: Optional[dict[str, list[Any]]] = None,
        train_months: int = 6,
        test_months: int = 2,
        min_trades: int = 10,
        data_dir: str = "data",
        initial_capital: float = 100_000.0,
    ):
        self.strategies = strategies or list(self.STRATEGY_NAMES)
        self.timeframes = timeframes or list(TIMEFRAMES)
        self.param_grid = param_grid or dict(DEFAULT_PARAM_GRID)
        self.train_months = train_months
        self.test_months = test_months
        self.min_trades = min_trades
        self.data_dir = data_dir
        self.initial_capital = initial_capital
        self._combinations = generate_combinations(self.param_grid)

    def run(self, instrument: str) -> OptimizationResult:
        """Run full walk-forward optimization for one instrument."""
        t0 = time.time()
        loader = DataLoader(self.data_dir)
        all_bars = loader.load_merged(instrument)
        if not all_bars:
            return self._empty_result(instrument, t0)

        all_dates = sorted({b.date for b in all_bars})
        windows = _generate_windows(all_dates, self.train_months, self.test_months)
        if not windows:
            return self._empty_result(instrument, t0)

        all_train: list[WindowResult] = []
        all_test: list[WindowResult] = []
        total_combos = len(self.strategies) * len(self.timeframes) * len(self._combinations)

        for _wi, (tr_s, tr_e, te_s, te_e) in enumerate(windows):
            best_per_strat_tf: dict[tuple[str, str], tuple[dict, float]] = {}
            for strat_name in self.strategies:
                for tf in self.timeframes:
                    for params in self._combinations:
                        wr = self._run_single(instrument, all_bars, strat_name, tf, params, tr_s, tr_e, True)
                        if wr is None:
                            continue
                        all_train.append(wr)
                        key = (strat_name, tf)
                        prev = best_per_strat_tf.get(key)
                        if prev is None or wr.composite_score > prev[1]:
                            best_per_strat_tf[key] = (params, wr.composite_score)

            for (strat_name, tf), (best_params, _) in best_per_strat_tf.items():
                wr = self._run_single(instrument, all_bars, strat_name, tf, best_params, te_s, te_e, False)
                if wr is not None:
                    all_test.append(wr)

        ranking = self._aggregate_ranking(all_test)
        return OptimizationResult(
            instrument=instrument, total_windows=len(windows),
            total_combinations=total_combos, runtime_seconds=time.time() - t0,
            train_results=all_train, test_results=all_test,
            best_combo=ranking[0] if ranking else {}, ranking=ranking,
        )

    def run_all_instruments(self, instruments: list[str]) -> dict[str, OptimizationResult]:
        """Run optimization across all instruments."""
        return {inst: self.run(inst) for inst in instruments}

    def _empty_result(self, instrument: str, t0: float) -> OptimizationResult:
        return OptimizationResult(instrument=instrument, total_windows=0,
                                  total_combinations=0, runtime_seconds=time.time() - t0)

    def _run_single(
        self, instrument: str, all_bars: list[Bar], strat_name: str,
        timeframe: str, params: dict[str, Any],
        start_date: str, end_date: str, is_train: bool,
    ) -> Optional[WindowResult]:
        """Run a single backtest. Returns None if insufficient data/trades."""
        try:
            strategy = _build_strategy(strat_name, params)
        except ValueError:
            return None

        window_bars = [b for b in all_bars if start_date <= b.date <= end_date]
        if len(window_bars) < 10:
            return None

        engine = BacktestEngine(
            strategy=strategy, data_dir=self.data_dir, instruments=[instrument],
            start_date=start_date, end_date=end_date, initial_capital=self.initial_capital,
        )
        engine._all_bars = {instrument: window_bars}
        engine._all_dates = sorted({b.date for b in window_bars})
        if not engine._all_dates:
            return None

        for date in engine._all_dates:
            bars_by_inst = {}
            for inst in engine._all_bars:
                history = engine._get_bars_up_to(inst, date)
                if history:
                    bars_by_inst[inst] = history
                    engine._current_prices[inst] = history[-1].close
            engine._process_exits(date, bars_by_inst)
            for t in engine.portfolio.open_trades.values():
                t.bars_held += 1
            actions = engine.strategy.on_bar(date, bars_by_inst, engine.portfolio, engine)
            engine._process_actions(date, actions)
            engine.portfolio.record_equity(date, engine._current_prices)

        if engine._all_dates:
            engine.portfolio.close_all(engine._current_prices, engine._all_dates[-1])

        report = engine.report()
        n_trades = report.get("trades", {}).get("total", 0)
        if n_trades < self.min_trades and not is_train:
            return None

        return WindowResult(
            window_start=start_date, window_end=end_date, is_train=is_train,
            strategy=strat_name, timeframe=timeframe, params=params,
            metrics={
                "sharpe": report.get("risk", {}).get("sharpe_ratio", 0.0),
                "win_rate": report.get("trades", {}).get("win_rate", 0.0),
                "max_drawdown": report.get("risk", {}).get("max_drawdown_pct", 0.0),
                "profit_factor": report.get("trades", {}).get("profit_factor", 0.0),
                "total_trades": n_trades,
                "total_return_pct": report.get("capital", {}).get("total_return_pct", 0.0),
            },
            composite_score=score_result(report),
        )

    def _aggregate_ranking(self, test_results: list[WindowResult]) -> list[dict[str, Any]]:
        """Group OOS results by combo, average scores, sort descending."""
        combos: dict[str, list[WindowResult]] = {}
        for wr in test_results:
            key = f"{wr.strategy}|{wr.timeframe}|{sorted(wr.params.items())}"
            combos.setdefault(key, []).append(wr)

        ranking: list[dict[str, Any]] = []
        for windows in combos.values():
            n = len(windows)
            first = windows[0]
            ranking.append({
                "strategy": first.strategy, "timeframe": first.timeframe,
                "params": first.params,
                "avg_test_score": round(sum(w.composite_score for w in windows) / n, 6),
                "avg_sharpe": round(sum(w.metrics.get("sharpe", 0) for w in windows) / n, 3),
                "avg_win_rate": round(sum(w.metrics.get("win_rate", 0) for w in windows) / n, 1),
                "avg_max_dd": round(sum(w.metrics.get("max_drawdown", 0) for w in windows) / n, 1),
                "avg_profit_factor": round(sum(w.metrics.get("profit_factor", 0) for w in windows) / n, 2),
                "n_windows": n,
            })
        ranking.sort(key=lambda x: x["avg_test_score"], reverse=True)
        return ranking


def main() -> None:
    """CLI entry point for walk-forward optimization."""
    parser = argparse.ArgumentParser(description="Walk-forward optimization for Cot-ExplorerV2")
    parser.add_argument("--instrument", "-i", required=True, help="Instrument (e.g. eurusd, gold)")
    parser.add_argument("--data-dir", "-d", default="data", help="Data directory (default: data)")
    parser.add_argument("--train-months", type=int, default=6, help="Train window months (default: 6)")
    parser.add_argument("--test-months", type=int, default=2, help="Test window months (default: 2)")
    parser.add_argument("--min-trades", type=int, default=10, help="Min OOS trades (default: 10)")
    parser.add_argument("--output-dir", "-o", default=None, help="Save reports to directory")

    args = parser.parse_args()
    opt = WalkForwardOptimizer(
        data_dir=args.data_dir, train_months=args.train_months,
        test_months=args.test_months, min_trades=args.min_trades,
    )
    print(f"Walk-forward optimization: {args.instrument}")
    print(f"  {len(opt.strategies)} strategies x {len(opt.timeframes)} timeframes x {len(opt._combinations)} params")
    print(f"  Train/Test: {args.train_months}m / {args.test_months}m\n")

    result = opt.run(args.instrument)
    reporter = OptimizationReport()
    print(reporter.generate_summary(result))

    stability = reporter.stability_analysis(result)
    if stability.get("warnings"):
        print("\n  STABILITY WARNINGS:")
        for w in stability["warnings"]:
            print(f"    ! {w}")

    if args.output_dir:
        paths = reporter.save(result, args.output_dir, prefix=f"wfo_{args.instrument}")
        print(f"\n  Reports saved: {', '.join(paths.values())}")


if __name__ == "__main__":
    main()
