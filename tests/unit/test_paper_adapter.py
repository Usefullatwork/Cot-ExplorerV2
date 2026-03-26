"""Unit tests for src.trading.bot.broker.paper — PaperAdapter simulated broker."""

from __future__ import annotations

import pytest

from src.trading.bot.broker.paper import PaperAdapter


# ===== Connection lifecycle ====================================================


class TestConnection:
    """Connect / disconnect lifecycle."""

    async def test_connect(self):
        adapter = PaperAdapter()
        result = await adapter.connect()
        assert result is True
        assert await adapter.is_connected() is True

    async def test_disconnect(self):
        adapter = PaperAdapter()
        await adapter.connect()
        await adapter.disconnect()
        assert await adapter.is_connected() is False

    async def test_not_connected_by_default(self):
        adapter = PaperAdapter()
        assert await adapter.is_connected() is False


# ===== Market orders ===========================================================


class TestMarketOrder:
    """Simulated market orders."""

    async def test_market_order_long(self):
        """Bull market order fills at ask price."""
        adapter = PaperAdapter(initial_balance=10_000.0)
        await adapter.connect()
        adapter.set_price("EURUSD", bid=1.0990, ask=1.1000)
        result = await adapter.market_order("EURUSD", "bull", 0.10, sl=1.0950, tp=1.1050)
        assert result.success is True
        assert result.position_id is not None
        assert result.fill_price == 1.1000  # ask
        assert result.error is None

    async def test_market_order_short(self):
        """Bear market order fills at bid price."""
        adapter = PaperAdapter()
        await adapter.connect()
        adapter.set_price("EURUSD", bid=1.0990, ask=1.1000)
        result = await adapter.market_order("EURUSD", "bear", 0.10, sl=1.1050)
        assert result.success is True
        assert result.fill_price == 1.0990  # bid

    async def test_market_order_not_connected(self):
        """Order rejected when adapter is not connected."""
        adapter = PaperAdapter()
        result = await adapter.market_order("EURUSD", "bull", 0.10)
        assert result.success is False
        assert "not connected" in result.error.lower()

    async def test_market_order_no_price_fills_at_zero(self):
        """Order fills at 0.0 if no price has been cached."""
        adapter = PaperAdapter()
        await adapter.connect()
        result = await adapter.market_order("EURUSD", "bull", 0.10)
        assert result.success is True
        assert result.fill_price == 0.0


# ===== Position management ====================================================


class TestClosePosition:
    """Close full / partial positions."""

    async def test_close_position_full(self):
        """Full close removes the position."""
        adapter = PaperAdapter(initial_balance=10_000.0)
        await adapter.connect()
        adapter.set_price("EURUSD", bid=1.1000, ask=1.1002)
        order = await adapter.market_order("EURUSD", "bull", 0.10)
        pid = order.position_id

        result = await adapter.close_position(pid, pct=1.0)
        assert result.success is True
        positions = await adapter.get_positions()
        assert len(positions) == 0

    async def test_close_position_partial(self):
        """Partial close reduces lot size proportionally."""
        adapter = PaperAdapter()
        await adapter.connect()
        adapter.set_price("EURUSD", bid=1.1000, ask=1.1002)
        order = await adapter.market_order("EURUSD", "bull", 1.0)
        pid = order.position_id

        result = await adapter.close_position(pid, pct=0.5)
        assert result.success is True
        positions = await adapter.get_positions()
        assert len(positions) == 1
        assert positions[0].lots == pytest.approx(0.5)

    async def test_close_nonexistent_position(self):
        """Closing a non-existent position returns error."""
        adapter = PaperAdapter()
        await adapter.connect()
        result = await adapter.close_position("FAKE-ID")
        assert result.success is False
        assert "not found" in result.error.lower()


# ===== Modify SL ===============================================================


class TestModifySL:
    """Stop-loss modification."""

    async def test_modify_sl(self):
        """Modify SL on an existing position."""
        adapter = PaperAdapter()
        await adapter.connect()
        adapter.set_price("EURUSD", bid=1.1000, ask=1.1002)
        order = await adapter.market_order("EURUSD", "bull", 0.10, sl=1.0950)
        pid = order.position_id

        success = await adapter.modify_sl(pid, new_sl=1.0970)
        assert success is True
        positions = await adapter.get_positions()
        assert positions[0].stop_loss == 1.0970

    async def test_modify_sl_nonexistent(self):
        """Modify SL on non-existent position returns False."""
        adapter = PaperAdapter()
        await adapter.connect()
        assert await adapter.modify_sl("FAKE", 1.0) is False


# ===== Queries =================================================================


class TestQueries:
    """Position and account queries."""

    async def test_get_positions_empty(self):
        """No positions returns empty list."""
        adapter = PaperAdapter()
        positions = await adapter.get_positions()
        assert positions == []

    async def test_get_positions_with_data(self):
        """Positions list populated after placing orders."""
        adapter = PaperAdapter()
        await adapter.connect()
        adapter.set_price("EURUSD", bid=1.1000, ask=1.1002)
        await adapter.market_order("EURUSD", "bull", 0.10)
        await adapter.market_order("EURUSD", "bear", 0.20)
        positions = await adapter.get_positions()
        assert len(positions) == 2

    async def test_get_account_initial_balance(self):
        """Account balance matches initial value."""
        adapter = PaperAdapter(initial_balance=25_000.0)
        account = await adapter.get_account()
        assert account.balance == 25_000.0
        assert account.equity == 25_000.0
        assert account.currency == "USD"


# ===== P&L calculation =========================================================


class TestPnL:
    """Unrealised P&L tracking."""

    async def test_pnl_calculation_profit(self):
        """Bull position with price increase shows positive P&L."""
        adapter = PaperAdapter(initial_balance=10_000.0)
        await adapter.connect()
        adapter.set_price("EURUSD", bid=1.1000, ask=1.1002)
        order = await adapter.market_order("EURUSD", "bull", 0.10)

        # Price moves up — bid increases
        adapter.set_price("EURUSD", bid=1.1050, ask=1.1052)

        positions = await adapter.get_positions()
        pos = positions[0]
        # PnL = (bid - entry) * lots * 100_000
        # entry was at ask=1.1002, now bid=1.1050
        expected_pnl = (1.1050 - 1.1002) * 0.10 * 100_000
        assert pos.pnl == pytest.approx(expected_pnl, rel=0.01)
        assert pos.pnl > 0

    async def test_pnl_calculation_loss(self):
        """Bull position with price decrease shows negative P&L."""
        adapter = PaperAdapter(initial_balance=10_000.0)
        await adapter.connect()
        adapter.set_price("EURUSD", bid=1.1000, ask=1.1002)
        order = await adapter.market_order("EURUSD", "bull", 0.10)

        # Price drops — bid decreases
        adapter.set_price("EURUSD", bid=1.0950, ask=1.0952)

        positions = await adapter.get_positions()
        pos = positions[0]
        # entry was at ask=1.1002, now bid=1.0950
        expected_pnl = (1.0950 - 1.1002) * 0.10 * 100_000
        assert pos.pnl == pytest.approx(expected_pnl, rel=0.01)
        assert pos.pnl < 0

    async def test_set_price_updates_positions(self):
        """set_price updates current_price on matching positions."""
        adapter = PaperAdapter()
        await adapter.connect()
        adapter.set_price("EURUSD", bid=1.1000, ask=1.1002)
        await adapter.market_order("EURUSD", "bull", 0.10)

        adapter.set_price("EURUSD", bid=1.1020, ask=1.1022)
        positions = await adapter.get_positions()
        assert positions[0].current_price == 1.1020  # bull uses bid
