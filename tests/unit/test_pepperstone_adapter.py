"""Unit tests for Pepperstone cTrader broker adapter safety guards."""

from __future__ import annotations

import logging

import pytest

from src.trading.bot.broker.base import BrokerAdapter
from src.trading.bot.broker.pepperstone import PepperstoneAdapter

# ---------------------------------------------------------------------------
# Safety guard tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_connect_raises_not_implemented():
    """connect() must raise NotImplementedError while endpoints are unverified."""
    adapter = PepperstoneAdapter(api_key="test", account_id="123", demo=True)
    with pytest.raises(NotImplementedError, match="cTrader endpoints not yet verified"):
        await adapter.connect()


@pytest.mark.asyncio
async def test_market_order_raises_not_implemented():
    """market_order() must raise NotImplementedError while endpoints are unverified."""
    adapter = PepperstoneAdapter(api_key="test", account_id="123", demo=True)
    with pytest.raises(NotImplementedError, match="cTrader endpoints not yet verified"):
        await adapter.market_order("EURUSD", "bull", 0.1)


def test_init_live_logs_warning(caplog):
    """Constructing with demo=False logs a production-readiness warning."""
    with caplog.at_level(logging.WARNING, logger="src.trading.bot.broker.pepperstone"):
        PepperstoneAdapter(api_key="test", account_id="123", demo=False)
    assert any("not production-ready" in msg for msg in caplog.messages)


def test_adapter_implements_interface():
    """PepperstoneAdapter must be a subclass of BrokerAdapter."""
    assert issubclass(PepperstoneAdapter, BrokerAdapter)
