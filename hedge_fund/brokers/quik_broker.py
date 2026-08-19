"""QUIK broker wrapper — adapts existing QuikConnector/OrderManager to BaseBroker.

Delegates to hedge_fund.quik.connector and hedge_fund.quik.order_manager,
making QUIK interchangeable with API-based brokers.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any, AsyncIterator

from ..utils.logger import get_logger
from ..quik.connector import QuikConnector
from ..quik.order_manager import (
    OrderManager,
    OrderSide as QuikSide,
    OrderType as QuikType,
    OrderStatus as QuikStatus,
    Position as QuikPosition,
)
from .base import (
    BaseBroker, BrokerCandle, BrokerOrder, BrokerPortfolio,
    BrokerPosition, BrokerQuote, OrderSide, OrderStatus, OrderType,
)

logger = get_logger("brokers.quik")

_STATUS_MAP: dict[QuikStatus, OrderStatus] = {
    QuikStatus.PENDING: OrderStatus.PENDING,
    QuikStatus.SENT: OrderStatus.SENT,
    QuikStatus.ACTIVE: OrderStatus.SENT,
    QuikStatus.PARTIALLY_FILLED: OrderStatus.PARTIAL,
    QuikStatus.FILLED: OrderStatus.FILLED,
    QuikStatus.CANCELLED: OrderStatus.CANCELLED,
    QuikStatus.REJECTED: OrderStatus.REJECTED,
}


class QuikBroker(BaseBroker):
    """Broker adapter wrapping the existing QUIK LUA bridge connector.

    Parameters
    ----------
    host : str
        QUIK LUA bridge host.
    port : int
        QUIK LUA bridge port.
    account : str
        QUIK trading account.
    client_code : str
        QUIK client code.
    firmid : str
        Firm ID for position queries.
    class_code : str
        Default class code (e.g. "TQBR" for MOEX equities).
    paper_trading : bool
        If True, use paper trading simulation.
    """

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 34130,
        account: str = "",
        client_code: str = "",
        firmid: str = "",
        class_code: str = "TQBR",
        paper_trading: bool = False,
    ) -> None:
        self._host = host
        self._port = port
        self._account = account
        self._client_code = client_code
        self._firmid = firmid
        self._class_code = class_code
        self._paper = paper_trading
        self._connector: QuikConnector | None = None
        self._order_manager: OrderManager | None = None

    @property
    def name(self) -> str:
        return "QUIK (Sber/VTB)" + (" paper" if self._paper else "")

    @property
    def supports_streaming(self) -> bool:
        return True

    async def connect(self) -> bool:
        try:
            self._connector = QuikConnector(host=self._host, port=self._port)
            await self._connector.connect()
            self._order_manager = OrderManager(
                self._connector,
                paper_trading=self._paper,
                account=self._account,
                client_code=self._client_code,
                firmid=self._firmid,
            )
            logger.info("connected to QUIK at {}:{}", self._host, self._port)
            return True
        except Exception as exc:
            logger.error("QUIK connection failed: {}", exc)
            return False

    async def disconnect(self) -> None:
        if self._connector:
            await self._connector.close()
            self._connector = None
            self._order_manager = None

    async def is_connected(self) -> bool:
        return self._connector is not None and self._connector.connected

    def _ensure_connected(self) -> tuple[QuikConnector, OrderManager]:
        if not self._connector or not self._order_manager:
            raise ConnectionError("QUIK not connected")
        return self._connector, self._order_manager

    async def place_order(self, ticker: str, side: OrderSide, qty: int,
                          order_type: OrderType = OrderType.MARKET,
                          price: float | None = None) -> BrokerOrder:
        _, om = self._ensure_connected()

        quik_side = "buy" if side == OrderSide.BUY else "sell"
        quik_type = "market" if order_type == OrderType.MARKET else "limit"

        order_id = await om.send_order(
            class_code=self._class_code,
            sec_code=ticker,
            side=quik_side,
            qty=qty,
            price=price,
            order_type=quik_type,
            account=self._account or None,
            client_code=self._client_code or None,
        )

        order = om.get_order_status(order_id)
        status = _STATUS_MAP.get(order.status, OrderStatus.PENDING) if order else OrderStatus.SENT

        return BrokerOrder(
            order_id=order_id,
            ticker=ticker,
            side=side,
            order_type=order_type,
            qty=qty,
            price=price,
            filled_qty=order.filled_qty if order else 0,
            avg_fill_price=order.avg_fill_price if order else 0.0,
            status=status,
            timestamp=datetime.now(timezone.utc),
        )

    async def cancel_order(self, order_id: str) -> bool:
        _, om = self._ensure_connected()
        try:
            await om.cancel_order(order_id)
            return True
        except Exception as exc:
            logger.error("QUIK cancel_order failed: {}", exc)
            return False

    async def get_order_status(self, order_id: str) -> BrokerOrder:
        _, om = self._ensure_connected()
        order = om.get_order_status(order_id)
        if not order:
            raise ValueError(f"order {order_id} not found")

        side = OrderSide.BUY if order.side == QuikSide.BUY else OrderSide.SELL
        o_type = OrderType.MARKET if order.order_type == QuikType.MARKET else OrderType.LIMIT
        status = _STATUS_MAP.get(order.status, OrderStatus.PENDING)

        return BrokerOrder(
            order_id=order_id,
            ticker=order.sec_code,
            side=side,
            order_type=o_type,
            qty=order.qty,
            price=order.price if order.price > 0 else None,
            filled_qty=order.filled_qty,
            avg_fill_price=order.avg_fill_price,
            status=status,
            timestamp=datetime.now(timezone.utc),
        )

    async def get_orders(self, active_only: bool = True) -> list[BrokerOrder]:
        _, om = self._ensure_connected()
        quik_orders = om.get_all_orders(active_only=active_only)

        orders = []
        for o in quik_orders:
            side = OrderSide.BUY if o.side == QuikSide.BUY else OrderSide.SELL
            o_type = OrderType.MARKET if o.order_type == QuikType.MARKET else OrderType.LIMIT
            status = _STATUS_MAP.get(o.status, OrderStatus.PENDING)
            orders.append(BrokerOrder(
                order_id=o.order_id,
                ticker=o.sec_code,
                side=side,
                order_type=o_type,
                qty=o.qty,
                price=o.price if o.price > 0 else None,
                filled_qty=o.filled_qty,
                avg_fill_price=o.avg_fill_price,
                status=status,
                timestamp=datetime.now(timezone.utc),
            ))
        return orders

    async def get_portfolio(self) -> BrokerPortfolio:
        _, om = self._ensure_connected()
        positions = await self.get_positions()
        total = await om.get_portfolio_value()
        return BrokerPortfolio(total_value=total, cash=0.0, positions=positions)

    async def get_positions(self) -> list[BrokerPosition]:
        _, om = self._ensure_connected()
        quik_positions = await om.get_positions()

        positions = []
        for pos in quik_positions.values():
            if pos.qty == 0:
                continue
            positions.append(BrokerPosition(
                ticker=pos.sec_code,
                qty=pos.qty,
                avg_price=pos.avg_price,
                current_price=pos.market_value / abs(pos.qty) if pos.qty else 0.0,
                unrealized_pnl=pos.unrealized_pnl,
            ))
        return positions

    async def get_quote(self, ticker: str) -> BrokerQuote:
        conn, _ = self._ensure_connected()
        data = await conn.get_quote(self._class_code, ticker)
        return BrokerQuote(
            ticker=ticker,
            bid=float(data.get("bid", 0)),
            ask=float(data.get("ask", 0)),
            last=float(data.get("last", 0)),
            volume=int(data.get("volume", 0)),
            timestamp=datetime.now(timezone.utc),
        )

    async def get_candles(self, ticker: str, interval: str = "1d",
                          count: int = 100) -> list[BrokerCandle]:
        conn, _ = self._ensure_connected()
        interval_map = {"1m": 1, "5m": 5, "15m": 15, "1h": 60, "1d": 1440}
        quik_interval = interval_map.get(interval, 1440)

        data = await conn.get_candles(self._class_code, ticker, quik_interval, count)

        candles = []
        for c in data.get("candles", []):
            candles.append(BrokerCandle(
                datetime=datetime.fromisoformat(c["datetime"]) if isinstance(c.get("datetime"), str)
                         else datetime.now(timezone.utc),
                open=float(c.get("open", 0)),
                high=float(c.get("high", 0)),
                low=float(c.get("low", 0)),
                close=float(c.get("close", 0)),
                volume=int(c.get("volume", 0)),
            ))
        return candles

    async def subscribe_quotes(self, tickers: list[str]) -> AsyncIterator[BrokerQuote]:
        conn, _ = self._ensure_connected()
        queue: asyncio.Queue[BrokerQuote] = asyncio.Queue()

        async def _on_quote(data: dict[str, Any]) -> None:
            ticker = data.get("sec_code", "")
            if ticker in tickers:
                quote = BrokerQuote(
                    ticker=ticker,
                    bid=float(data.get("bid", 0)),
                    ask=float(data.get("ask", 0)),
                    last=float(data.get("last", 0)),
                    volume=int(data.get("volume", 0)),
                    timestamp=datetime.now(timezone.utc),
                )
                await queue.put(quote)

        conn.on_quote(_on_quote)
        for ticker in tickers:
            await conn.subscribe(self._class_code, ticker)

        while True:
            yield await queue.get()

    async def get_accounts(self) -> list[dict[str, Any]]:
        conn, _ = self._ensure_connected()
        info = await conn.get_info()
        return [{"id": self._account, "name": info.get("server", "QUIK"),
                 "type": "quik"}]
