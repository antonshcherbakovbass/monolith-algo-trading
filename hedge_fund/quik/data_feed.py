"""Market data manager for QUIK integration.

Maintains an in-memory cache of quotes and order books, aggregates ticks
into multi-timeframe candles, and exposes async generators for streaming.
"""

from __future__ import annotations

import asyncio
import enum
import logging
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Any, AsyncIterator

from .connector import QuikConnector

logger = logging.getLogger(__name__)

_MOSCOW_TZ = timezone(timedelta(hours=3))


class Timeframe(enum.Enum):
    S1 = 1
    S5 = 5
    M1 = 60
    M5 = 300
    M15 = 900
    H1 = 3600
    D1 = 86400


class SessionType(enum.Enum):
    PRE_MARKET = "pre_market"
    MAIN = "main"
    EVENING = "evening"
    CLOSED = "closed"


_SESSION_RANGES: list[tuple[SessionType, tuple[int, int], tuple[int, int]]] = [
    (SessionType.PRE_MARKET, (9, 50), (10, 0)),
    (SessionType.MAIN, (10, 0), (18, 40)),
    (SessionType.EVENING, (19, 5), (23, 50)),
]


def current_session() -> SessionType:
    """Determine the current MOEX session based on Moscow time."""
    now = datetime.now(_MOSCOW_TZ)
    t = (now.hour, now.minute)
    for session, start, end_ in _SESSION_RANGES:
        if start <= t < end_:
            return session
    return SessionType.CLOSED


@dataclass
class Quote:
    class_code: str
    sec_code: str
    last: float = 0.0
    bid: float = 0.0
    ask: float = 0.0
    volume: int = 0
    open: float = 0.0
    high: float = 0.0
    low: float = 0.0
    close: float = 0.0
    change: float = 0.0
    change_pct: float = 0.0
    waprice: float = 0.0
    timestamp: float = field(default_factory=time.time)


@dataclass
class OrderBookLevel:
    price: float
    quantity: int


@dataclass
class OrderBook:
    class_code: str
    sec_code: str
    bids: list[OrderBookLevel] = field(default_factory=list)
    asks: list[OrderBookLevel] = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)

    @property
    def spread(self) -> float:
        if self.asks and self.bids:
            return self.asks[0].price - self.bids[0].price
        return 0.0

    @property
    def mid_price(self) -> float:
        if self.asks and self.bids:
            return (self.asks[0].price + self.bids[0].price) / 2.0
        return 0.0


@dataclass
class Candle:
    open: float
    high: float
    low: float
    close: float
    volume: int
    vwap: float
    tick_count: int
    timestamp: float


@dataclass
class TickData:
    price: float
    volume: int
    timestamp: float
    direction: int = 0  # 1=uptick, -1=downtick, 0=neutral


