"""Alor OpenAPI broker connector.

Uses REST API (https://api.alor.ru) and WebSocket (wss://api.alor.ru/ws)
for real-time data. Implements OAuth2 token refresh.
"""
from __future__ import annotations

import asyncio
import json
import time
from datetime import datetime, timezone
from typing import Any, AsyncIterator

import aiohttp

from ..utils.logger import get_logger
from .base import (
    BaseBroker, BrokerCandle, BrokerOrder, BrokerPortfolio,
    BrokerPosition, BrokerQuote, OrderSide, OrderStatus, OrderType,
)

logger = get_logger("brokers.alor")

_BASE_URL = "https://api.alor.ru"
_AUTH_URL = "https://oauth.alor.ru/refresh"
_WS_URL = "wss://api.alor.ru/ws"


class AlorBroker(BaseBroker):
    """Broker connector for Alor OpenAPI.

    Parameters
    ----------
    refresh_token : str
        Long-lived refresh token from Alor.
    portfolio : str
        Portfolio/account identifier (e.g. "D39004").
    exchange : str
        Exchange code, default "MOEX".
    """

    def __init__(self, refresh_token: str, portfolio: str = "",
                 exchange: str = "MOEX") -> None:
        self._refresh_token = refresh_token
        self._portfolio = portfolio
        self._exchange = exchange
        self._access_token: str = ""
        self._token_expires: float = 0.0
        self._session: aiohttp.ClientSession | None = None

    @property
    def name(self) -> str:
        return "Alor OpenAPI"

    @property
    def supports_streaming(self) -> bool:
        return True

    async def _ensure_token(self) -> str:
        if self._access_token and time.time() < self._token_expires - 60:
            return self._access_token

        async with aiohttp.ClientSession() as session:
            async with session.post(
                _AUTH_URL, params={"token": self._refresh_token}
            ) as resp:
                data = await resp.json()
                if resp.status != 200:
                    raise ConnectionError(f"Alor auth failed: {data}")
                self._access_token = data["AccessToken"]
                self._token_expires = time.time() + data.get("expires_in", 1800)
                return self._access_token

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._access_token}"}

    async def connect(self) -> bool:
        try:
            await self._ensure_token()
            self._session = aiohttp.ClientSession(
                base_url=_BASE_URL, headers=self._headers())

            if not self._portfolio:
                async with self._session.get("/client/v1.0/portfolios") as resp:
                    data = await resp.json()
                    if data:
                        self._portfolio = data[0].get("portfolio", "")

            logger.info("connected to Alor, portfolio={}", self._portfolio)
            return True
        except Exception as exc:
            logger.error("Alor connection failed: {}", exc)
            return False

    async def disconnect(self) -> None:
        if self._session:
            await self._session.close()
            self._session = None

    async def is_connected(self) -> bool:
        return self._session is not None and not self._session.closed

    async def _get(self, path: str, **params: Any) -> Any:
        await self._ensure_token()
        assert self._session
        self._session._default_headers = self._headers()  # type: ignore[assignment]
        async with self._session.get(path, params=params) as resp:
            if resp.status != 200:
                text = await resp.text()
                raise RuntimeError(f"Alor GET {path} failed ({resp.status}): {text}")
            return await resp.json()

    async def _post(self, path: str, body: dict[str, Any]) -> Any:
        await self._ensure_token()
        assert self._session
        self._session._default_headers = self._headers()  # type: ignore[assignment]
        async with self._session.post(path, json=body) as resp:
            if resp.status not in (200, 201):
                text = await resp.text()
                raise RuntimeError(f"Alor POST {path} failed ({resp.status}): {text}")
            return await resp.json()

    async def _delete(self, path: str) -> bool:
        await self._ensure_token()
        assert self._session
        self._session._default_headers = self._headers()  # type: ignore[assignment]
        async with self._session.delete(path) as resp:
            return resp.status in (200, 204)

    async def place_order(self, ticker: str, side: OrderSide, qty: int,
                          order_type: OrderType = OrderType.MARKET,
                          price: float | None = None) -> BrokerOrder:
        body: dict[str, Any] = {
            "symbol": ticker,
            "exchange": self._exchange,
            "portfolio": self._portfolio,
            "side": "buy" if side == OrderSide.BUY else "sell",
            "quantity": qty,
            "type": "market" if order_type == OrderType.MARKET else "limit",
        }
        if price is not None and order_type == OrderType.LIMIT:
            body["price"] = price

        path = f"/commandapi/warptrans/TRADE/v2/client/orders/actions/{body['type']}"
        data = await self._post(path, body)

        return BrokerOrder(
            order_id=str(data.get("orderNumber", "")),
            ticker=ticker,
            side=side,
            order_type=order_type,
            qty=qty,
            price=price,
            status=OrderStatus.SENT,
            timestamp=datetime.now(timezone.utc),
            broker_message=data.get("message", ""),
        )

    async def cancel_order(self, order_id: str) -> bool:
        path = (f"/commandapi/warptrans/TRADE/v2/client/orders/"
                f"{order_id}?portfolio={self._portfolio}&exchange={self._exchange}")
        return await self._delete(path)

    async def get_order_status(self, order_id: str) -> BrokerOrder:
        orders = await self.get_orders(active_only=False)
        for o in orders:
            if o.order_id == order_id:
                return o
        raise ValueError(f"order {order_id} not found")

    async def get_orders(self, active_only: bool = True) -> list[BrokerOrder]:
        path = f"/md/v2/clients/{self._exchange}/{self._portfolio}/orders"
        data = await self._get(path)

        orders = []
        for o in data if isinstance(data, list) else []:
            status_map = {
                "working": OrderStatus.SENT,
                "filled": OrderStatus.FILLED,
                "cancelled": OrderStatus.CANCELLED,
                "rejected": OrderStatus.REJECTED,
            }
            status = status_map.get(o.get("status", ""), OrderStatus.PENDING)
            if active_only and status in (OrderStatus.FILLED, OrderStatus.CANCELLED, OrderStatus.REJECTED):
                continue

            orders.append(BrokerOrder(
                order_id=str(o.get("id", "")),
                ticker=o.get("symbol", ""),
                side=OrderSide.BUY if o.get("side") == "buy" else OrderSide.SELL,
                order_type=OrderType.LIMIT if o.get("type") == "limit" else OrderType.MARKET,
                qty=o.get("qty", 0),
                price=o.get("price"),
                filled_qty=o.get("filledQty", 0),
                status=status,
                timestamp=datetime.now(timezone.utc),
            ))
        return orders

    async def get_portfolio(self) -> BrokerPortfolio:
        path = f"/md/v2/clients/{self._exchange}/{self._portfolio}/summary"
        data = await self._get(path)

        positions = await self.get_positions()
        return BrokerPortfolio(
            total_value=float(data.get("portfolioEvaluation", 0)),
            cash=float(data.get("buyingPower", 0)),
            positions=positions,
        )

    async def get_positions(self) -> list[BrokerPosition]:
        path = f"/md/v2/clients/{self._exchange}/{self._portfolio}/positions"
        data = await self._get(path)

        positions = []
        for p in data if isinstance(data, list) else []:
            qty = int(p.get("qty", 0))
            if qty == 0:
                continue
            positions.append(BrokerPosition(
                ticker=p.get("symbol", ""),
                qty=qty,
                avg_price=float(p.get("avgPrice", 0)),
                current_price=float(p.get("currentPrice", 0)),
                unrealized_pnl=float(p.get("unrealizedPl", 0)),
            ))
        return positions

    async def get_quote(self, ticker: str) -> BrokerQuote:
        path = f"/md/v2/Securities/{self._exchange}/{ticker}/quotes"
        data = await self._get(path)
        return BrokerQuote(
            ticker=ticker,
            bid=float(data.get("bid", 0)),
            ask=float(data.get("ask", 0)),
            last=float(data.get("last_price", 0)),
            volume=int(data.get("volume", 0)),
            timestamp=datetime.now(timezone.utc),
        )

    async def get_candles(self, ticker: str, interval: str = "1d",
                          count: int = 100) -> list[BrokerCandle]:
        tf_map = {"1m": 60, "5m": 300, "15m": 900, "1h": 3600, "1d": "D", "1w": "W"}
        tf = tf_map.get(interval, "D")
        path = f"/md/v2/history/{self._exchange}/{ticker}/{tf}"

        now = int(time.time())
        seconds_per = {"1m": 60, "5m": 300, "15m": 900, "1h": 3600, "1d": 86400, "1w": 604800}
        from_ts = now - seconds_per.get(interval, 86400) * count

        data = await self._get(path, **{"from": from_ts, "to": now})

        candles = []
        for c in data.get("history", []) if isinstance(data, dict) else []:
            candles.append(BrokerCandle(
                datetime=datetime.fromtimestamp(c["time"], tz=timezone.utc),
                open=c["open"],
                high=c["high"],
                low=c["low"],
                close=c["close"],
                volume=int(c.get("volume", 0)),
            ))
        return candles[-count:]

    async def subscribe_quotes(self, tickers: list[str]) -> AsyncIterator[BrokerQuote]:
        import websockets

        token = await self._ensure_token()
        async with websockets.connect(_WS_URL) as ws:
            for ticker in tickers:
                sub_msg = {
                    "opcode": "QuotesSubscribe",
                    "code": ticker,
                    "exchange": self._exchange,
                    "token": token,
                }
                await ws.send(json.dumps(sub_msg))

            async for msg in ws:
                data = json.loads(msg)
                if data.get("data"):
                    d = data["data"]
                    yield BrokerQuote(
                        ticker=d.get("symbol", ""),
                        bid=float(d.get("bid", 0)),
                        ask=float(d.get("ask", 0)),
                        last=float(d.get("last_price", 0)),
                        volume=int(d.get("volume", 0)),
                        timestamp=datetime.now(timezone.utc),
                    )

    async def get_accounts(self) -> list[dict[str, Any]]:
        data = await self._get("/client/v1.0/portfolios")
        return [{"id": p.get("portfolio", ""), "name": p.get("portfolio", ""),
                 "type": p.get("marketType", "")} for p in (data or [])]
