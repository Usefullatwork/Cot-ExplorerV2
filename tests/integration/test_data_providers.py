"""Integration tests for data provider fallback chain.

Tests the multi-source routing logic: Twelvedata -> Stooq -> Yahoo,
circuit breaker behavior, and end-to-end fallback across providers.
All external I/O is mocked.
"""

from __future__ import annotations

import json
import time
from unittest.mock import MagicMock, patch

import pytest

from src.core.errors import ProviderError, ProviderUnavailableError
from src.core.models import OhlcBar
from src.data.providers.base import BaseProvider, CircuitBreaker


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _bar(h: float = 1.1, l: float = 1.0, c: float = 1.05) -> OhlcBar:
    return OhlcBar(high=h, low=l, close=c)


def _bars(n: int = 5, base_close: float = 100.0) -> list[OhlcBar]:
    return [
        OhlcBar(high=base_close + i * 2 + 1, low=base_close + i * 2 - 1, close=base_close + i * 2)
        for i in range(n)
    ]


# ===========================================================================
# Circuit breaker integration
# ===========================================================================


class TestCircuitBreakerLifecycle:
    """Full lifecycle: closed -> open -> half_open -> closed."""

    def test_starts_closed(self):
        cb = CircuitBreaker(threshold=3, cooldown_s=0.1)
        assert cb.state == "closed"
        assert cb.allow_request() is True

    def test_opens_after_threshold_failures(self):
        cb = CircuitBreaker(threshold=3, cooldown_s=300.0)
        for _ in range(3):
            cb.record_failure()
        assert cb.state == "open"
        assert cb.allow_request() is False

    def test_transitions_to_half_open_after_cooldown(self):
        cb = CircuitBreaker(threshold=2, cooldown_s=0.05)
        cb.record_failure()
        cb.record_failure()
        assert cb.state == "open"

        time.sleep(0.06)
        assert cb.state == "half_open"
        assert cb.allow_request() is True

    def test_success_in_half_open_resets_to_closed(self):
        cb = CircuitBreaker(threshold=2, cooldown_s=0.05)
        cb.record_failure()
        cb.record_failure()
        time.sleep(0.06)
        assert cb.state == "half_open"

        cb.record_success()
        assert cb.state == "closed"
        assert cb.allow_request() is True

    def test_failure_in_half_open_reopens(self):
        cb = CircuitBreaker(threshold=2, cooldown_s=0.05)
        cb.record_failure()
        cb.record_failure()
        time.sleep(0.06)
        assert cb.state == "half_open"

        cb.record_failure()
        assert cb.state == "open"
        assert cb.allow_request() is False


# ===========================================================================
# Provider retry integration
# ===========================================================================


class DummyProvider(BaseProvider):
    """Concrete provider for testing base class retry logic."""

    def __init__(self):
        super().__init__(name="dummy")

    def is_available(self) -> bool:
        return True


class TestProviderRetryIntegration:
    """BaseProvider.fetch_with_retry across success and failure scenarios."""

    def test_success_on_first_try(self):
        p = DummyProvider()
        result = p.fetch_with_retry(lambda: "ok", retries=2, delay=0.01)
        assert result == "ok"

    def test_success_after_one_failure(self):
        p = DummyProvider()
        call_count = 0

        def flaky():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ConnectionError("temporary")
            return "recovered"

        result = p.fetch_with_retry(flaky, retries=2, delay=0.01)
        assert result == "recovered"
        assert call_count == 2

    def test_all_retries_exhausted_raises(self):
        p = DummyProvider()

        with pytest.raises(ProviderError, match="all 3 attempts failed"):
            p.fetch_with_retry(
                lambda: (_ for _ in ()).throw(ConnectionError("down")),
                retries=2,
                delay=0.01,
            )

    def test_circuit_breaker_blocks_after_many_failures(self):
        """After enough failures the circuit opens and requests are blocked."""
        p = DummyProvider()
        p.circuit_breaker = CircuitBreaker(threshold=3, cooldown_s=300.0)

        # Fail 3 times to trip the breaker
        for _ in range(3):
            try:
                p.fetch_with_retry(
                    lambda: (_ for _ in ()).throw(ConnectionError("fail")),
                    retries=0,
                    delay=0.01,
                )
            except ProviderError:
                pass

        with pytest.raises(ProviderUnavailableError, match="circuit breaker is open"):
            p.fetch_with_retry(lambda: "should not run", retries=0, delay=0.01)


# ===========================================================================
# Full fallback chain (Twelvedata -> Stooq -> Yahoo)
# ===========================================================================


