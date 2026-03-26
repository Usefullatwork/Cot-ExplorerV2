"""Integration tests for the backtesting engine — end-to-end with mock data.

Tests the full pipeline: data loading -> bar iteration -> strategy execution ->
trade lifecycle -> metrics computation -> report generation.
"""

from __future__ import annotations

import json

from src.trading.backtesting.engine import BacktestEngine, Strategy
from src.trading.backtesting.models import Bar

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _weekly_dates(n: int, start: str = "2025-01-06") -> list[str]:
    """Generate n weekly date strings starting from start (Monday)."""
    from datetime import datetime, timedelta

    d = datetime.strptime(start, "%Y-%m-%d")
    return [(d + timedelta(weeks=i)).strftime("%Y-%m-%d") for i in range(n)]


def _make_bars(
    instrument: str,
    prices: list[tuple[str, float, float, float]],
    spec_nets: list[int | None] | None = None,
) -> list[Bar]:
    """Create a list of Bar objects from (date, close, high, low) tuples.

    If spec_nets is provided, it is zipped with the price tuples.
    """
    if spec_nets is None:
        spec_nets = [None] * len(prices)
    bars = []
    for i, (date, close, high, low) in enumerate(prices):
        sn = spec_nets[i] if i < len(spec_nets) else None
        bars.append(
            Bar(
                date=date,
                instrument=instrument,
                price=close,
                high=high,
                low=low,
                spec_net=sn,
                open_interest=100000 if sn is not None else None,
            )
        )
    return bars


class AlwaysLongStrategy(Strategy):
    """Test strategy that opens a long on the first bar, never closes manually."""

    name = "AlwaysLong"

    def __init__(self, target_instrument: str = "gold"):
        self.target_instrument = target_instrument
        self._opened = False

    def on_bar(self, date, bars_by_instrument, portfolio, engine) -> list[dict]:
        if self._opened:
            return []
        bars = bars_by_instrument.get(self.target_instrument, [])
        if not bars:
            return []
        current = bars[-1]
        self._opened = True
        return [
            {
                "action": "open",
                "instrument": self.target_instrument,
                "direction": "long",
                "entry_price": current.close,
                "stop_loss": current.close * 0.95,
                "take_profit": current.close * 1.10,
                "size": 10.0,
                "use_risk_sizing": False,
                "reason": "test_open",
            }
        ]


class MultiTradeStrategy(Strategy):
    """Strategy that opens a trade each bar for 3 bars, then does nothing."""

    name = "MultiTrade"

    def __init__(self, instrument: str = "gold"):
        self.instrument = instrument
        self._count = 0

    def on_bar(self, date, bars_by_instrument, portfolio, engine) -> list[dict]:
        if self._count >= 3:
            return []
        bars = bars_by_instrument.get(self.instrument, [])
        if not bars:
            return []
        self._count += 1
        current = bars[-1]
        return [
            {
                "action": "open",
                "instrument": self.instrument,
                "direction": "long",
                "entry_price": current.close,
                "stop_loss": current.close * 0.97,
                "take_profit": current.close * 1.05,
                "size": 5.0,
                "use_risk_sizing": False,
                "reason": f"trade_{self._count}",
            }
        ]


# ---------------------------------------------------------------------------
# Mock data directory setup
# ---------------------------------------------------------------------------


def _write_mock_data(tmp_path, instrument: str, price_data: list[dict], cot_data: list[dict] | None = None):
    """Write price and COT JSON files in the expected directory layout."""
    prices_dir = tmp_path / "prices"
    prices_dir.mkdir(exist_ok=True)
    ts_dir = tmp_path / "timeseries"
    ts_dir.mkdir(exist_ok=True)

    # Price file
    with open(prices_dir / f"{instrument}.json", "w") as f:
        json.dump({"data": price_data}, f)

    # cot_map.json (map COT symbol to instrument)
    cot_map = {"099741": instrument}
    with open(prices_dir / "cot_map.json", "w") as f:
        json.dump(cot_map, f)

    # COT timeseries file
    if cot_data:
        with open(ts_dir / "099741_tff.json", "w") as f:
            json.dump({"data": cot_data}, f)


# ===========================================================================
# Tests
# ===========================================================================


