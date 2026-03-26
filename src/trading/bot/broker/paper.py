"""Paper-trading broker adapter.

Simulates broker operations in memory — no real orders are placed.
"""

from __future__ import annotations

from datetime import datetime, timezone

from src.trading.bot.broker.base import (
    AccountInfo,
    BrokerAdapter,
    BrokerPosition,
    OrderResult,
    Price,
)


class PaperAdapter(BrokerAdapter):
    """Simulates broker operations for testing.

    Tracks positions in memory and simulates fills at the current cached
    price.  Starts with a configurable paper balance (default $10 000).
    """

    def __init__(self, initial_balance: float = 10_000.0) -> None:
        self._connected: bool = False
        self._positions: dict[str, BrokerPosition] = {}
        self._balance: float = initial_balance
        self._next_id: int = 1
        self._prices: dict[str, Price] = {}

    # -- connection lifecycle -------------------------------------------------

    async def connect(self) -> bool:
        """Mark the adapter as connected."""
        self._connected = True
        return True

    async def disconnect(self) -> None:
        """Mark the adapter as disconnected."""
        self._connected = False

    async def is_connected(self) -> bool:
        """Return current connection flag."""
        return self._connected

    # -- account --------------------------------------------------------------

    async def get_account(self) -> AccountInfo:
        """Return account info derived from balance and open P&L."""
        unrealised = sum(p.pnl for p in self._positions.values())
        return AccountInfo(
            balance=self._balance,
            equity=self._balance + unrealised,
            margin_used=0.0,
            currency="USD",
        )

    # -- orders ---------------------------------------------------------------

    async def market_order(
        self,
        symbol: str,
        direction: str,
        lots: float,
        sl: float | None = None,
        tp: float | None = None,
    ) -> OrderResult:
        """Simulate a market fill at the last cached price for *symbol*.

        If no price has been cached yet, the fill is recorded at 0.0 and
        should be updated on the next price tick.
        """
        if not self._connected:
            return OrderResult(
                success=False,
                position_id=None,
                fill_price=None,
                error="Adapter not connected",
            )

        now = datetime.now(timezone.utc).isoformat()
        price = self._prices.get(symbol)
        fill = price.ask if (price and direction == "bull") else (
            price.bid if price else 0.0
        )

        pid = f"PAPER-{self._next_id}"
        self._next_id += 1

        self._positions[pid] = BrokerPosition(
            position_id=pid,
            instrument=symbol,
            direction=direction,
            lots=lots,
            entry_price=fill,
            current_price=fill,
            stop_loss=sl,
            take_profit=tp,
            pnl=0.0,
            opened_at=now,
        )

        return OrderResult(
            success=True,
            position_id=pid,
            fill_price=fill,
            error=None,
        )

    async def close_position(
        self, position_id: str, pct: float = 1.0
    ) -> OrderResult:
        """Close (fully or partially) a paper position.

        Realised P&L is added to the cash balance.  Partial closes reduce
        the position's lot size proportionally.
        """
        pos = self._positions.get(position_id)
        if pos is None:
            return OrderResult(
                success=False,
                position_id=position_id,
                fill_price=None,
                error=f"Position {position_id} not found",
            )

        pct = max(0.0, min(pct, 1.0))
        close_lots = pos.lots * pct
        realised_pnl = pos.pnl * pct

        self._balance += realised_pnl

        price = self._prices.get(pos.instrument)
        close_price = (
            price.bid if (price and pos.direction == "bull") else (
                price.ask if price else pos.current_price
            )
        )

        if pct >= 1.0:
            del self._positions[position_id]
        else:
            pos.lots -= close_lots
            pos.pnl -= realised_pnl

        return OrderResult(
            success=True,
            position_id=position_id,
            fill_price=close_price,
            error=None,
        )

    async def modify_sl(self, position_id: str, new_sl: float) -> bool:
        """Update the stop-loss on a paper position."""
        pos = self._positions.get(position_id)
        if pos is None:
            return False
        pos.stop_loss = new_sl
        return True

    # -- queries --------------------------------------------------------------

    async def get_positions(self) -> list[BrokerPosition]:
        """Return a list of all open paper positions."""
        return list(self._positions.values())

    async def get_price(self, symbol: str) -> Price:
        """Return the last cached price for *symbol*.

        Call :meth:`set_price` to feed in external price data.  If no
        price has been cached yet a zero quote is returned.
        """
        return self._prices.get(
            symbol,
            Price(bid=0.0, ask=0.0, timestamp=datetime.now(timezone.utc).isoformat()),
        )

    # -- paper-only helpers ---------------------------------------------------

    def set_price(self, symbol: str, bid: float, ask: float) -> None:
        """Inject a price tick (paper-only convenience method).

        Also updates `current_price` and `pnl` on every open position
        for this instrument.
        """
        now = datetime.now(timezone.utc).isoformat()
        self._prices[symbol] = Price(bid=bid, ask=ask, timestamp=now)

        for pos in self._positions.values():
            if pos.instrument != symbol:
                continue
            if pos.direction == "bull":
                pos.current_price = bid
                pos.pnl = (bid - pos.entry_price) * pos.lots * 100_000
            else:
                pos.current_price = ask
                pos.pnl = (pos.entry_price - ask) * pos.lots * 100_000
