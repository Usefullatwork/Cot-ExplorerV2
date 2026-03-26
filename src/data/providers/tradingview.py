"""TradingView data provider — real-time price access via TradingView WebSocket.

Uses the TradingView-API package (pip install TradingView-API).
Gracefully degrades if the package is not installed.
"""

from __future__ import annotations

import asyncio
import logging
import threading
import time
from typing import Any

from src.core.models import OhlcBar
from src.data.providers.base import BaseProvider
from src.data.rate_limiter import RateLimiter

logger = logging.getLogger(__name__)

# TradingView symbol mapping: Yahoo-style keys -> TradingView symbols
TV_SYMBOLS: dict[str, str] = {
    "EURUSD=X": "FX:EURUSD",
    "JPY=X": "FX:USDJPY",
    "GBPUSD=X": "FX:GBPUSD",
    "AUDUSD=X": "FX:AUDUSD",
    "GC=F": "TVC:GOLD",
    "SI=F": "TVC:SILVER",
    "BZ=F": "NYMEX:BZ1!",
    "CL=F": "NYMEX:CL1!",
    "^GSPC": "SP:SPX",
    "^NDX": "NASDAQ:NDX",
    "DX-Y.NYB": "TVC:DXY",
    "^VIX": "TVC:VIX",
    "HG=F": "COMEX:HG1!",
    "HYG": "AMEX:HYG",
    "TIP": "AMEX:TIP",
    "EEM": "AMEX:EEM",
}

# TradingView timeframe mapping: our intervals -> TV timeframes
TV_TIMEFRAMES: dict[str, str] = {
    "1d": "D",
    "1D": "D",
    "15m": "15",
    "60m": "60",
    "4h": "240",
    "1h": "60",
    "5m": "5",
    "1m": "1",
}

# Range sizes: how many bars to request for each range key
TV_RANGE_SIZES: dict[str, int] = {
    "1y": 365,
    "5d": 50,
    "30d": 35,
    "60d": 65,
}


