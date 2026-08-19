"""Abstract broker interface that all broker connectors must implement."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
from typing import Any, AsyncIterator


class OrderSide(Enum):
    BUY = "buy"
    SELL = "sell"


class OrderType(Enum):
    MARKET = "market"
    LIMIT = "limit"


class OrderStatus(Enum):
    PENDING = "pending"
    SENT = "sent"
    PARTIAL = "partial"
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"


@dataclass
class BrokerOrder:
    order_id: str
    ticker: str
    side: OrderSide
    order_type: OrderType
    qty: int
    price: float | None = None
    filled_qty: int = 0
    avg_fill_price: float = 0.0
    status: OrderStatus = OrderStatus.PENDING
    timestamp: datetime | None = None
    broker_message: str = ""


@dataclass
class BrokerPosition:
    ticker: str
    qty: int
    avg_price: float
    current_price: float = 0.0
    unrealized_pnl: float = 0.0


@dataclass
class BrokerPortfolio:
    total_value: float
    cash: float
    positions: list[BrokerPosition] = field(default_factory=list)


@dataclass
class BrokerCandle:
    datetime: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int


@dataclass
class BrokerQuote:
    ticker: str
    bid: float
    ask: float
    last: float
    volume: int
    timestamp: datetime


class BaseBroker(ABC):
    """Abstract broker connector. All brokers implement this interface."""

    @property
    @abstractmethod
    def name(self) -> str: ...

    @property
    @abstractmethod
    def supports_streaming(self) -> bool: ...

    @abstractmethod
    async def connect(self) -> bool: ...

    @abstractmethod
    async def disconnect(self) -> None: ...

    @abstractmethod
    async def is_connected(self) -> bool: ...

    # --- Orders ---
    @abstractmethod
    async def place_order(self, ticker: str, side: OrderSide, qty: int,
                          order_type: OrderType = OrderType.MARKET,
                          price: float | None = None) -> BrokerOrder: ...

    @abstractmethod
    async def cancel_order(self, order_id: str) -> bool: ...

    @abstractmethod
    async def get_order_status(self, order_id: str) -> BrokerOrder: ...

    @abstractmethod
    async def get_orders(self, active_only: bool = True) -> list[BrokerOrder]: ...

    # --- Portfolio ---
    @abstractmethod
    async def get_portfolio(self) -> BrokerPortfolio: ...

    @abstractmethod
    async def get_positions(self) -> list[BrokerPosition]: ...

    # --- Market data ---
    @abstractmethod
    async def get_quote(self, ticker: str) -> BrokerQuote: ...

    @abstractmethod
    async def get_candles(self, ticker: str, interval: str = "1d",
                          count: int = 100) -> list[BrokerCandle]: ...

    @abstractmethod
    async def subscribe_quotes(self, tickers: list[str]) -> AsyncIterator[BrokerQuote]: ...

    # --- Account ---
    @abstractmethod
    async def get_accounts(self) -> list[dict[str, Any]]: ...

    async def close_all_positions(self) -> list[BrokerOrder]:
        """Emergency close all positions with market orders."""
        positions = await self.get_positions()
        orders = []
        for pos in positions:
            if pos.qty > 0:
                order = await self.place_order(pos.ticker, OrderSide.SELL, abs(pos.qty))
                orders.append(order)
            elif pos.qty < 0:
                order = await self.place_order(pos.ticker, OrderSide.BUY, abs(pos.qty))
                orders.append(order)
        return orders
