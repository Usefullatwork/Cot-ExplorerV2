"""
Backtesting engine for Cot-ExplorerV2 trading strategies.
Uses historical COT + price data. Zero external dependencies.

Data sources:
  - data/prices/{instrument}.json  -- weekly price + date
  - data/timeseries/{symbol}_{report}.json -- weekly COT spec_net, oi
  - data/prices/cot_map.json -- maps COT symbol -> price key

The engine merges COT and price data by date (weekly alignment),
iterates chronologically, and calls strategy.on_bar() for each bar.
"""

from typing import Dict, List, Optional

from .data_loader import DataLoader
from .indicators import Indicators

# Re-export extracted classes for backward compatibility
from .models import Bar, Portfolio, Trade

# ---------------------------------------------------------------------------
# Strategy Base Class
# ---------------------------------------------------------------------------


class Strategy:
    """Base class for all backtesting strategies.

    Subclasses must implement:
        on_bar(date, bars_by_instrument, portfolio, engine) -> List[dict]

    on_bar returns a list of action dicts:
        {"action": "open", "instrument": ..., "direction": ...,
         "entry_price": ..., "stop_loss": ..., "take_profit": ...,
         "size": ..., "reason": ...}
        {"action": "close", "trade_id": ..., "reason": ...}
    """

    name: str = "BaseStrategy"

    def on_bar(
        self,
        date: str,
        bars_by_instrument: Dict[str, List[Bar]],
        portfolio: Portfolio,
        engine: "BacktestEngine",
    ) -> List[Dict]:
        """Called once per date with all available instrument data.

        bars_by_instrument: {instrument: [Bar, ...]} -- full history up to current date
        Returns list of trade actions.
        """
        raise NotImplementedError


# ---------------------------------------------------------------------------
# BacktestEngine
# ---------------------------------------------------------------------------


# Default pip sizes per instrument (override via pip_size param)
DEFAULT_PIP_SIZES: Dict[str, float] = {
    "eurusd": 0.0001, "gbpusd": 0.0001, "audusd": 0.0001,
    "nzdusd": 0.0001, "usdcad": 0.0001, "usdchf": 0.0001,
    "eurgbp": 0.0001, "eurjpy": 0.01, "gbpjpy": 0.01,
    "usdjpy": 0.01, "audjpy": 0.01, "nzdjpy": 0.01,
    "gold": 0.1, "silver": 0.01, "spx": 0.1, "sp500": 0.1,
    "nasdaq": 0.1, "dax": 0.1, "oil": 0.01, "copper": 0.01,
    "natgas": 0.001, "btcusd": 1.0, "ethusd": 0.01,
}


