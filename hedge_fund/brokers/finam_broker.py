"""Finam Trade API broker connector.

Uses the finam-trade-api package (gRPC) for orders and streaming.
Token-based authentication with MOEX ticker mapping.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any, AsyncIterator

from ..utils.logger import get_logger
from .base import (
    BaseBroker, BrokerCandle, BrokerOrder, BrokerPortfolio,
    BrokerPosition, BrokerQuote, OrderSide, OrderStatus, OrderType,
)

logger = get_logger("brokers.finam")


class FinamBroker(BaseBroker):
    """Broker connector for Finam Trade API (gRPC).

    Parameters
    ----------
    token : str
        API token from Finam.
    client_id : str
        Finam client account ID.
    """

    def __init__(self, token: str, client_id: str = "") -> None:
        self._token = token
        self._client_id = client_id
        self._api: Any = None
        self._connected = False

    @property
    def name(self) -> str:
        return "Finam Trade"

    @property
    def supports_streaming(self) -> bool:
        return True

    async def connect(self) -> bool:
        try:
            from finam_trade_api import FinamTradeApi
            self._api = FinamTradeApi(self._token)

            if not self._client_id:
                accounts = await asyncio.to_thread(self._api.accounts.get_accounts)
                if accounts and hasattr(accounts, "accounts") and accounts.accounts:
                    self._client_id = accounts.accounts[0].client_id
                else:
                    logger.error("no Finam accounts found")
                    return False

            self._connected = True
            logger.info("connected to Finam, client_id={}", self._client_id)
            return True
        except Exception as exc:
            logger.error("Finam connection failed: {}", exc)
            return False

    async def disconnect(self) -> None:
        self._api = None
        self._connected = False

    async def is_connected(self) -> bool:
        return self._connected and self._api is not None

    async def place_order(self, ticker: str, side: OrderSide, qty: int,
                          order_type: OrderType = OrderType.MARKET,
                          price: float | None = None) -> BrokerOrder:
        from finam_trade_api.order import (
            OrderValidBefore, OrderValidBeforeType,
            CreateOrderRequest, BuySell,
        )

        buy_sell = BuySell.Buy if side == OrderSide.BUY else BuySell.Sell

        request = CreateOrderRequest(
            client_id=self._client_id,
            security_board="TQBR",
            security_code=ticker,
            buy_sell=buy_sell,
            quantity=qty,
            price=price if order_type == OrderType.LIMIT else None,
            use_credit=False,
            valid_before=OrderValidBefore(type=OrderValidBeforeType.TillEndSession),
        )

        resp = await asyncio.to_thread(self._api.orders.create_order, request)

        return BrokerOrder(
            order_id=str(getattr(resp, "transaction_id", "")),
            ticker=ticker,
            side=side,
            order_type=order_type,
            qty=qty,
            price=price,
            status=OrderStatus.SENT,
            timestamp=datetime.now(timezone.utc),
        )

    async def cancel_order(self, order_id: str) -> bool:
        try:
            await asyncio.to_thread(
                self._api.orders.cancel_order,
                client_id=self._client_id,
                transaction_id=int(order_id),
            )
            return True
        except Exception as exc:
            logger.error("Finam cancel_order failed: {}", exc)
            return False

    async def get_order_status(self, order_id: str) -> BrokerOrder:
        orders = await self.get_orders(active_only=False)
        for o in orders:
            if o.order_id == order_id:
                return o
        raise ValueError(f"order {order_id} not found")

    async def get_orders(self, active_only: bool = True) -> list[BrokerOrder]:
        resp = await asyncio.to_thread(
            self._api.orders.get_orders, client_id=self._client_id)

        orders = []
        for o in getattr(resp, "orders", []):
            status_map = {
                "Active": OrderStatus.SENT,
                "Matched": OrderStatus.FILLED,
                "Cancelled": OrderStatus.CANCELLED,
                "Rejected": OrderStatus.REJECTED,
            }
            status = status_map.get(getattr(o, "status", ""), OrderStatus.PENDING)
            if active_only and status in (OrderStatus.FILLED, OrderStatus.CANCELLED, OrderStatus.REJECTED):
                continue

            side = OrderSide.BUY if getattr(o, "buy_sell", "") == "Buy" else OrderSide.SELL
            orders.append(BrokerOrder(
                order_id=str(getattr(o, "transaction_id", "")),
                ticker=getattr(o, "security_code", ""),
                side=side,
                order_type=OrderType.LIMIT,
                qty=getattr(o, "quantity", 0),
                price=getattr(o, "price", None),
                filled_qty=getattr(o, "matched_quantity", 0),
                status=status,
                timestamp=datetime.now(timezone.utc),
            ))
        return orders

    async def get_portfolio(self) -> BrokerPortfolio:
        resp = await asyncio.to_thread(
            self._api.portfolio.get_portfolio, client_id=self._client_id)

        positions = []
        for p in getattr(resp, "positions", []):
            qty = int(getattr(p, "balance", 0))
            if qty == 0:
                continue
            positions.append(BrokerPosition(
                ticker=getattr(p, "security_code", ""),
                qty=qty,
                avg_price=float(getattr(p, "avg_price", 0)),
                current_price=float(getattr(p, "current_price", 0)),
                unrealized_pnl=float(getattr(p, "unrealized_pnl", 0)),
            ))

        total = float(getattr(resp, "equity", 0))
        cash = float(getattr(resp, "money", 0))
        return BrokerPortfolio(total_value=total, cash=cash, positions=positions)

    async def get_positions(self) -> list[BrokerPosition]:
        portfolio = await self.get_portfolio()
        return portfolio.positions

    async def get_quote(self, ticker: str) -> BrokerQuote:
        resp = await asyncio.to_thread(
            self._api.market_data.get_quote,
            security_board="TQBR", security_code=ticker)

        return BrokerQuote(
            ticker=ticker,
            bid=float(getattr(resp, "bid", 0)),
            ask=float(getattr(resp, "ask", 0)),
            last=float(getattr(resp, "last_price", 0)),
            volume=int(getattr(resp, "volume", 0)),
            timestamp=datetime.now(timezone.utc),
        )

    async def get_candles(self, ticker: str, interval: str = "1d",
                          count: int = 100) -> list[BrokerCandle]:
        from datetime import timedelta

        tf_map = {"1m": "M1", "5m": "M5", "15m": "M15", "1h": "H1", "1d": "D1", "1w": "W1"}
        tf = tf_map.get(interval, "D1")

        now = datetime.now(timezone.utc)
        delta_map = {"1m": 1, "5m": 5, "15m": 15, "1h": 60, "1d": 1440, "1w": 10080}
        minutes = delta_map.get(interval, 1440)
        from_dt = now - timedelta(minutes=minutes * count)

        resp = await asyncio.to_thread(
            self._api.market_data.get_candles,
            security_board="TQBR",
            security_code=ticker,
            time_frame=tf,
            date_from=from_dt.isoformat(),
            date_to=now.isoformat(),
            count=count,
        )

        candles = []
        for c in getattr(resp, "candles", []):
            candles.append(BrokerCandle(
                datetime=datetime.fromisoformat(getattr(c, "timestamp", "")),
                open=float(getattr(c, "open", 0)),
                high=float(getattr(c, "high", 0)),
                low=float(getattr(c, "low", 0)),
                close=float(getattr(c, "close", 0)),
                volume=int(getattr(c, "volume", 0)),
            ))
        return candles[-count:]

    async def subscribe_quotes(self, tickers: list[str]) -> AsyncIterator[BrokerQuote]:
        while self._connected:
            for ticker in tickers:
                try:
                    quote = await self.get_quote(ticker)
                    yield quote
                except Exception as exc:
                    logger.warning("Finam quote poll error for {}: {}", ticker, exc)
            await asyncio.sleep(1.0)

    async def get_accounts(self) -> list[dict[str, Any]]:
        resp = await asyncio.to_thread(self._api.accounts.get_accounts)
        return [{"id": a.client_id, "name": getattr(a, "name", a.client_id),
                 "type": getattr(a, "type", "trading")}
                for a in getattr(resp, "accounts", [])]
