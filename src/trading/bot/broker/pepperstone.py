"""Pepperstone cTrader REST API broker adapter.

Uses httpx for async HTTP.  Endpoint paths are TODO placeholders until
cTrader API access is provisioned.
"""

from __future__ import annotations

import logging
from typing import Any

try:
    import httpx
except ImportError:  # pragma: no cover
    httpx = None  # type: ignore[assignment]

from src.trading.bot.broker.base import (
    AccountInfo,
    BrokerAdapter,
    BrokerPosition,
    OrderResult,
    Price,
)

logger = logging.getLogger(__name__)
_DEMO = "https://demo.ctraderapi.com/v2"
_LIVE = "https://live.ctraderapi.com/v2"
_ENDPOINTS_VERIFIED = False


class PepperstoneAdapter(BrokerAdapter):
    """Pepperstone cTrader REST API adapter."""

    def __init__(self, api_key: str, account_id: str, demo: bool = True) -> None:
        if httpx is None:
            raise ImportError("httpx required — pip install httpx")
        self._api_key = api_key
        self._account_id = account_id
        self._base_url = _DEMO if demo else _LIVE
        self._client: httpx.AsyncClient | None = None
        self._connected: bool = False
        if not demo:
            logger.warning("Pepperstone adapter not production-ready — cTrader endpoints unverified")

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._api_key}", "Content-Type": "application/json"}

    async def _request(self, method: str, path: str, *, json: dict[str, Any] | None = None) -> dict[str, Any]:
        """Send an authenticated request.  Raises RuntimeError on failure."""
        if self._client is None or not self._connected:
            raise RuntimeError("PepperstoneAdapter is not connected")
        url = f"{self._base_url}{path}"
        try:
            resp = await self._client.request(method, url, headers=self._headers(), json=json, timeout=10.0)
            resp.raise_for_status()
            return resp.json()  # type: ignore[no-any-return]
        except httpx.HTTPStatusError as exc:
            logger.error("HTTP %s %s -> %s", method, url, exc.response.status_code)
            raise RuntimeError(f"Broker API error: {exc.response.status_code}") from exc
        except httpx.RequestError as exc:
            logger.error("Request failed: %s", exc)
            raise RuntimeError(f"Broker request failed: {exc}") from exc

    # -- connection -----------------------------------------------------------

    async def connect(self) -> bool:
        """Open an httpx session and verify connectivity."""
        if not _ENDPOINTS_VERIFIED:
            raise NotImplementedError(
                "Pepperstone cTrader endpoints not yet verified. Use PaperAdapter for testing."
            )
        self._client = httpx.AsyncClient()
        self._connected = True  # allow _request to work
        try:
            # TODO: replace with real cTrader auth/ping endpoint
            await self._request("GET", f"/accounts/{self._account_id}")
        except RuntimeError:
            self._connected = False
        return self._connected

    async def disconnect(self) -> None:
        """Close the httpx session."""
        if self._client:
            await self._client.aclose()
            self._client = None
        self._connected = False

    async def is_connected(self) -> bool:
        return self._connected

    # -- account --------------------------------------------------------------

    async def get_account(self) -> AccountInfo:
        """Fetch account balance, equity, and margin from cTrader."""
        # TODO: real cTrader account endpoint
        data = await self._request("GET", f"/accounts/{self._account_id}")
        return AccountInfo(
            balance=float(data.get("balance", 0)),
            equity=float(data.get("equity", 0)),
            margin_used=float(data.get("marginUsed", 0)),
            currency=str(data.get("currency", "USD")),
        )

    # -- orders ---------------------------------------------------------------

    async def market_order(
        self, symbol: str, direction: str, lots: float,
        sl: float | None = None, tp: float | None = None,
    ) -> OrderResult:
        """Place a market order via cTrader REST API."""
        if not _ENDPOINTS_VERIFIED:
            raise NotImplementedError(
                "Pepperstone cTrader endpoints not yet verified. Use PaperAdapter for testing."
            )
        payload: dict[str, Any] = {
            "accountId": self._account_id, "symbolName": symbol,
            "tradeSide": "BUY" if direction == "bull" else "SELL",
            "volume": int(lots * 100_000),
        }
        if sl is not None:
            payload["stopLoss"] = sl
        if tp is not None:
            payload["takeProfit"] = tp
        try:
            # TODO: real cTrader order endpoint
            data = await self._request("POST", "/orders/market", json=payload)
            return OrderResult(True, str(data.get("positionId", "")), float(data.get("fillPrice", 0)), None)
        except RuntimeError as exc:
            return OrderResult(False, None, None, str(exc))

    async def close_position(self, position_id: str, pct: float = 1.0) -> OrderResult:
        """Close (fully or partially) a position via cTrader."""
        payload: dict[str, Any] = {"accountId": self._account_id, "positionId": position_id}
        if pct < 1.0:
            payload["volumePercent"] = pct
        try:
            # TODO: real cTrader close endpoint
            data = await self._request("POST", "/positions/close", json=payload)
            return OrderResult(True, position_id, float(data.get("fillPrice", 0)), None)
        except RuntimeError as exc:
            return OrderResult(False, position_id, None, str(exc))

    async def modify_sl(self, position_id: str, new_sl: float) -> bool:
        """Update stop-loss on an open position."""
        try:
            # TODO: real cTrader modify endpoint
            await self._request("PUT", f"/positions/{position_id}",
                                json={"stopLoss": new_sl, "accountId": self._account_id})
            return True
        except RuntimeError:
            return False

    # -- queries --------------------------------------------------------------

    async def get_positions(self) -> list[BrokerPosition]:
        """Fetch all open positions from cTrader."""
        # TODO: real cTrader positions endpoint
        data = await self._request("GET", f"/accounts/{self._account_id}/positions")
        return [
            BrokerPosition(
                position_id=str(p["positionId"]), instrument=str(p["symbolName"]),
                direction="bull" if p["tradeSide"] == "BUY" else "bear",
                lots=float(p.get("volume", 0)) / 100_000,
                entry_price=float(p.get("entryPrice", 0)),
                current_price=float(p.get("currentPrice", 0)),
                stop_loss=p.get("stopLoss"), take_profit=p.get("takeProfit"),
                pnl=float(p.get("unrealizedPnl", 0)),
                opened_at=str(p.get("openTimestamp", "")),
            )
            for p in data.get("positions", [])
        ]

    async def get_price(self, symbol: str) -> Price:
        """Fetch the latest bid/ask for *symbol* from cTrader."""
        # TODO: real cTrader quote endpoint
        data = await self._request("GET", f"/symbols/{symbol}/quote")
        return Price(bid=float(data.get("bid", 0)), ask=float(data.get("ask", 0)),
                     timestamp=str(data.get("timestamp", "")))