class BacktestEngine:
    """Main backtesting engine. Orchestrates data loading, bar iteration,
    strategy execution, and report generation."""

    def __init__(
        self,
        strategy: Strategy,
        data_dir: str,
        instruments: Optional[List[str]] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        initial_capital: float = 100000.0,
        risk_per_trade: float = 0.01,
        slippage_pips: float = 0.0,
        commission_pips: float = 0.0,
        spread_pips: float = 0.0,
        pip_size: Optional[Dict[str, float]] = None,
    ):
        self.strategy = strategy
        self.data_dir = data_dir
        self.instruments = instruments
        self.start_date = start_date
        self.end_date = end_date
        self.initial_capital = initial_capital
        self.risk_per_trade = risk_per_trade

        # Trading cost parameters (in pips)
        self.slippage_pips = slippage_pips
        self.commission_pips = commission_pips
        self.spread_pips = spread_pips
        self._pip_sizes: Dict[str, float] = {**DEFAULT_PIP_SIZES, **(pip_size or {})}

        self.loader = DataLoader(data_dir)
        self.portfolio = Portfolio(initial_capital)
        self.indicators = Indicators()

        # Populated by load_data()
        self._all_bars: Dict[str, List[Bar]] = {}
        self._all_dates: List[str] = []
        self._current_prices: Dict[str, float] = {}

    def _get_pip_size(self, instrument: str) -> float:
        """Return pip size for an instrument. Falls back to 0.0001."""
        return self._pip_sizes.get(instrument.lower(), 0.0001)

    def _entry_cost(self, instrument: str) -> float:
        """Total entry cost in price units (spread + slippage)."""
        ps = self._get_pip_size(instrument)
        return (self.spread_pips + self.slippage_pips) * ps

    def _exit_cost(self, instrument: str) -> float:
        """Total exit cost in price units (slippage only -- spread paid at entry)."""
        ps = self._get_pip_size(instrument)
        return self.slippage_pips * ps

    def _commission_cost(self, instrument: str, size: float) -> float:
        """Commission cost in currency for a trade."""
        ps = self._get_pip_size(instrument)
        return self.commission_pips * ps * size

    def load_data(self):
        """Load all instrument data and build date index."""
        if self.instruments is None:
            self.instruments = self.loader.available_instruments()

        date_set = set()
        for inst in self.instruments:
            bars = self.loader.load_merged(inst, self.start_date, self.end_date)
            if bars:
                self._all_bars[inst] = bars
                for b in bars:
                    date_set.add(b.date)

        self._all_dates = sorted(date_set)

    def _get_bars_up_to(self, instrument: str, date: str) -> List[Bar]:
        """Return all bars for instrument up to and including date."""
        bars = self._all_bars.get(instrument, [])
        return [b for b in bars if b.date <= date]

    def run(self) -> Dict:
        """Execute the backtest. Returns full results dict."""
        self.load_data()

        if not self._all_dates:
            return {"error": "No data loaded", "trades": [], "equity": []}

        for date in self._all_dates:
            # Build bars_by_instrument with history up to current date
            bars_by_inst: Dict[str, List[Bar]] = {}
            for inst in self._all_bars:
                history = self._get_bars_up_to(inst, date)
                if history:
                    bars_by_inst[inst] = history
                    self._current_prices[inst] = history[-1].close

            # Check stops and targets on open trades first
            self._process_exits(date, bars_by_inst)

            # Increment bars_held for open trades
            for t in self.portfolio.open_trades.values():
                t.bars_held += 1

            # Call strategy
            actions = self.strategy.on_bar(date, bars_by_inst, self.portfolio, self)

            # Process strategy actions
            self._process_actions(date, actions)

            # Record equity
            self.portfolio.record_equity(date, self._current_prices)

        # Close remaining positions at last known prices (with exit costs)
        if self._all_dates:
            last_date = self._all_dates[-1]
            for trade_id in list(self.portfolio.open_trades.keys()):
                trade = self.portfolio.open_trades[trade_id]
                price = self._current_prices.get(trade.instrument)
                if price is not None:
                    exit_slip = self._exit_cost(trade.instrument)
                    if trade.direction == "long":
                        price = price - exit_slip
                    else:
                        price = price + exit_slip
                    commission = self._commission_cost(trade.instrument, trade.size)
                    self.portfolio.close_trade(trade_id, price, last_date, "end_of_backtest")
                    self.portfolio.cash -= commission

        return self.report()

    def _process_exits(self, date: str, bars_by_inst: Dict[str, List[Bar]]):
        """Check stop loss and take profit for all open trades.
        Applies exit slippage and commission costs."""
        for trade_id in list(self.portfolio.open_trades.keys()):
            trade = self.portfolio.open_trades[trade_id]
            inst_bars = bars_by_inst.get(trade.instrument, [])
            if not inst_bars:
                continue
            current_bar = inst_bars[-1]
            if current_bar.date != date:
                continue

            h = current_bar.high
            lo = current_bar.low
            exit_slip = self._exit_cost(trade.instrument)

            # Stop loss hit first (conservative: assume worst case)
            if trade.check_stop_loss(h, lo):
                # Slippage worsens exit: long fills lower, short fills higher
                if trade.direction == "long":
                    exit_price = trade.stop_loss - exit_slip
                else:
                    exit_price = trade.stop_loss + exit_slip
                commission = self._commission_cost(trade.instrument, trade.size)
                self.portfolio.close_trade(trade_id, exit_price, date, "stop_loss")
                self.portfolio.cash -= commission
            elif trade.check_take_profit(h, lo):
                # Slippage worsens exit: long fills lower, short fills higher
                if trade.direction == "long":
                    exit_price = trade.take_profit - exit_slip
                else:
                    exit_price = trade.take_profit + exit_slip
                commission = self._commission_cost(trade.instrument, trade.size)
                self.portfolio.close_trade(trade_id, exit_price, date, "take_profit")
                self.portfolio.cash -= commission

    def _process_actions(self, date: str, actions: List[Dict]):
        """Execute trade actions from the strategy.
        Applies spread + slippage on entry, slippage on manual close,
        and commission on both entry and exit."""
        for action in actions:
            act_type = action.get("action")

            if act_type == "open":
                entry_price = action["entry_price"]
                stop_loss = action.get("stop_loss")
                take_profit = action.get("take_profit")
                instrument = action["instrument"]
                direction = action["direction"]
                reason = action.get("reason", "")

                # Apply spread + slippage to entry price (unfavorable direction)
                entry_adj = self._entry_cost(instrument)
                if direction == "long":
                    entry_price = entry_price + entry_adj
                else:
                    entry_price = entry_price - entry_adj

                # Calculate size from risk if stop_loss provided
                size = action.get("size", 1.0)
                if stop_loss and action.get("use_risk_sizing", True):
                    size = self.portfolio.position_size_from_risk(self.risk_per_trade, entry_price, stop_loss)
                    if size <= 0:
                        continue

                trade = Trade(
                    instrument=instrument,
                    direction=direction,
                    entry_price=entry_price,
                    entry_date=date,
                    stop_loss=stop_loss,
                    take_profit=take_profit,
                    size=size,
                    reason=reason,
                )
                self.portfolio.open_trade(trade)
                # Deduct entry commission from cash
                self.portfolio.cash -= self._commission_cost(instrument, size)

            elif act_type == "close":
                trade_id = action["trade_id"]
                trade_obj = self.portfolio.open_trades.get(trade_id)
                if trade_obj is None:
                    continue
                price = self._current_prices.get(trade_obj.instrument, 0)
                exit_slip = self._exit_cost(trade_obj.instrument)
                # Slippage worsens exit
                if trade_obj.direction == "long":
                    price = price - exit_slip
                else:
                    price = price + exit_slip
                commission = self._commission_cost(trade_obj.instrument, trade_obj.size)
                self.portfolio.close_trade(trade_id, price, date, action.get("reason", "manual_close"))
                self.portfolio.cash -= commission

    def report(self) -> Dict:
        """Generate full performance report."""
        from . import metrics as m

        all_trades = self.portfolio.closed_trades
        equity = self.portfolio.equity_curve()
        eq_values = [e[1] for e in equity]
        returns = []
        for i in range(1, len(eq_values)):
            if eq_values[i - 1] != 0:
                returns.append(eq_values[i] / eq_values[i - 1] - 1)

        trades_list = [t.to_dict() for t in all_trades]

        # Compute metrics
        total_return = (eq_values[-1] / self.initial_capital - 1) * 100 if eq_values else 0
        max_dd, dd_start, dd_end = m.max_drawdown(eq_values) if eq_values else (0, "", "")

        report = {
            "strategy": self.strategy.name,
            "instruments": list(self._all_bars.keys()),
            "period": {
                "start": self._all_dates[0] if self._all_dates else "",
                "end": self._all_dates[-1] if self._all_dates else "",
                "bars": len(self._all_dates),
            },
            "capital": {
                "initial": self.initial_capital,
                "final": round(eq_values[-1], 2) if eq_values else self.initial_capital,
                "total_return_pct": round(total_return, 2),
            },
            "trades": {
                "total": len(all_trades),
                "winners": sum(1 for t in all_trades if t.pnl > 0),
                "losers": sum(1 for t in all_trades if t.pnl <= 0),
                "win_rate": round(m.win_rate(all_trades), 2),
                "avg_pnl": round(sum(t.pnl for t in all_trades) / len(all_trades), 4) if all_trades else 0,
                "avg_winner": round(
                    sum(t.pnl for t in all_trades if t.pnl > 0) / max(1, sum(1 for t in all_trades if t.pnl > 0)), 4
                ),
                "avg_loser": round(
                    sum(t.pnl for t in all_trades if t.pnl <= 0) / max(1, sum(1 for t in all_trades if t.pnl <= 0)), 4
                ),
                "profit_factor": round(m.profit_factor(all_trades), 2),
                "expectancy": round(m.expectancy(all_trades), 4),
                "avg_bars_held": round(m.avg_holding_period(all_trades), 1),
            },
            "risk": {
                "sharpe_ratio": round(m.sharpe_ratio(returns), 3) if returns else 0,
                "sortino_ratio": round(m.sortino_ratio(returns), 3) if returns else 0,
                "max_drawdown_pct": round(max_dd, 2),
                "calmar_ratio": round(m.calmar_ratio(returns, max_dd), 3) if returns and max_dd else 0,
                "recovery_factor": round(
                    m.recovery_factor(eq_values[-1] - self.initial_capital, max_dd * self.initial_capital / 100), 2
                )
                if eq_values and max_dd
                else 0,
            },
            "costs": {
                "slippage_pips": self.slippage_pips,
                "commission_pips": self.commission_pips,
                "spread_pips": self.spread_pips,
            },
            "equity_curve": equity,
            "trade_log": trades_list,
        }

        return report