class DataFeed:
    """Market data manager with caching, candle aggregation, and streaming."""

    def __init__(self, connector: QuikConnector, max_ticks: int = 50_000) -> None:
        self._connector = connector
        self._max_ticks = max_ticks

        self._quotes: dict[str, Quote] = {}
        self._orderbooks: dict[str, OrderBook] = {}
        self._ticks: dict[str, deque[TickData]] = defaultdict(lambda: deque(maxlen=max_ticks))
        self._candles: dict[str, dict[Timeframe, deque[Candle]]] = defaultdict(
            lambda: {tf: deque(maxlen=10_000) for tf in Timeframe}
        )
        self._last_candle_ts: dict[str, dict[Timeframe, float]] = defaultdict(
            lambda: {tf: 0.0 for tf in Timeframe}
        )
        self._subscriptions: set[str] = set()

        self._quote_events: dict[str, list[asyncio.Event]] = defaultdict(list)
        self._orderbook_events: dict[str, list[asyncio.Event]] = defaultdict(list)

        connector.on_quote(self._on_quote)

    def _key(self, class_code: str, sec_code: str) -> str:
        return f"{class_code}:{sec_code}"

    # ------------------------------------------------------------------
    # Subscriptions
    # ------------------------------------------------------------------

    async def subscribe(self, class_code: str, sec_code: str) -> None:
        key = self._key(class_code, sec_code)
        if key in self._subscriptions:
            return
        await self._connector.subscribe(class_code, sec_code)
        self._subscriptions.add(key)
        logger.info("subscribed to %s", key)

    async def unsubscribe(self, class_code: str, sec_code: str) -> None:
        key = self._key(class_code, sec_code)
        if key not in self._subscriptions:
            return
        await self._connector.unsubscribe(class_code, sec_code)
        self._subscriptions.discard(key)
        logger.info("unsubscribed from %s", key)

    # ------------------------------------------------------------------
    # Quote callback
    # ------------------------------------------------------------------

    async def _on_quote(self, data: dict[str, Any]) -> None:
        cc = data.get("class_code", "")
        sc = data.get("sec_code", "")
        key = self._key(cc, sc)

        now = time.time()
        quote = Quote(
            class_code=cc,
            sec_code=sc,
            last=data.get("last", 0.0) or 0.0,
            bid=data.get("bid", 0.0) or 0.0,
            ask=data.get("ask", 0.0) or 0.0,
            volume=int(data.get("volume", 0) or 0),
            open=data.get("open", 0.0) or 0.0,
            high=data.get("high", 0.0) or 0.0,
            low=data.get("low", 0.0) or 0.0,
            close=data.get("close", 0.0) or 0.0,
            change=data.get("change", 0.0) or 0.0,
            change_pct=data.get("change_pct", 0.0) or 0.0,
            waprice=data.get("waprice", 0.0) or 0.0,
            timestamp=now,
        )
        prev = self._quotes.get(key)
        self._quotes[key] = quote

        direction = 0
        if prev and quote.last != prev.last:
            direction = 1 if quote.last > prev.last else -1

        tick = TickData(price=quote.last, volume=quote.volume, timestamp=now, direction=direction)
        self._ticks[key].append(tick)
        self._aggregate_candles(key, tick)

        for evt in self._quote_events.get(key, []):
            evt.set()

    # ------------------------------------------------------------------
    # Candle aggregation
    # ------------------------------------------------------------------

    def _aggregate_candles(self, key: str, tick: TickData) -> None:
        for tf in Timeframe:
            interval = tf.value
            bucket = int(tick.timestamp // interval) * interval
            candles_deque = self._candles[key][tf]
            last_ts = self._last_candle_ts[key][tf]

            if bucket > last_ts:
                candle = Candle(
                    open=tick.price,
                    high=tick.price,
                    low=tick.price,
                    close=tick.price,
                    volume=tick.volume,
                    vwap=tick.price,
                    tick_count=1,
                    timestamp=bucket,
                )
                candles_deque.append(candle)
                self._last_candle_ts[key][tf] = bucket
            elif candles_deque:
                c = candles_deque[-1]
                c.high = max(c.high, tick.price)
                c.low = min(c.low, tick.price)
                c.close = tick.price
                c.volume += tick.volume
                c.tick_count += 1
                total_value = c.vwap * (c.tick_count - 1) + tick.price
                c.vwap = total_value / c.tick_count

    # ------------------------------------------------------------------
    # Data access
    # ------------------------------------------------------------------

    def get_quote(self, class_code: str, sec_code: str) -> Quote | None:
        return self._quotes.get(self._key(class_code, sec_code))

    def get_orderbook(self, class_code: str, sec_code: str) -> OrderBook | None:
        return self._orderbooks.get(self._key(class_code, sec_code))

    def get_candles(
        self, class_code: str, sec_code: str, tf: Timeframe, count: int = 100
    ) -> list[Candle]:
        key = self._key(class_code, sec_code)
        candles_deque = self._candles.get(key, {}).get(tf)
        if not candles_deque:
            return []
        items = list(candles_deque)
        return items[-count:]

    def get_vwap(self, class_code: str, sec_code: str) -> float:
        """Calculate VWAP from all stored ticks."""
        key = self._key(class_code, sec_code)
        ticks = self._ticks.get(key)
        if not ticks:
            return 0.0
        total_pv = sum(t.price * t.volume for t in ticks if t.volume > 0)
        total_v = sum(t.volume for t in ticks if t.volume > 0)
        return total_pv / total_v if total_v > 0 else 0.0

    def get_spread(self, class_code: str, sec_code: str) -> float:
        ob = self.get_orderbook(class_code, sec_code)
        return ob.spread if ob else 0.0

    def get_tick_direction(self, class_code: str, sec_code: str) -> int:
        key = self._key(class_code, sec_code)
        ticks = self._ticks.get(key)
        if not ticks:
            return 0
        return ticks[-1].direction

    # ------------------------------------------------------------------
    # Async orderbook refresh
    # ------------------------------------------------------------------

    async def refresh_orderbook(self, class_code: str, sec_code: str) -> OrderBook:
        data = await self._connector.get_orderbook(class_code, sec_code)
        key = self._key(class_code, sec_code)
        ob = OrderBook(
            class_code=class_code,
            sec_code=sec_code,
            bids=[OrderBookLevel(price=b["price"], quantity=b["quantity"]) for b in data.get("bids", [])],
            asks=[OrderBookLevel(price=a["price"], quantity=a["quantity"]) for a in data.get("asks", [])],
            timestamp=time.time(),
        )
        self._orderbooks[key] = ob
        for evt in self._orderbook_events.get(key, []):
            evt.set()
        return ob

    # ------------------------------------------------------------------
    # Streaming generators
    # ------------------------------------------------------------------

    async def stream_quotes(self, class_code: str, sec_code: str) -> AsyncIterator[Quote]:
        """Yield quotes as they arrive. Caller must break to stop."""
        key = self._key(class_code, sec_code)
        evt = asyncio.Event()
        self._quote_events[key].append(evt)
        try:
            while True:
                await evt.wait()
                evt.clear()
                quote = self._quotes.get(key)
                if quote:
                    yield quote
        finally:
            self._quote_events[key].remove(evt)

    async def stream_orderbook(
        self, class_code: str, sec_code: str, poll_interval: float = 0.5
    ) -> AsyncIterator[OrderBook]:
        """Poll and yield orderbook updates."""
        key = self._key(class_code, sec_code)
        evt = asyncio.Event()
        self._orderbook_events[key].append(evt)
        try:
            while True:
                ob = await self.refresh_orderbook(class_code, sec_code)
                yield ob
                try:
                    await asyncio.wait_for(evt.wait(), timeout=poll_interval)
                    evt.clear()
                except asyncio.TimeoutError:
                    pass
        finally:
            self._orderbook_events[key].remove(evt)

    async def fetch_historical_candles(
        self,
        class_code: str,
        sec_code: str,
        interval: int = 1,
        count: int = 100,
    ) -> list[dict[str, Any]]:
        """Fetch historical candles from QUIK DataSource."""
        result = await self._connector.get_candles(class_code, sec_code, interval, count)
        return result.get("candles", [])