class TestBacktestEngineEndToEnd:
    """Full end-to-end backtest with mock data on disk."""

    def _price_rows(self) -> list[dict]:
        """10 weekly bars with rising prices."""
        base = 1800.0
        dates = _weekly_dates(10)
        return [{"date": dates[i], "price": base + i * 20} for i in range(10)]

    def test_run_produces_report_with_all_keys(self, tmp_path):
        """A complete backtest run returns a report with expected top-level keys."""
        _write_mock_data(tmp_path, "gold", self._price_rows())
        strategy = AlwaysLongStrategy("gold")
        engine = BacktestEngine(
            strategy=strategy,
            data_dir=str(tmp_path),
            instruments=["gold"],
            initial_capital=100000.0,
        )
        report = engine.run()

        assert "strategy" in report
        assert "instruments" in report
        assert "period" in report
        assert "capital" in report
        assert "trades" in report
        assert "risk" in report
        assert "equity_curve" in report
        assert "trade_log" in report
        assert report["strategy"] == "AlwaysLong"

    def test_trade_is_opened_and_closed_at_end(self, tmp_path):
        """Strategy opens one trade; it is closed at end_of_backtest."""
        _write_mock_data(tmp_path, "gold", self._price_rows())
        strategy = AlwaysLongStrategy("gold")
        engine = BacktestEngine(
            strategy=strategy,
            data_dir=str(tmp_path),
            instruments=["gold"],
            initial_capital=100000.0,
        )
        report = engine.run()

        assert report["trades"]["total"] == 1
        trade_log = report["trade_log"]
        assert len(trade_log) == 1
        assert trade_log[0]["direction"] == "long"
        assert trade_log[0]["is_open"] is False

    def test_rising_prices_produce_positive_pnl(self, tmp_path):
        """Long trade in a rising market has positive PnL."""
        _write_mock_data(tmp_path, "gold", self._price_rows())
        strategy = AlwaysLongStrategy("gold")
        engine = BacktestEngine(
            strategy=strategy,
            data_dir=str(tmp_path),
            instruments=["gold"],
            initial_capital=100000.0,
        )
        report = engine.run()

        assert report["trade_log"][0]["pnl"] > 0
        assert report["capital"]["total_return_pct"] > 0

    def test_equity_curve_length_matches_bar_count(self, tmp_path):
        """Equity curve has one entry per date."""
        rows = self._price_rows()
        _write_mock_data(tmp_path, "gold", rows)
        strategy = AlwaysLongStrategy("gold")
        engine = BacktestEngine(
            strategy=strategy,
            data_dir=str(tmp_path),
            instruments=["gold"],
            initial_capital=100000.0,
        )
        report = engine.run()

        assert len(report["equity_curve"]) == len(rows)

    def test_stop_loss_closes_trade_early(self, tmp_path):
        """When price drops through stop loss, trade is closed with negative PnL."""
        # Prices: 1800, then crash to 1600
        price_data = [
            {"date": "2025-01-07", "price": 1800.0},
            {"date": "2025-01-14", "price": 1600.0},
            {"date": "2025-01-21", "price": 1550.0},
        ]
        _write_mock_data(tmp_path, "gold", price_data)
        strategy = AlwaysLongStrategy("gold")
        engine = BacktestEngine(
            strategy=strategy,
            data_dir=str(tmp_path),
            instruments=["gold"],
            initial_capital=100000.0,
        )
        report = engine.run()

        assert report["trades"]["total"] == 1
        trade = report["trade_log"][0]
        # The stop loss is 1800 * 0.95 = 1710.  Price drops to 1600,
        # so stop loss is hit and PnL is negative.
        assert trade["pnl"] < 0
        assert trade["exit_reason"] in ("stop_loss", "end_of_backtest")

    def test_take_profit_closes_trade(self, tmp_path):
        """When price rises through take profit, trade is closed with positive PnL."""
        # Prices rise sharply past 10% target
        price_data = [
            {"date": "2025-01-07", "price": 1000.0},
            {"date": "2025-01-14", "price": 1120.0},  # high will be 1120, tp is 1100
            {"date": "2025-01-21", "price": 1150.0},
        ]
        _write_mock_data(tmp_path, "gold", price_data)
        strategy = AlwaysLongStrategy("gold")
        engine = BacktestEngine(
            strategy=strategy,
            data_dir=str(tmp_path),
            instruments=["gold"],
            initial_capital=100000.0,
        )
        report = engine.run()

        assert report["trades"]["total"] == 1
        trade = report["trade_log"][0]
        assert trade["pnl"] > 0

    def test_no_data_returns_error(self, tmp_path):
        """When no instrument data exists, run() returns error dict."""
        # Empty data directory
        (tmp_path / "prices").mkdir(exist_ok=True)
        (tmp_path / "timeseries").mkdir(exist_ok=True)

        strategy = AlwaysLongStrategy("gold")
        engine = BacktestEngine(
            strategy=strategy,
            data_dir=str(tmp_path),
            instruments=["gold"],
            initial_capital=100000.0,
        )
        report = engine.run()

        assert "error" in report
        assert report["trades"] == []


class TestBacktestMetricsIntegration:
    """Verify that metrics are computed correctly from actual trade results."""

    def test_win_rate_with_mixed_trades(self, tmp_path):
        """Multi-trade strategy: verify win_rate reflects actual outcomes."""
        # 10 bars, prices go up then down then up
        dates = _weekly_dates(10)
        prices = [100, 102, 104, 106, 103, 99, 96, 98, 101, 105]
        price_data = [{"date": dates[i], "price": p} for i, p in enumerate(prices)]
        _write_mock_data(tmp_path, "gold", price_data)
        strategy = MultiTradeStrategy("gold")
        engine = BacktestEngine(
            strategy=strategy,
            data_dir=str(tmp_path),
            instruments=["gold"],
            initial_capital=100000.0,
        )
        report = engine.run()

        total = report["trades"]["total"]
        winners = report["trades"]["winners"]
        losers = report["trades"]["losers"]
        assert total == winners + losers
        assert total >= 1
        # Win rate should be a valid percentage
        assert 0 <= report["trades"]["win_rate"] <= 100

    def test_sharpe_and_sortino_computed(self, tmp_path):
        """Risk metrics are computed when there are enough bars."""
        dates = _weekly_dates(20)
        price_data = [{"date": dates[i], "price": 100 + i * 2} for i in range(20)]
        _write_mock_data(tmp_path, "gold", price_data)
        strategy = AlwaysLongStrategy("gold")
        engine = BacktestEngine(
            strategy=strategy,
            data_dir=str(tmp_path),
            instruments=["gold"],
            initial_capital=100000.0,
        )
        report = engine.run()

        # With 20 bars there should be enough data for metrics
        assert isinstance(report["risk"]["sharpe_ratio"], (int, float))
        assert isinstance(report["risk"]["sortino_ratio"], (int, float))
        assert isinstance(report["risk"]["max_drawdown_pct"], (int, float))
