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

import json
import os
import math
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any


# ---------------------------------------------------------------------------
# Trade
# ---------------------------------------------------------------------------

class Trade:
    """Represents a single trade with full lifecycle tracking."""

    _next_id = 1

    def __init__(
        self,
        instrument: str,
        direction: str,
        entry_price: float,
        entry_date: str,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None,
        size: float = 1.0,
        reason: str = "",
    ):
        self.id = Trade._next_id
        Trade._next_id += 1
        self.instrument = instrument
        self.direction = direction  # "long" or "short"
        self.entry_price = entry_price
        self.entry_date = entry_date
        self.stop_loss = stop_loss
        self.take_profit = take_profit
        self.size = size
        self.reason = reason

        # Filled on close
        self.exit_price: Optional[float] = None
        self.exit_date: Optional[str] = None
        self.exit_reason: str = ""
        self.pnl: float = 0.0
        self.pnl_pct: float = 0.0
        self.bars_held: int = 0
        self.is_open: bool = True

    def close(self, exit_price: float, exit_date: str, reason: str = "") -> float:
        """Close the trade and compute P&L."""
        self.exit_price = exit_price
        self.exit_date = exit_date
        self.exit_reason = reason
        self.is_open = False

        if self.direction == "long":
            self.pnl = (exit_price - self.entry_price) * self.size
            self.pnl_pct = (exit_price / self.entry_price - 1) * 100
        else:
            self.pnl = (self.entry_price - exit_price) * self.size
            self.pnl_pct = (self.entry_price / exit_price - 1) * 100 if exit_price else 0

        return self.pnl

    def unrealized_pnl(self, current_price: float) -> float:
        """Calculate unrealized P&L at current price."""
        if self.direction == "long":
            return (current_price - self.entry_price) * self.size
        else:
            return (self.entry_price - current_price) * self.size

    def check_stop_loss(self, high: float, low: float) -> bool:
        """Check if stop loss was hit during this bar."""
        if self.stop_loss is None:
            return False
        if self.direction == "long":
            return low <= self.stop_loss
        else:
            return high >= self.stop_loss

    def check_take_profit(self, high: float, low: float) -> bool:
        """Check if take profit was hit during this bar."""
        if self.take_profit is None:
            return False
        if self.direction == "long":
            return high >= self.take_profit
        else:
            return low <= self.take_profit

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "instrument": self.instrument,
            "direction": self.direction,
            "entry_price": self.entry_price,
            "entry_date": self.entry_date,
            "exit_price": self.exit_price,
            "exit_date": self.exit_date,
            "stop_loss": self.stop_loss,
            "take_profit": self.take_profit,
            "size": self.size,
            "reason": self.reason,
            "exit_reason": self.exit_reason,
            "pnl": round(self.pnl, 4),
            "pnl_pct": round(self.pnl_pct, 4),
            "bars_held": self.bars_held,
            "is_open": self.is_open,
        }


# ---------------------------------------------------------------------------
# Portfolio
# ---------------------------------------------------------------------------

class Portfolio:
    """Track portfolio state, equity, positions, and risk."""

    def __init__(self, initial_capital: float = 100000.0):
        self.initial_capital = initial_capital
        self.cash = initial_capital
        self.open_trades: Dict[int, Trade] = {}
        self.closed_trades: List[Trade] = []
        self._equity_history: List[Tuple[str, float]] = []
        self._peak_equity: float = initial_capital

    @property
    def equity(self) -> float:
        return self.cash + sum(t.pnl for t in self.open_trades.values())

    def open_trade(self, trade: Trade) -> int:
        """Open a new trade. Returns trade id."""
        self.open_trades[trade.id] = trade
        return trade.id

    def close_trade(
        self, trade_id: int, exit_price: float, exit_date: str, reason: str = ""
    ) -> Optional[float]:
        """Close an open trade. Returns realized P&L or None if not found."""
        trade = self.open_trades.pop(trade_id, None)
        if trade is None:
            return None
        pnl = trade.close(exit_price, exit_date, reason)
        self.cash += pnl
        self.closed_trades.append(trade)
        return pnl

    def close_all(self, prices: Dict[str, float], date: str, reason: str = "end_of_backtest"):
        """Close all open positions at given prices."""
        for trade_id in list(self.open_trades.keys()):
            trade = self.open_trades[trade_id]
            price = prices.get(trade.instrument)
            if price is not None:
                self.close_trade(trade_id, price, date, reason)

    def record_equity(self, date: str, prices: Dict[str, float]):
        """Snapshot equity at end of bar."""
        unrealized = 0.0
        for t in self.open_trades.values():
            p = prices.get(t.instrument)
            if p is not None:
                unrealized += t.unrealized_pnl(p)
        eq = self.cash + unrealized
        self._equity_history.append((date, eq))
        if eq > self._peak_equity:
            self._peak_equity = eq

    def equity_curve(self) -> List[Tuple[str, float]]:
        return list(self._equity_history)

    def position_size_from_risk(
        self, risk_pct: float, entry_price: float, stop_loss: float
    ) -> float:
        """Calculate position size based on risk percentage of equity.
        Returns number of units (contracts/lots).
        risk_pct: e.g. 0.01 for 1% risk
        """
        risk_per_unit = abs(entry_price - stop_loss)
        if risk_per_unit <= 0:
            return 0.0
        risk_amount = self.equity * risk_pct
        return risk_amount / risk_per_unit

    def max_open_trades(self) -> int:
        """Return maximum concurrent open trades seen so far."""
        return max(len(self.open_trades), 0)


