"""Abstract broker adapter interface.

Defines the contract that all broker adapters (paper, demo, live) must
implement.  Every method is async to allow non-blocking I/O in real
broker integrations.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class AccountInfo:
    """Snapshot of broker account state."""

    balance: float
    equity: float
    margin_used: float
    currency: str  # "USD", "EUR", etc.


@dataclass
class OrderResult:
    """Result returned after placing or closing an order."""

    success: bool
    position_id: str | None
    fill_price: float | None
    error: str | None


@dataclass
class BrokerPosition:
    """A single open position as reported by the broker."""

    position_id: str
    instrument: str
    direction: str  # "bull" / "bear"
    lots: float
    entry_price: float
    current_price: float
    stop_loss: float | None
    take_profit: float | None
    pnl: float
    opened_at: str  # ISO-8601 datetime


@dataclass
class Price:
    """Bid/ask quote for an instrument."""

    bid: float
    ask: float
    timestamp: str  # ISO-8601 datetime


class BrokerAdapter(ABC):
    """Abstract interface for broker connections.

    All methods are async for non-blocking I/O.  Concrete adapters must
    implement every abstract method.
    """

    @abstractmethod
    async def connect(self) -> bool:
        """Establish connection to the broker.  Returns True on success."""
        ...

    @abstractmethod
    async def disconnect(self) -> None:
        """Gracefully close the broker connection."""
        ...

    @abstractmethod
    async def is_connected(self) -> bool:
        """Return True if the adapter is currently connected."""
        ...

    @abstractmethod
    async def get_account(self) -> AccountInfo:
        """Fetch current account balance, equity, and margin."""
        ...

    @abstractmethod
    async def market_order(
        self,
        symbol: str,
        direction: str,
        lots: float,
        sl: float | None = None,
        tp: float | None = None,
    ) -> OrderResult:
        """Place a market order.

        Args:
            symbol: Instrument identifier (e.g. "EURUSD").
            direction: "bull" for long, "bear" for short.
            lots: Position size in standard lots.
            sl: Optional stop-loss price.
            tp: Optional take-profit price.
        """
        ...

    @abstractmethod
    async def close_position(
        self, position_id: str, pct: float = 1.0
    ) -> OrderResult:
        """Close an open position (fully or partially).

        Args:
            position_id: Broker-assigned position identifier.
            pct: Fraction to close (1.0 = full close, 0.5 = half).
        """
        ...

    @abstractmethod
    async def modify_sl(self, position_id: str, new_sl: float) -> bool:
        """Move the stop-loss on an open position.  Returns True on success."""
        ...

    @abstractmethod
    async def get_positions(self) -> list[BrokerPosition]:
        """Return all currently open positions."""
        ...

    @abstractmethod
    async def get_price(self, symbol: str) -> Price:
        """Fetch the latest bid/ask quote for *symbol*."""
        ...
