"""WFO runner service — orchestrates backtest, OOS validation, PBO, DB persistence.

Coordinates the full walk-forward optimization pipeline:
1. Load price/COT data from DB via DbDataLoader
2. Configure WalkForwardOptimizer with Pepperstone transaction costs
3. Run WFO across strategies × timeframes × param grid
4. Run CPCV + PBO on the results
5. Persist everything to wfo_runs + wfo_window_results tables
"""

from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from sqlalchemy.orm import Session

from src.analysis.transaction_costs import load_cost_configs
from src.db.models import WfoRun, WfoWindowResult

from .db_loader import DbDataLoader
from .engine import BacktestEngine
from .models import Bar
from .oos_validation import (
    probability_of_backtest_overfit,
    validate_strategy_oos,
)
from .optimizer import WalkForwardOptimizer, _build_strategy, score_result
from .wfo_models import OptimizationResult, WindowResult

logger = logging.getLogger(__name__)

# Default instruments for WFO runs
DEFAULT_INSTRUMENTS = ["EURUSD", "GBPUSD", "USDJPY", "XAUUSD", "USOIL", "SPX500"]

# Path to Pepperstone cost config
_COST_CONFIG_PATH = Path(__file__).resolve().parents[3] / "config" / "transaction_costs.yaml"


def _load_pepperstone_costs() -> dict[str, Any]:
    """Load Pepperstone transaction costs, return spread_pips per instrument."""
    if not _COST_CONFIG_PATH.exists():
        return {}
    configs = load_cost_configs(str(_COST_CONFIG_PATH))
    return {
        symbol: cfg.base_spread
        for symbol, cfg in configs.items()
    }