# ---------------------------------------------------------------------------
# Bar
# ---------------------------------------------------------------------------

class Bar:
    """A single data bar combining price and COT data for one instrument/date."""

    def __init__(
        self,
        date: str,
        instrument: str,
        price: float,
        high: Optional[float] = None,
        low: Optional[float] = None,
        spec_net: Optional[int] = None,
        spec_long: Optional[int] = None,
        spec_short: Optional[int] = None,
        open_interest: Optional[int] = None,
    ):
        self.date = date
        self.instrument = instrument
        self.price = price  # close price
        self.high = high if high is not None else price
        self.low = low if low is not None else price
        self.close = price
        self.spec_net = spec_net
        self.spec_long = spec_long
        self.spec_short = spec_short
        self.open_interest = open_interest

    def __repr__(self):
        return f"Bar({self.date}, {self.instrument}, close={self.price})"


# ---------------------------------------------------------------------------
# Data Loader
# ---------------------------------------------------------------------------

class DataLoader:
    """Load and merge price + COT data from the cot-explorer data directory."""

    # COT symbol -> price key mapping (from cot_map.json)
    DEFAULT_COT_MAP = {
        "099741": "eurusd",
        "096742": "usdjpy",
        "092741": "gbpusd",
        "232741": "audusd",
        "088691": "gold",
        "084691": "silver",
        "067651": "wti",
        "023651": "brent",
        "133741": "spx",
        "209742": "nas100",
        "098662": "dxy",
        "002602": "corn",
        "001602": "wheat",
        "005602": "soybean",
        "083731": "sugar",
        "073732": "coffee",
        "080732": "cocoa",
    }

    # Reverse: price key -> list of COT symbols
    PRICE_TO_COT = {}
    for cot_sym, price_key in DEFAULT_COT_MAP.items():
        PRICE_TO_COT.setdefault(price_key, []).append(cot_sym)

    # Report type preference order
    REPORT_PREF = ["tff", "legacy", "disaggregated", "supplemental"]

    def __init__(self, data_dir: str):
        self.data_dir = data_dir
        self.prices_dir = os.path.join(data_dir, "prices")
        self.timeseries_dir = os.path.join(data_dir, "timeseries")
        self.cot_map = self._load_cot_map()

    def _load_cot_map(self) -> Dict[str, str]:
        path = os.path.join(self.prices_dir, "cot_map.json")
        if os.path.exists(path):
            with open(path, "r") as f:
                return json.load(f)
        return dict(self.DEFAULT_COT_MAP)

    def available_instruments(self) -> List[str]:
        """List instruments that have price data."""
        instruments = []
        if os.path.isdir(self.prices_dir):
            for fname in os.listdir(self.prices_dir):
                if fname.endswith(".json") and fname != "cot_map.json":
                    instruments.append(fname.replace(".json", ""))
        return sorted(instruments)

    def load_prices(self, instrument: str) -> List[Dict]:
        """Load price data: returns list of {date, price}."""
        path = os.path.join(self.prices_dir, f"{instrument}.json")
        if not os.path.exists(path):
            return []
        with open(path, "r") as f:
            data = json.load(f)
        return data.get("data", [])

    def load_cot(self, instrument: str) -> List[Dict]:
        """Load COT timeseries for an instrument. Tries preferred report types."""
        cot_symbols = self.PRICE_TO_COT.get(instrument, [])
        if not cot_symbols:
            # Try reverse lookup from loaded map
            rev = {}
            for k, v in self.cot_map.items():
                rev.setdefault(v, []).append(k)
            cot_symbols = rev.get(instrument, [])

        for cot_sym in cot_symbols:
            for report in self.REPORT_PREF:
                path = os.path.join(self.timeseries_dir, f"{cot_sym}_{report}.json")
                if os.path.exists(path):
                    with open(path, "r") as f:
                        data = json.load(f)
                    return data.get("data", [])
        return []

    def load_merged(
        self,
        instrument: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> List[Bar]:
        """Load and merge price + COT data for an instrument.

        Price data is weekly (each date = one bar).
        COT data is also weekly, aligned by nearest date.
        Returns chronologically sorted list of Bar objects.
        """
        prices = self.load_prices(instrument)
        cot_data = self.load_cot(instrument)

        # Build COT lookup by date
        cot_by_date: Dict[str, Dict] = {}
        for row in cot_data:
            cot_by_date[row["date"]] = row

        bars = []
        last_cot = None

        for row in prices:
            date_str = row["date"]
            price = row["price"]

            # Date filtering
            if start_date and date_str < start_date:
                continue
            if end_date and date_str > end_date:
                continue

            # Find matching COT data (exact date or nearest previous)
            cot = cot_by_date.get(date_str)
            if cot is None:
                # Find nearest previous COT date (within 10 days)
                d = datetime.strptime(date_str, "%Y-%m-%d")
                for offset in range(1, 11):
                    candidate = (d - timedelta(days=offset)).strftime("%Y-%m-%d")
                    if candidate in cot_by_date:
                        cot = cot_by_date[candidate]
                        break

            if cot is None:
                cot = last_cot  # carry forward
            else:
                last_cot = cot

            bar = Bar(
                date=date_str,
                instrument=instrument,
                price=price,
                spec_net=cot["spec_net"] if cot else None,
                spec_long=cot["spec_long"] if cot else None,
                spec_short=cot["spec_short"] if cot else None,
                open_interest=cot["oi"] if cot else None,
            )
            bars.append(bar)

        return bars


# ---------------------------------------------------------------------------
# Technical Indicators (stdlib only)
# ---------------------------------------------------------------------------

class Indicators:
    """Technical indicator calculations operating on lists of Bar objects."""

    @staticmethod
    def sma(bars: List[Bar], period: int) -> Optional[float]:
        """Simple Moving Average of close prices over last `period` bars."""
        if len(bars) < period:
            return None
        return sum(b.close for b in bars[-period:]) / period

    @staticmethod
    def ema(bars: List[Bar], period: int) -> Optional[float]:
        """Exponential Moving Average of close prices."""
        if len(bars) < period + 1:
            return None
        k = 2.0 / (period + 1)
        closes = [b.close for b in bars]
        ema_val = sum(closes[:period]) / period
        for c in closes[period:]:
            ema_val = c * k + ema_val * (1 - k)
        return ema_val

    @staticmethod
    def atr(bars: List[Bar], period: int = 14) -> Optional[float]:
        """Average True Range."""
        if len(bars) < period + 1:
            return None
        trs = []
        for i in range(1, len(bars)):
            h, l, pc = bars[i].high, bars[i].low, bars[i - 1].close
            tr = max(h - l, abs(h - pc), abs(l - pc))
            trs.append(tr)
        if len(trs) < period:
            return None
        return sum(trs[-period:]) / period

    @staticmethod
    def rsi(bars: List[Bar], period: int = 14) -> Optional[float]:
        """Relative Strength Index."""
        if len(bars) < period + 1:
            return None
        changes = [bars[i].close - bars[i - 1].close for i in range(1, len(bars))]
        if len(changes) < period:
            return None

        gains = [max(c, 0) for c in changes[-period:]]
        losses = [max(-c, 0) for c in changes[-period:]]
        avg_gain = sum(gains) / period
        avg_loss = sum(losses) / period

        if avg_loss == 0:
            return 100.0
        rs = avg_gain / avg_loss
        return 100.0 - (100.0 / (1.0 + rs))

    @staticmethod
    def macd(bars: List[Bar], fast: int = 12, slow: int = 26, signal: int = 9):
        """MACD line, signal line, histogram. Returns (macd, signal, hist) or None."""
        if len(bars) < slow + signal:
            return None
        closes = [b.close for b in bars]

        def _ema(data, n):
            k = 2.0 / (n + 1)
            e = sum(data[:n]) / n
            result = [e]
            for v in data[n:]:
                e = v * k + e * (1 - k)
                result.append(e)
            return result

        ema_fast = _ema(closes, fast)
        ema_slow = _ema(closes, slow)

        # Align lengths
        diff = len(ema_fast) - len(ema_slow)
        macd_line = [ema_fast[i + diff] - ema_slow[i] for i in range(len(ema_slow))]

        if len(macd_line) < signal:
            return None

        sig_line = _ema(macd_line, signal)
        diff2 = len(macd_line) - len(sig_line)
        hist = macd_line[-1] - sig_line[-1]

        return (macd_line[-1], sig_line[-1], hist)

    @staticmethod
    def spec_net_change(bars: List[Bar], weeks: int = 3) -> Optional[int]:
        """Change in speculator net position over N weeks."""
        relevant = [b for b in bars if b.spec_net is not None]
        if len(relevant) < weeks + 1:
            return None
        return relevant[-1].spec_net - relevant[-(weeks + 1)].spec_net

    @staticmethod
    def spec_net_trend(bars: List[Bar], weeks: int = 3) -> Optional[str]:
        """Direction of spec_net over last N weeks: 'increasing', 'decreasing', or 'flat'."""
        relevant = [b for b in bars if b.spec_net is not None]
        if len(relevant) < weeks + 1:
            return None
        values = [b.spec_net for b in relevant[-(weeks + 1):]]
        increases = sum(1 for i in range(1, len(values)) if values[i] > values[i - 1])
        decreases = sum(1 for i in range(1, len(values)) if values[i] < values[i - 1])
        if increases >= weeks:
            return "increasing"
        elif decreases >= weeks:
            return "decreasing"
        return "flat"

    @staticmethod
    def cot_pct(bar: Bar) -> Optional[float]:
        """Spec net as percentage of open interest."""
        if bar.spec_net is None or bar.open_interest is None or bar.open_interest == 0:
            return None
        return (bar.spec_net / bar.open_interest) * 100


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
    ):
        self.strategy = strategy
        self.data_dir = data_dir
        self.instruments = instruments
        self.start_date = start_date
        self.end_date = end_date
        self.initial_capital = initial_capital
        self.risk_per_trade = risk_per_trade

        self.loader = DataLoader(data_dir)
        self.portfolio = Portfolio(initial_capital)
        self.indicators = Indicators()

        # Populated by load_data()
        self._all_bars: Dict[str, List[Bar]] = {}
        self._all_dates: List[str] = []
        self._current_prices: Dict[str, float] = {}

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
            actions = self.strategy.on_bar(
                date, bars_by_inst, self.portfolio, self
            )

            # Process strategy actions
            self._process_actions(date, actions)

            # Record equity
            self.portfolio.record_equity(date, self._current_prices)

        # Close remaining positions at last known prices
        if self._all_dates:
            last_date = self._all_dates[-1]
            self.portfolio.close_all(self._current_prices, last_date)

        return self.report()

    def _process_exits(self, date: str, bars_by_inst: Dict[str, List[Bar]]):
        """Check stop loss and take profit for all open trades."""
        for trade_id in list(self.portfolio.open_trades.keys()):
            trade = self.portfolio.open_trades[trade_id]
            inst_bars = bars_by_inst.get(trade.instrument, [])
            if not inst_bars:
                continue
            current_bar = inst_bars[-1]
            if current_bar.date != date:
                continue

            h = current_bar.high
            l = current_bar.low

            # Stop loss hit first (conservative: assume worst case)
            if trade.check_stop_loss(h, l):
                exit_price = trade.stop_loss
                self.portfolio.close_trade(trade_id, exit_price, date, "stop_loss")
            elif trade.check_take_profit(h, l):
                exit_price = trade.take_profit
                self.portfolio.close_trade(trade_id, exit_price, date, "take_profit")

    def _process_actions(self, date: str, actions: List[Dict]):
        """Execute trade actions from the strategy."""
        for action in actions:
            act_type = action.get("action")

            if act_type == "open":
                entry_price = action["entry_price"]
                stop_loss = action.get("stop_loss")
                take_profit = action.get("take_profit")
                instrument = action["instrument"]
                direction = action["direction"]
                reason = action.get("reason", "")

                # Calculate size from risk if stop_loss provided
                size = action.get("size", 1.0)
                if stop_loss and action.get("use_risk_sizing", True):
                    size = self.portfolio.position_size_from_risk(
                        self.risk_per_trade, entry_price, stop_loss
                    )
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

            elif act_type == "close":
                trade_id = action["trade_id"]
                price = self._current_prices.get(
                    self.portfolio.open_trades.get(trade_id, Trade("", "", 0, "")).instrument,
                    0,
                )
                self.portfolio.close_trade(
                    trade_id, price, date, action.get("reason", "manual_close")
                )

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
                ) if eq_values and max_dd else 0,
            },
            "equity_curve": equity,
            "trade_log": trades_list,
        }

        return report
