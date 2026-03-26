"""
Data models for the backtesting framework.

Classes:
    Trade     - Single trade with full lifecycle tracking
    Portfolio - Track portfolio state, equity, positions, and risk
    Bar       - A single data bar combining price and COT data
"""

from typing import Dict, List, Optional, Tuple

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

    def close_trade(self, trade_id: int, exit_price: float, exit_date: str, reason: str = "") -> Optional[float]:
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

    def position_size_from_risk(self, risk_pct: float, entry_price: float, stop_loss: float) -> float:
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
