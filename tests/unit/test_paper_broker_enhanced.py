"""Unit tests for enhanced PaperAdapter -- slippage, partial fills, requotes."""

from __future__ import annotations

import pytest

from src.trading.bot.broker.paper import PaperAdapter


# ===== Default behaviour (no enhancements) ====================================


class TestDefaultBehaviour:
    """With all enhancements OFF the broker behaves exactly as before."""

    async def test_execution_log_exists(self):
        """Adapter always has an execution_log attribute."""
        adapter = PaperAdapter()
        assert hasattr(adapter, "execution_log")
        assert adapter.execution_log == []

    async def test_default_fill_unchanged(self):
        """Default fill price equals the raw ask/bid with no adjustments."""
        adapter = PaperAdapter()
        await adapter.connect()
        adapter.set_price("EURUSD", bid=1.0990, ask=1.1000)
        result = await adapter.market_order("EURUSD", "bull", 0.10)
        assert result.fill_price == 1.1000
        assert len(adapter.execution_log) == 1
        entry = adapter.execution_log[0]
        assert entry["slippage_pips"] == 0.0
        assert entry["requoted"] is False
        assert entry["partial"] is False
        assert entry["fill_pct"] == 1.0

    async def test_default_bear_fill(self):
        """Bear fill price equals bid with no slippage."""
        adapter = PaperAdapter()
        await adapter.connect()
        adapter.set_price("GBPUSD", bid=1.2600, ask=1.2602)
        result = await adapter.market_order("GBPUSD", "bear", 0.50)
        assert result.fill_price == 1.2600


# ===== Slippage =================================================================


class TestSlippage:
    """enable_slippage=True adds lognormal slippage to fills."""

    async def test_slippage_adjusts_fill(self):
        """Fill price should differ from the raw ask/bid."""
        adapter = PaperAdapter(enable_slippage=True, slippage_seed=123)
        await adapter.connect()
        adapter.set_price("EURUSD", bid=1.0990, ask=1.1000)
        result = await adapter.market_order("EURUSD", "bull", 0.10)

        # Bull fill should be >= ask (slippage makes it worse)
        assert result.fill_price > 1.1000
        entry = adapter.execution_log[0]
        assert entry["slippage_pips"] > 0

    async def test_slippage_bear_fills_lower(self):
        """Bear fill with slippage should be below bid."""
        adapter = PaperAdapter(enable_slippage=True, slippage_seed=99)
        await adapter.connect()
        adapter.set_price("EURUSD", bid=1.0990, ask=1.1000)
        result = await adapter.market_order("EURUSD", "bear", 0.10)
        assert result.fill_price < 1.0990

    async def test_slippage_deterministic(self):
        """Same seed produces identical slippage."""
        fills = []
        for _ in range(2):
            adapter = PaperAdapter(enable_slippage=True, slippage_seed=42)
            await adapter.connect()
            adapter.set_price("EURUSD", bid=1.0990, ask=1.1000)
            result = await adapter.market_order("EURUSD", "bull", 0.10)
            fills.append(result.fill_price)
        assert fills[0] == pytest.approx(fills[1])


# ===== Partial fills ============================================================


class TestPartialFills:
    """enable_partial_fills=True partially fills large orders."""

    async def test_large_order_partial(self):
        """Orders > 5 lots get partial fills."""
        adapter = PaperAdapter(enable_partial_fills=True, slippage_seed=42)
        await adapter.connect()
        adapter.set_price("EURUSD", bid=1.0990, ask=1.1000)
        result = await adapter.market_order("EURUSD", "bull", 10.0)

        assert result.success is True
        entry = adapter.execution_log[0]
        assert entry["partial"] is True
        assert 0.7 <= entry["fill_pct"] <= 1.0

        # Position lots should match partial fill
        positions = await adapter.get_positions()
        expected_lots = 10.0 * entry["fill_pct"]
        assert positions[0].lots == pytest.approx(expected_lots, rel=0.01)

    async def test_small_order_full_fill(self):
        """Orders <= 5 lots are fully filled."""
        adapter = PaperAdapter(enable_partial_fills=True, slippage_seed=42)
        await adapter.connect()
        adapter.set_price("EURUSD", bid=1.0990, ask=1.1000)
        await adapter.market_order("EURUSD", "bull", 2.0)

        entry = adapter.execution_log[0]
        assert entry["partial"] is False
        assert entry["fill_pct"] == 1.0

    async def test_exactly_5_lots_full_fill(self):
        """Boundary: exactly 5.0 lots should still get a full fill."""
        adapter = PaperAdapter(enable_partial_fills=True, slippage_seed=42)
        await adapter.connect()
        adapter.set_price("EURUSD", bid=1.0990, ask=1.1000)
        await adapter.market_order("EURUSD", "bull", 5.0)

        entry = adapter.execution_log[0]
        assert entry["partial"] is False
        assert entry["fill_pct"] == 1.0