class TradingViewProvider(BaseProvider):
    """Real-time price data from TradingView WebSocket.

    Uses the TradingView-API package (``pip install TradingView-API``).
    Falls back gracefully when the package is not installed — all fetch
    methods return empty lists without raising.

    Provides:
    - Historical OHLCV candles (daily and intraday)
    - Real-time last price via the latest bar
    """

    def __init__(self) -> None:
        super().__init__(name="tradingview")
        self._available = False
        self._rate_limiter = RateLimiter(max_tokens=1, refill_rate=0.5)  # 1 req / 2s
        try:
            from TradingView import ChartSession, Client  # noqa: F401

            self._available = True
            logger.info("TradingView-API package found — provider enabled")
        except ImportError:
            logger.info("TradingView-API package not installed — provider disabled")

    def is_available(self) -> bool:
        """Return True if the TradingView-API package is importable."""
        return self._available

    def _resolve_symbol(self, symbol: str) -> str | None:
        """Map a Yahoo-style symbol to a TradingView symbol."""
        tv_sym = TV_SYMBOLS.get(symbol)
        if not tv_sym:
            logger.debug("TradingView: no mapping for symbol %s", symbol)
        return tv_sym

    def _fetch_bars(
        self,
        symbol: str,
        timeframe: str,
        bar_count: int,
    ) -> list[OhlcBar]:
        """Connect to TradingView WebSocket and fetch OHLCV bars synchronously.

        Runs the async TradingView client in a dedicated event loop on a
        background thread so the caller is never blocked on import-time
        async machinery.
        """
        from TradingView import ChartSession, Client

        tv_sym = self._resolve_symbol(symbol)
        if not tv_sym:
            return []

        # Rate-limit: max 1 request per 2 seconds
        self._rate_limiter.acquire(timeout=30.0)

        result: list[dict[str, Any]] = []
        error_holder: list[str] = []
        data_ready = threading.Event()

        async def _run() -> None:
            client = Client()

            def on_connect() -> None:
                logger.debug("TradingView: WebSocket connected")

            def on_error(err: Any) -> None:
                logger.warning("TradingView: client error: %s", err)
                error_holder.append(str(err))
                data_ready.set()

            def on_close() -> None:
                logger.debug("TradingView: WebSocket closed")

            client.on_connected(on_connect)
            client.on_error(on_error)
            client.on_disconnected(on_close)

            try:
                await client.connect()
                await asyncio.sleep(0.5)

                session = ChartSession(client)

                def on_update(data: dict[str, Any]) -> None:
                    periods = data.get("periods", [])
                    if periods:
                        result.extend(periods)
                        data_ready.set()

                def on_session_error(err: Any) -> None:
                    logger.warning("TradingView: session error: %s", err)
                    error_holder.append(str(err))
                    data_ready.set()

                session.on_update(on_update)
                session.on_error(on_session_error)
                session.subscribe(tv_sym, timeframe=timeframe, range_count=bar_count)

                # Wait for data with timeout
                deadline = time.monotonic() + 15.0
                while not data_ready.is_set() and time.monotonic() < deadline:
                    await asyncio.sleep(0.2)

                session.unsubscribe()
                client.disconnect()
            except Exception as exc:
                logger.error("TradingView: connection failed: %s", exc)
                error_holder.append(str(exc))
                data_ready.set()

        # Run the async code in a new event loop on a background thread
        loop = asyncio.new_event_loop()

        def _thread_target() -> None:
            asyncio.set_event_loop(loop)
            loop.run_until_complete(_run())

        thread = threading.Thread(target=_thread_target, daemon=True)
        thread.start()
        thread.join(timeout=20.0)

        try:
            loop.close()
        except Exception:
            pass

        if error_holder and not result:
            logger.warning("TradingView %s: errors=%s", symbol, error_holder)
            return []

        # Convert TradingView periods to OhlcBar
        # TV period format: {'time': int, 'open': float, 'close': float,
        #                     'max': float, 'min': float, 'volume': float}
        bars: list[OhlcBar] = []
        # Sort oldest-first (TV returns newest-first via periods_list)
        sorted_periods = sorted(result, key=lambda p: p.get("time", 0))
        for p in sorted_periods:
            try:
                hi = float(p.get("max", 0))
                lo = float(p.get("min", 0))
                cl = float(p.get("close", 0))
                if hi and lo and cl:
                    bars.append(OhlcBar(high=hi, low=lo, close=cl))
            except (ValueError, TypeError):
                continue

        logger.info("TradingView %s: fetched %d bars (tf=%s)", symbol, len(bars), timeframe)
        return bars

    def _fetch_daily(self, symbol: str, range_: str = "1y") -> list[OhlcBar]:
        """Raw fetch for daily bars."""
        bar_count = TV_RANGE_SIZES.get(range_, 365)
        return self._fetch_bars(symbol, timeframe="D", bar_count=bar_count)

    def fetch_daily(self, symbol: str, range_: str = "1y") -> list[OhlcBar]:
        """Fetch daily OHLCV bars with retry and circuit breaker.

        Parameters
        ----------
        symbol : str
            Yahoo-style symbol that maps to a TradingView ticker.
        range_ : str
            Date range key: ``"1y"``, ``"30d"``, ``"5d"``.

        Returns
        -------
        list[OhlcBar]
            Bars ordered oldest to newest.  Empty list on failure.
        """
        if not self._available:
            return []
        try:
            return self.fetch_with_retry(self._fetch_daily, symbol, range_)
        except Exception as exc:
            logger.error("TradingView daily %s: %s", symbol, exc)
            return []

    def _fetch_intraday(self, symbol: str, interval: str = "15m") -> list[OhlcBar]:
        """Raw fetch for intraday bars."""
        tf = TV_TIMEFRAMES.get(interval, "15")
        return self._fetch_bars(symbol, timeframe=tf, bar_count=200)

    def fetch_intraday(self, symbol: str, interval: str = "15m") -> list[OhlcBar]:
        """Fetch intraday OHLCV bars with retry and circuit breaker.

        Parameters
        ----------
        symbol : str
            Yahoo-style symbol.
        interval : str
            Candle interval: ``"1m"``, ``"5m"``, ``"15m"``, ``"60m"``, ``"4h"``.

        Returns
        -------
        list[OhlcBar]
            Bars ordered oldest to newest.  Empty list on failure.
        """
        if not self._available:
            return []
        try:
            return self.fetch_with_retry(self._fetch_intraday, symbol, interval)
        except Exception as exc:
            logger.error("TradingView intraday %s (%s): %s", symbol, interval, exc)
            return []


# Module-level convenience instances and functions
_provider = TradingViewProvider()


def fetch_tradingview(symbol: str, interval: str = "1d", range_: str = "1y") -> list[OhlcBar]:
    """Fetch OHLC from TradingView — convenience function.

    Parameters
    ----------
    symbol : str
        Yahoo-style symbol.
    interval : str
        ``"1d"`` for daily, ``"15m"``/``"60m"`` for intraday.
    range_ : str
        Date range key (only used for daily): ``"1y"``, ``"5d"``, ``"30d"``.

    Returns
    -------
    list[OhlcBar]
        Bars ordered oldest to newest.
    """
    if interval == "1d":
        return _provider.fetch_daily(symbol, range_)
    return _provider.fetch_intraday(symbol, interval)
