"""Market data adapter for API-based brokers (Tinkoff, Alor, Finam)."""
from __future__ import annotations

from typing import Any

from .base import BaseBroker


class BrokerDataFeed:
    """Minimal DataFeed-compatible wrapper around BaseBroker quotes."""

    def __init__(self, broker: BaseBroker) -> None:
        self._broker = broker
        self._subscribed: set[str] = set()

    async def subscribe(self, class_code: str, sec_code: str) -> None:
        self._subscribed.add(sec_code)

    async def get_quote(self, ticker: str) -> dict[str, Any] | None:
        try:
            quote = await self._broker.get_quote(ticker)
            return {
                "bid": quote.bid,
                "ask": quote.ask,
                "last": quote.last,
                "volume": quote.volume,
            }
        except Exception:
            return None

    async def get_orderbook(self, ticker: str) -> dict[str, Any] | None:
        return None