class WfoRunnerService:
    """Orchestrates walk-forward optimization with DB persistence."""

    def __init__(self, session: Session):
        self.session = session
        self.loader = DbDataLoader(session)
        self.costs = _load_pepperstone_costs()

    def run_wfo(
        self,
        instrument: str,
        strategies: Optional[list[str]] = None,
        train_months: int = 6,
        test_months: int = 2,
        window_mode: str = "sliding",
        min_trades: int = 10,
        purge_days: int = 0,
        embargo_days: int = 0,
    ) -> WfoRun:
        """Run full WFO for one instrument and persist results.

        Returns the WfoRun DB record with all window results attached.
        """
        # Create run record
        run = WfoRun(
            instrument=instrument.upper(),
            status="running",
            train_months=train_months,
            test_months=test_months,
            window_mode=window_mode,
        )
        self.session.add(run)
        self.session.flush()  # get run.id

        t0 = time.time()

        try:
            result = self._execute_wfo(
                instrument, strategies, train_months, test_months,
                window_mode, min_trades, purge_days, embargo_days,
            )

            # Compute PBO from train/test results
            pbo, oos_summary = self._compute_oos_metrics(result)

            # Update run record
            run.finished_at = datetime.now(timezone.utc)
            run.status = "ok"
            run.total_windows = result.total_windows
            run.total_combinations = result.total_combinations
            run.runtime_seconds = round(time.time() - t0, 2)
            run.pbo_score = pbo
            run.overfit_warnings_json = json.dumps(
                result.overfit_warnings, ensure_ascii=False,
            )
            run.oos_summary_json = json.dumps(oos_summary, ensure_ascii=False)

            if result.best_combo:
                run.best_strategy = result.best_combo.get("strategy")
                run.best_timeframe = result.best_combo.get("timeframe")
                run.best_params_json = json.dumps(
                    result.best_combo.get("params", {}), ensure_ascii=False,
                )
                run.best_test_score = result.best_combo.get("avg_test_score")

            run.ranking_json = json.dumps(
                result.ranking[:20], ensure_ascii=False, default=str,
            )

            # Persist window results (test only — train can be huge)
            for wr in result.test_results:
                self._persist_window_result(run.id, wr)

            # Also persist top train results (best per strategy+timeframe)
            best_train = self._pick_best_train_results(result.train_results)
            for wr in best_train:
                self._persist_window_result(run.id, wr)

            self.session.commit()
            logger.info(
                "WFO complete: %s — %d windows, PBO=%.3f, best=%s/%s",
                instrument, result.total_windows, pbo or 0,
                run.best_strategy, run.best_timeframe,
            )

        except Exception as exc:
            run.status = "error"
            run.error_message = str(exc)[:1000]
            run.finished_at = datetime.now(timezone.utc)
            run.runtime_seconds = round(time.time() - t0, 2)
            self.session.commit()
            logger.error("WFO failed for %s: %s", instrument, exc)
            raise

        return run

    def run_all(
        self,
        instruments: Optional[list[str]] = None,
        **kwargs: Any,
    ) -> list[WfoRun]:
        """Run WFO for all instruments sequentially."""
        instruments = instruments or DEFAULT_INSTRUMENTS
        available = set(self.loader.available_instruments())

        runs: list[WfoRun] = []
        for inst in instruments:
            if inst.upper() not in available:
                logger.warning("Skipping %s — no price data in DB", inst)
                continue
            run = self.run_wfo(inst, **kwargs)
            runs.append(run)

        return runs

    def _execute_wfo(
        self,
        instrument: str,
        strategies: Optional[list[str]],
        train_months: int,
        test_months: int,
        window_mode: str,
        min_trades: int,
        purge_days: int,
        embargo_days: int,
    ) -> OptimizationResult:
        """Execute the WFO using DB-loaded data.

        Loads bars from DB, feeds them to the optimizer, applies
        Pepperstone transaction costs.
        """
        inst_upper = instrument.upper()
        bars = self.loader.load_merged(inst_upper)

        if not bars:
            return OptimizationResult(
                instrument=inst_upper,
                total_windows=0,
                total_combinations=0,
                runtime_seconds=0.0,
            )

        # Get spread for this instrument
        spread = self.costs.get(inst_upper, 0.0)

        # Create optimizer with DB-loaded data injected
        optimizer = WalkForwardOptimizer(
            strategies=strategies,
            train_months=train_months,
            test_months=test_months,
            min_trades=min_trades,
            window_mode=window_mode,
            purge_days=purge_days,
            embargo_days=embargo_days,
        )

        # Run via internal method that accepts pre-loaded bars
        return self._run_with_bars(
            optimizer, inst_upper, bars, spread,
        )

    def _run_with_bars(
        self,
        optimizer: WalkForwardOptimizer,
        instrument: str,
        bars: list[Bar],
        spread_pips: float,
    ) -> OptimizationResult:
        """Run WFO with pre-loaded bars (bypassing file-based DataLoader).

        Mirrors optimizer.run() but uses bars directly instead of loading
        from JSON files.
        """
        from .optimizer import (
            _generate_windows,
            generate_windows_enhanced,
        )

        t0 = time.time()
        if not bars:
            return OptimizationResult(
                instrument=instrument, total_windows=0,
                total_combinations=0, runtime_seconds=0.0,
            )

        all_dates = sorted({b.date for b in bars})
        use_enhanced = (
            optimizer.window_mode != "sliding"
            or optimizer.purge_days > 0
            or optimizer.embargo_days > 0
        )
        if use_enhanced:
            windows = generate_windows_enhanced(
                all_dates, optimizer.train_months, optimizer.test_months,
                mode=optimizer.window_mode,
                purge_days=optimizer.purge_days,
                embargo_days=optimizer.embargo_days,
            )
        else:
            windows = _generate_windows(
                all_dates, optimizer.train_months, optimizer.test_months,
            )

        if not windows:
            return OptimizationResult(
                instrument=instrument, total_windows=0,
                total_combinations=0, runtime_seconds=0.0,
            )

        all_train: list[WindowResult] = []
        all_test: list[WindowResult] = []
        total_combos = (
            len(optimizer.strategies)
            * len(optimizer.timeframes)
            * len(optimizer._combinations)
        )

        for _wi, (tr_s, tr_e, te_s, te_e) in enumerate(windows):
            best_per_strat_tf: dict[tuple[str, str], tuple[dict, float]] = {}

            for strat_name in optimizer.strategies:
                for tf in optimizer.timeframes:
                    for params in optimizer._combinations:
                        wr = self._run_single_window(
                            instrument, bars, strat_name, tf, params,
                            tr_s, tr_e, True, spread_pips,
                            optimizer.initial_capital,
                            optimizer.min_trades,
                        )
                        if wr is None:
                            continue
                        all_train.append(wr)
                        key = (strat_name, tf)
                        prev = best_per_strat_tf.get(key)
                        if prev is None or wr.composite_score > prev[1]:
                            best_per_strat_tf[key] = (params, wr.composite_score)

            for (strat_name, tf), (best_params, _) in best_per_strat_tf.items():
                wr = self._run_single_window(
                    instrument, bars, strat_name, tf, best_params,
                    te_s, te_e, False, spread_pips,
                    optimizer.initial_capital,
                    optimizer.min_trades,
                )
                if wr is not None:
                    all_test.append(wr)

        ranking = optimizer._aggregate_ranking(all_test)
        overfit_warnings = optimizer._detect_overfitting(all_train, all_test)

        return OptimizationResult(
            instrument=instrument,
            total_windows=len(windows),
            total_combinations=total_combos,
            runtime_seconds=time.time() - t0,
            train_results=all_train,
            test_results=all_test,
            best_combo=ranking[0] if ranking else {},
            ranking=ranking,
            overfit_warnings=overfit_warnings,
        )

    def _run_single_window(
        self,
        instrument: str,
        all_bars: list[Bar],
        strat_name: str,
        timeframe: str,
        params: dict[str, Any],
        start_date: str,
        end_date: str,
        is_train: bool,
        spread_pips: float,
        initial_capital: float,
        min_trades: int,
    ) -> Optional[WindowResult]:
        """Run a single backtest window with Pepperstone costs applied."""
        try:
            strategy = _build_strategy(strat_name, params)
        except ValueError:
            return None

        window_bars = [b for b in all_bars if start_date <= b.date <= end_date]
        if len(window_bars) < 10:
            return None

        engine = BacktestEngine(
            strategy=strategy,
            data_dir="",  # not used — we inject bars directly
            instruments=[instrument],
            start_date=start_date,
            end_date=end_date,
            initial_capital=initial_capital,
            spread_pips=spread_pips,
        )
        engine._all_bars = {instrument: window_bars}
        engine._all_dates = sorted({b.date for b in window_bars})
        if not engine._all_dates:
            return None

        for date in engine._all_dates:
            bars_by_inst: dict[str, list[Bar]] = {}
            for inst in engine._all_bars:
                history = engine._get_bars_up_to(inst, date)
                if history:
                    bars_by_inst[inst] = history
                    engine._current_prices[inst] = history[-1].close
            engine._process_exits(date, bars_by_inst)
            for t in engine.portfolio.open_trades.values():
                t.bars_held += 1
            actions = engine.strategy.on_bar(
                date, bars_by_inst, engine.portfolio, engine,
            )
            engine._process_actions(date, actions)
            engine.portfolio.record_equity(date, engine._current_prices)

        if engine._all_dates:
            engine.portfolio.close_all(
                engine._current_prices, engine._all_dates[-1],
            )

        report = engine.report()
        n_trades = report.get("trades", {}).get("total", 0)
        if n_trades < min_trades and not is_train:
            return None

        return WindowResult(
            window_start=start_date,
            window_end=end_date,
            is_train=is_train,
            strategy=strat_name,
            timeframe=timeframe,
            params=params,
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

    def _compute_oos_metrics(
        self, result: OptimizationResult,
    ) -> tuple[Optional[float], dict[str, Any]]:
        """Compute PBO and OOS summary from WFO results."""
        if not result.test_results or not result.train_results:
            return None, {"message": "insufficient data for OOS analysis"}

        # Group by strategy+timeframe for CPCV-style analysis
        is_by_param: dict[str, list[float]] = {}
        oos_by_param: dict[str, list[float]] = {}

        for wr in result.train_results:
            key = f"{wr.strategy}|{wr.timeframe}"
            is_by_param.setdefault(key, []).append(wr.composite_score)

        for wr in result.test_results:
            key = f"{wr.strategy}|{wr.timeframe}"
            oos_by_param.setdefault(key, []).append(wr.composite_score)

        # Only keep keys present in both
        common_keys = set(is_by_param.keys()) & set(oos_by_param.keys())
        if not common_keys:
            return None, {"message": "no overlapping strategy+timeframe combos"}

        is_filtered = {k: is_by_param[k] for k in sorted(common_keys)}
        oos_filtered = {k: oos_by_param[k] for k in sorted(common_keys)}

        # Compute aggregate IS and OOS means per combo
        is_means = [sum(v) / len(v) for v in is_filtered.values()]
        oos_means = [sum(v) / len(v) for v in oos_filtered.values()]

        pbo = probability_of_backtest_overfit(is_means, oos_means)

        # CPCV summary
        cpcv = validate_strategy_oos(is_filtered, oos_filtered)

        summary = {
            "pbo": round(pbo, 4),
            "n_combos": len(common_keys),
            "mean_oos_score": round(cpcv.mean_oos, 6),
            "std_oos_score": round(cpcv.std_oos, 6),
            "is_significant": cpcv.is_significant,
            "pbo_rating": (
                "green" if pbo < 0.3
                else "yellow" if pbo < 0.5
                else "red"
            ),
        }

        return pbo, summary

    def _persist_window_result(
        self, run_id: int, wr: WindowResult,
    ) -> None:
        """Save a single window result to the DB."""
        record = WfoWindowResult(
            run_id=run_id,
            window_start=wr.window_start,
            window_end=wr.window_end,
            is_train=wr.is_train,
            strategy=wr.strategy,
            timeframe=wr.timeframe,
            params_json=json.dumps(wr.params, ensure_ascii=False, default=str),
            sharpe=wr.metrics.get("sharpe"),
            win_rate=wr.metrics.get("win_rate"),
            max_drawdown=wr.metrics.get("max_drawdown"),
            profit_factor=wr.metrics.get("profit_factor"),
            total_trades=wr.metrics.get("total_trades", 0),
            total_return_pct=wr.metrics.get("total_return_pct"),
            composite_score=wr.composite_score,
        )
        self.session.add(record)

    def _pick_best_train_results(
        self, train_results: list[WindowResult], max_per_combo: int = 1,
    ) -> list[WindowResult]:
        """Pick the best train result per strategy+timeframe combo."""
        best: dict[tuple[str, str], WindowResult] = {}
        for wr in train_results:
            key = (wr.strategy, wr.timeframe)
            if key not in best or wr.composite_score > best[key].composite_score:
                best[key] = wr
        return list(best.values())