# ===== Requotes =================================================================


class TestRequotes:
    """enable_requotes=True adds probabilistic requotes."""

    async def test_requotes_over_many_fills(self):
        """Over many fills some should be requoted (seeded)."""
        adapter = PaperAdapter(enable_requotes=True, slippage_seed=7)
        await adapter.connect()
        adapter.set_price("EURUSD", bid=1.0990, ask=1.1000)

        for _ in range(200):
            await adapter.market_order("EURUSD", "bull", 0.10)

        requoted_count = sum(
            1 for e in adapter.execution_log if e["requoted"]
        )
        # ~2% requote rate = ~4 out of 200.  Allow wide margin.
        assert requoted_count > 0
        assert requoted_count < 50  # sanity upper bound

    async def test_high_vix_increases_requotes(self):
        """VIX > 30 should increase requote probability to ~10%."""
        adapter = PaperAdapter(enable_requotes=True, slippage_seed=7)
        await adapter.connect()
        adapter.set_vix(40.0)
        adapter.set_price("EURUSD", bid=1.0990, ask=1.1000)

        for _ in range(200):
            await adapter.market_order("EURUSD", "bull", 0.10)

        requoted_count = sum(
            1 for e in adapter.execution_log if e["requoted"]
        )
        # ~10% rate = ~20 out of 200.
        assert requoted_count > 5

    async def test_requoted_fills_have_extra_slippage(self):
        """Requoted entries should show non-zero slippage."""
        adapter = PaperAdapter(
            enable_requotes=True, enable_slippage=False, slippage_seed=7,
        )
        await adapter.connect()
        adapter.set_price("EURUSD", bid=1.0990, ask=1.1000)

        for _ in range(200):
            await adapter.market_order("EURUSD", "bull", 0.10)

        for entry in adapter.execution_log:
            if entry["requoted"]:
                assert entry["slippage_pips"] > 0
                break
        else:
            pytest.skip("No requotes occurred in this seed — not a failure")


# ===== Execution log accumulation =============================================


class TestExecutionLog:
    """Execution log grows with each fill and contains all fields."""

    async def test_log_grows(self):
        """Each fill appends one entry."""
        adapter = PaperAdapter()
        await adapter.connect()
        adapter.set_price("EURUSD", bid=1.0990, ask=1.1000)

        await adapter.market_order("EURUSD", "bull", 0.10)
        await adapter.market_order("EURUSD", "bear", 0.20)
        assert len(adapter.execution_log) == 2

    async def test_log_entry_fields(self):
        """Every entry contains all required keys."""
        adapter = PaperAdapter(
            enable_slippage=True,
            enable_partial_fills=True,
            enable_requotes=True,
            slippage_seed=42,
        )
        await adapter.connect()
        adapter.set_price("EURUSD", bid=1.0990, ask=1.1000)
        await adapter.market_order("EURUSD", "bull", 0.10)

        required_keys = {
            "instrument", "direction", "requested_price", "fill_price",
            "slippage_pips", "filled", "partial", "fill_pct", "requoted",
            "timestamp",
        }
        entry = adapter.execution_log[0]
        assert required_keys.issubset(entry.keys())

    async def test_not_connected_no_log_entry(self):
        """Failed order (not connected) should not add to log."""
        adapter = PaperAdapter()
        await adapter.market_order("EURUSD", "bull", 0.10)
        assert len(adapter.execution_log) == 0
