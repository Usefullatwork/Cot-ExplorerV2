"""Paper-trading broker adapter.

Simulates broker operations in memory — no real orders are placed.
Optionally models slippage, partial fills, and requotes for realistic
back-testing when the corresponding flags are enabled.
"""

from __future__ import annotations

import math
import random
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

    Optional enhancements (all OFF by default for backward compat):

    - ``enable_slippage``:  lognormal slippage on every fill.
    - ``enable_partial_fills``:  large orders (>5 lots) get partial fills.
    - ``enable_requotes``:  small probability of requote with extra slippage.
    """

    def __init__(
        self,
        initial_balance: float = 10_000.0,
        enable_slippage: bool = False,
        enable_partial_fills: bool = False,
        enable_requotes: bool = False,
        slippage_seed: int = 42,
    ) -> None:
        self._connected: bool = False
        self._positions: dict[str, BrokerPosition] = {}
        self._balance: float = initial_balance
        self._next_id: int = 1
        self._prices: dict[str, Price] = {}

        # Enhancement flags
        self._enable_slippage = enable_slippage
        self._enable_partial_fills = enable_partial_fills
        self._enable_requotes = enable_requotes
        self._rng = random.Random(slippage_seed)

        # Every fill is recorded here for post-trade analysis.
        self.execution_log: list[dict] = []

        # Configurable VIX for requote probability scaling.
        self._current_vix: float = 15.0

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

    def set_vix(self, vix: float) -> None:
        """Set the current VIX level for requote probability scaling."""
        self._current_vix = vix

    # -- slippage / requote helpers -------------------------------------------

    def _sample_slippage(self) -> float:
        """Sample slippage from a lognormal distribution (pips).

        Mean 0.3 pips, std 0.2 pips — converted to lognormal mu/sigma.
        """
        mean, std = 0.3, 0.2
        variance = std ** 2
        mu = math.log(mean ** 2 / math.sqrt(variance + mean ** 2))
        sigma = math.sqrt(math.log(1 + variance / mean ** 2))
        return self._rng.lognormvariate(mu, sigma)

    def _apply_slippage(
        self, base_price: float, direction: str, pips: float,
    ) -> float:
        """Adjust price by slippage — worse for the trader.

        Buy (bull) fills higher, sell (bear) fills lower.
        Assumes 1 pip = 0.0001 for most instruments.
        """
        pip_value = 0.0001
        if direction == "bull":
            return base_price + pips * pip_value
        return base_price - pips * pip_value

    def _check_requote(self) -> tuple[bool, float]:
        """Determine if a requote occurs and sample extra slippage.

        Returns ``(requoted, extra_slippage_pips)``.
        """
        prob = 0.02 if self._current_vix <= 30.0 else 0.10
        requoted = self._rng.random() < prob
        extra = self._sample_slippage() if requoted else 0.0
        return requoted, extra

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

        When enhancement flags are enabled the fill may include slippage,
        partial fills, or requotes.  All details are appended to
        ``execution_log``.
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
        base_fill = price.ask if (price and direction == "bull") else (
            price.bid if price else 0.0
        )

        # --- slippage ---
        slippage_pips = 0.0
        if self._enable_slippage:
            slippage_pips = self._sample_slippage()

        # --- requote ---
        requoted = False
        if self._enable_requotes:
            requoted, extra = self._check_requote()
            slippage_pips += extra

        adjusted_fill = (
            self._apply_slippage(base_fill, direction, slippage_pips)
            if slippage_pips > 0 else base_fill
        )

        # --- partial fills ---
        fill_pct = 1.0
        partial = False
        if self._enable_partial_fills and lots > 5.0:
            fill_pct = self._rng.uniform(0.7, 1.0)
            partial = True

        filled_lots = lots * fill_pct

        pid = f"PAPER-{self._next_id}"
        self._next_id += 1

        self._positions[pid] = BrokerPosition(
            position_id=pid,
            instrument=symbol,
            direction=direction,
            lots=filled_lots,
            entry_price=adjusted_fill,
            current_price=adjusted_fill,
            stop_loss=sl,
            take_profit=tp,
            pnl=0.0,
            opened_at=now,
        )

        # --- execution log ---
        self.execution_log.append({
            "instrument": symbol,
            "direction": direction,
            "requested_price": base_fill,
            "fill_price": adjusted_fill,
            "slippage_pips": slippage_pips,
            "filled": True,
            "partial": partial,
            "fill_pct": fill_pct,
            "requoted": requoted,
            "timestamp": now,
        })

        return OrderResult(
            success=True,
            position_id=pid,
            fill_price=adjusted_fill,
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