class TestFullFallbackChain:
    """End-to-end fallback through all three providers."""

    @pytest.fixture(autouse=True)
    def _clean_env(self, monkeypatch):
        monkeypatch.delenv("TWELVEDATA_API_KEY", raising=False)
        monkeypatch.delenv("FINNHUB_API_KEY", raising=False)

    @patch("src.data.price_router._fetch_twelvedata")
    @patch("src.data.price_router._stooq")
    @patch("src.data.price_router._yahoo")
    @patch("src.data.price_router._fetch_finnhub_quote", return_value=None)
    def test_all_three_providers_tried_in_order(self, mock_fh, mock_yahoo, mock_stooq, mock_td):
        """TD returns empty -> Stooq returns empty -> Yahoo is the final try."""
        from src.data import price_router

        yahoo_bars = _bars(3)
        mock_td.return_value = []
        mock_stooq.fetch_stooq.return_value = []
        mock_yahoo.fetch_yahoo.return_value = yahoo_bars

        with patch.object(price_router, "TWELVEDATA_API_KEY", "key"):
            result = price_router.fetch_prices("EURUSD=X", "1d", "1y")

        mock_td.assert_called_once()
        mock_stooq.fetch_stooq.assert_called_once()
        mock_yahoo.fetch_yahoo.assert_called_once()
        assert result == yahoo_bars

    @patch("src.data.price_router._fetch_twelvedata")
    @patch("src.data.price_router._stooq")
    @patch("src.data.price_router._yahoo")
    @patch("src.data.price_router._fetch_finnhub_quote", return_value=None)
    def test_first_provider_success_short_circuits(self, mock_fh, mock_yahoo, mock_stooq, mock_td):
        """When TD succeeds, Stooq and Yahoo are never called."""
        from src.data import price_router

        td_bars = _bars(10)
        mock_td.return_value = td_bars

        with patch.object(price_router, "TWELVEDATA_API_KEY", "key"):
            result = price_router.fetch_prices("EURUSD=X", "1d", "1y")

        mock_td.assert_called_once()
        mock_stooq.fetch_stooq.assert_not_called()
        mock_yahoo.fetch_yahoo.assert_not_called()
        assert result == td_bars

    @patch("src.data.price_router._fetch_twelvedata")
    @patch("src.data.price_router._stooq")
    @patch("src.data.price_router._yahoo")
    @patch("src.data.price_router._fetch_finnhub_quote")
    def test_finnhub_overlay_replaces_last_bar(self, mock_fh, mock_yahoo, mock_stooq, mock_td):
        """Finnhub quote overlay replaces the last bar from any daily provider."""
        from src.data import price_router

        stooq_bars = _bars(5)
        realtime_bar = _bar(h=999.0, l=990.0, c=995.0)
        mock_stooq.fetch_stooq.return_value = stooq_bars
        mock_fh.return_value = realtime_bar

        with patch.object(price_router, "TWELVEDATA_API_KEY", ""):
            result = price_router.fetch_prices("^GSPC", "1d", "1y")

        assert len(result) == 5
        assert result[-1] == realtime_bar
        assert result[0] == stooq_bars[0]

    @patch("src.data.price_router._fetch_twelvedata")
    @patch("src.data.price_router._stooq")
    @patch("src.data.price_router._yahoo")
    @patch("src.data.price_router._fetch_finnhub_quote", return_value=None)
    def test_all_empty_returns_empty_list(self, mock_fh, mock_yahoo, mock_stooq, mock_td):
        """When every provider returns empty, the result is an empty list."""
        from src.data import price_router

        mock_stooq.fetch_stooq.return_value = []
        mock_yahoo.fetch_yahoo.return_value = []

        with patch.object(price_router, "TWELVEDATA_API_KEY", ""):
            result = price_router.fetch_prices("UNKNOWN_SYM", "1d", "1y")

        assert result == []

    @patch("src.data.price_router._fetch_twelvedata")
    @patch("src.data.price_router._stooq")
    @patch("src.data.price_router._yahoo")
    @patch("src.data.price_router._fetch_finnhub_quote", return_value=None)
    def test_intraday_skips_stooq(self, mock_fh, mock_yahoo, mock_stooq, mock_td):
        """For intraday intervals, Stooq is not called (only supports daily)."""
        from src.data import price_router

        yahoo_bars = _bars(3)
        mock_yahoo.fetch_yahoo.return_value = yahoo_bars

        with patch.object(price_router, "TWELVEDATA_API_KEY", ""):
            result = price_router.fetch_prices("^GSPC", "15m", "5d")

        mock_stooq.fetch_stooq.assert_not_called()
        mock_yahoo.fetch_yahoo.assert_called_once()
        assert result == yahoo_bars

    @patch("src.data.price_router._fetch_twelvedata")
    @patch("src.data.price_router._stooq")
    @patch("src.data.price_router._yahoo")
    @patch("src.data.price_router._fetch_finnhub_quote")
    def test_intraday_no_finnhub_overlay(self, mock_fh, mock_yahoo, mock_stooq, mock_td):
        """Finnhub overlay is only applied to daily data, not intraday."""
        from src.data import price_router

        yahoo_bars = _bars(3)
        mock_yahoo.fetch_yahoo.return_value = yahoo_bars

        with patch.object(price_router, "TWELVEDATA_API_KEY", ""):
            price_router.fetch_prices("^GSPC", "60m", "5d")

        mock_fh.assert_not_called()
