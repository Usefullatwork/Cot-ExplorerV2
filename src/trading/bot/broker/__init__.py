"""Broker adapter layer — abstract interface + concrete adapters."""

from __future__ import annotations

from src.trading.bot.broker.base import (
    AccountInfo,
    BrokerAdapter,
    BrokerPosition,
    OrderResult,
    Price,
)
from src.trading.bot.broker.paper import PaperAdapter

__all__ = [
    "AccountInfo",
    "BrokerAdapter",
    "BrokerPosition",
    "OrderResult",
    "PaperAdapter",
    "Price",
]
