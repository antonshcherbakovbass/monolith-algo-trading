"""Tinkoff Invest API broker connector.

Uses the tinkoff-investments package for gRPC streaming and REST operations.
Supports sandbox (paper) and production modes with built-in rate limiting.
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

logger = get_logger("brokers.tinkoff")

# Tinkoff interval mapping
_INTERVAL_MAP = {
    "1m": "CANDLE_INTERVAL_1_MIN",
    "5m": "CANDLE_INTERVAL_5_MIN",
    "15m": "CANDLE_INTERVAL_15_MIN",
    "1h": "CANDLE_INTERVAL_HOUR",
    "1d": "CANDLE_INTERVAL_DAY",
    "1w": "CANDLE_INTERVAL_WEEK",
    "1M": "CANDLE_INTERVAL_MONTH",
}


def _money_to_float(money: Any) -> float:
    """Convert Tinkoff MoneyValue to float."""
    if money is None:
        return 0.0
    return money.units + money.nano / 1e9


def _quotation_to_float(q: Any) -> float:
    """Convert Tinkoff Quotation to float."""
    if q is None:
        return 0.0
    return q.units + q.nano / 1e9


class TinkoffBroker(BaseBroker):
    """Broker connector for Tinkoff Invest API (T-Invest).

    Parameters
    ----------
    token : str
        API token from Tinkoff developer portal.
    account_id : str
        Trading account ID (sandbox or production).
    sandbox : bool
        If True, use sandbox environment for paper trading.
    """

    def __init__(self, token: str, account_id: str = "", sandbox: bool = False) -> None:
        self._token = token
        self._account_id = account_id
        self._sandbox = sandbox
        self._client: Any = None
        self._figi_cache: dict[str, str] = {}
        self._ticker_cache: dict[str, str] = {}
        self._rate_semaphore = asyncio.Semaphore(5)

    @property
    def name(self) -> str:
        return "Tinkoff Invest" + (" (sandbox)" if self._sandbox else "")

    @property
    def supports_streaming(self) -> bool:
        return True

    async def connect(self) -> bool:
        try:
            from tinkoff.invest import AsyncClient
            self._client = await AsyncClient(self._token, sandbox=self._sandbox).__aenter__()

            if not self._account_id:
                if self._sandbox:
                    resp = await self._client.sandbox.open_sandbox_account()
                    self._account_id = resp.account_id
                    logger.info("opened sandbox account: {}", self._account_id)
                else:
                    accounts = await self._client.users.get_accounts()
                    if accounts.accounts:
                        self._account_id = accounts.accounts[0].id
                    else:
                        logger.error("no accounts found")
                        return False

            logger.info("connected to Tinkoff, account={}", self._account_id)
            return True
        except Exception as exc:
            logger.error("Tinkoff connection failed: {}", exc)
            return False

    async def disconnect(self) -> None:
        if self._client:
            try:
                await self._client.__aexit__(None, None, None)
            except Exception:
                pass
            self._client = None

    async def is_connected(self) -> bool:
        return self._client is not None

    async def _resolve_figi(self, ticker: str) -> str:
        """Resolve MOEX ticker to Tinkoff FIGI."""
        if ticker in self._figi_cache:
            return self._figi_cache[ticker]

        from tinkoff.invest import InstrumentIdType
        try:
            resp = await self._client.instruments.find_instrument(query=ticker)
            for instr in resp.instruments:
                if instr.ticker.upper() == ticker.upper():
                    self._figi_cache[ticker] = instr.figi
                    self._ticker_cache[instr.figi] = ticker
                    return instr.figi
        except Exception as exc:
            logger.error("FIGI resolution failed for {}: {}", ticker, exc)

        raise ValueError(f"cannot resolve ticker {ticker} to FIGI")

    def _figi_to_ticker(self, figi: str) -> str:
        return self._ticker_cache.get(figi, figi)

    async def place_order(self, ticker: str, side: OrderSide, qty: int,
                          order_type: OrderType = OrderType.MARKET,
                          price: float | None = None) -> BrokerOrder:
        from tinkoff.invest import OrderDirection, OrderType as TinkoffOrderType, Quotation

        figi = await self._resolve_figi(ticker)
        direction = (OrderDirection.ORDER_DIRECTION_BUY if side == OrderSide.BUY
                     else OrderDirection.ORDER_DIRECTION_SELL)
        t_order_type = (TinkoffOrderType.ORDER_TYPE_MARKET if order_type == OrderType.MARKET
                        else TinkoffOrderType.ORDER_TYPE_LIMIT)

        kwargs: dict[str, Any] = {
            "figi": figi,
            "quantity": qty,
            "direction": direction,
            "account_id": self._account_id,
            "order_type": t_order_type,
        }
        if price is not None and order_type == OrderType.LIMIT:
            units = int(price)
            nano = int((price - units) * 1e9)
            kwargs["price"] = Quotation(units=units, nano=nano)

        async with self._rate_semaphore:
            if self._sandbox:
                resp = await self._client.sandbox.post_sandbox_order(**kwargs)
            else:
                resp = await self._client.orders.post_order(**kwargs)

        status = OrderStatus.SENT
        if resp.execution_report_status.name == "EXECUTION_REPORT_STATUS_FILL":
            status = OrderStatus.FILLED

        return BrokerOrder(
            order_id=resp.order_id,
            ticker=ticker,
            side=side,
            order_type=order_type,
            qty=qty,
            price=price,
            filled_qty=resp.lots_executed,
            avg_fill_price=_money_to_float(resp.executed_order_price),
            status=status,
            timestamp=datetime.now(timezone.utc),
            broker_message=resp.message or "",
        )

    async def cancel_order(self, order_id: str) -> bool:
        try:
            async with self._rate_semaphore:
                if self._sandbox:
                    await self._client.sandbox.cancel_sandbox_order(
                        account_id=self._account_id, order_id=order_id)
                else:
                    await self._client.orders.cancel_order(
                        account_id=self._account_id, order_id=order_id)
            return True
        except Exception as exc:
            logger.error("cancel_order failed: {}", exc)
            return False

    async def get_order_status(self, order_id: str) -> BrokerOrder:
        async with self._rate_semaphore:
            resp = await self._client.orders.get_order_state(
                account_id=self._account_id, order_id=order_id)

        status_map = {
            "EXECUTION_REPORT_STATUS_FILL": OrderStatus.FILLED,
            "EXECUTION_REPORT_STATUS_REJECTED": OrderStatus.REJECTED,
            "EXECUTION_REPORT_STATUS_CANCELLED": OrderStatus.CANCELLED,
            "EXECUTION_REPORT_STATUS_NEW": OrderStatus.SENT,
            "EXECUTION_REPORT_STATUS_PARTIALLYFILL": OrderStatus.PARTIAL,
        }
        status = status_map.get(resp.execution_report_status.name, OrderStatus.PENDING)
        ticker = self._figi_to_ticker(resp.figi)
        side = OrderSide.BUY if resp.direction.name == "ORDER_DIRECTION_BUY" else OrderSide.SELL

        return BrokerOrder(
            order_id=order_id,
            ticker=ticker,
            side=side,
            order_type=OrderType.LIMIT,
            qty=resp.lots_requested,
            filled_qty=resp.lots_executed,
            avg_fill_price=_money_to_float(resp.average_position_price),
            status=status,
            timestamp=datetime.now(timezone.utc),
        )

    async def get_orders(self, active_only: bool = True) -> list[BrokerOrder]:
        async with self._rate_semaphore:
            resp = await self._client.orders.get_orders(account_id=self._account_id)

        orders = []
        for o in resp.orders:
            ticker = self._figi_to_ticker(o.figi)
            side = OrderSide.BUY if o.direction.name == "ORDER_DIRECTION_BUY" else OrderSide.SELL
            orders.append(BrokerOrder(
                order_id=o.order_id,
                ticker=ticker,
                side=side,
                order_type=OrderType.LIMIT,
                qty=o.lots_requested,
                filled_qty=o.lots_executed,
                status=OrderStatus.SENT,
                timestamp=datetime.now(timezone.utc),
            ))
        return orders

    async def get_portfolio(self) -> BrokerPortfolio:
        async with self._rate_semaphore:
            if self._sandbox:
                resp = await self._client.sandbox.get_sandbox_portfolio(account_id=self._account_id)
            else:
                resp = await self._client.operations.get_portfolio(account_id=self._account_id)

        positions = []
        for p in resp.positions:
            ticker = self._figi_to_ticker(p.figi)
            qty = int(_quotation_to_float(p.quantity))
            avg = _money_to_float(p.average_position_price)
            current = _money_to_float(p.current_price)
            pnl = _money_to_float(p.expected_yield)
            positions.append(BrokerPosition(
                ticker=ticker, qty=qty, avg_price=avg,
                current_price=current, unrealized_pnl=pnl,
            ))

        total = _money_to_float(resp.total_amount_portfolio)
        cash = _money_to_float(resp.total_amount_currencies)
        return BrokerPortfolio(total_value=total, cash=cash, positions=positions)

    async def get_positions(self) -> list[BrokerPosition]:
        portfolio = await self.get_portfolio()
        return portfolio.positions

    async def get_quote(self, ticker: str) -> BrokerQuote:
        figi = await self._resolve_figi(ticker)
        async with self._rate_semaphore:
            resp = await self._client.market_data.get_last_prices(figi=[figi])

        price = _quotation_to_float(resp.last_prices[0].price) if resp.last_prices else 0.0
        return BrokerQuote(
            ticker=ticker, bid=price, ask=price, last=price,
            volume=0, timestamp=datetime.now(timezone.utc),
        )

    async def get_candles(self, ticker: str, interval: str = "1d",
                          count: int = 100) -> list[BrokerCandle]:
        from tinkoff.invest import CandleInterval
        from datetime import timedelta

        figi = await self._resolve_figi(ticker)
        t_interval = getattr(CandleInterval, _INTERVAL_MAP.get(interval, "CANDLE_INTERVAL_DAY"))

        now = datetime.now(timezone.utc)
        delta_map = {"1m": 1, "5m": 5, "15m": 15, "1h": 60, "1d": 1440, "1w": 10080}
        minutes = delta_map.get(interval, 1440)
        from_dt = now - timedelta(minutes=minutes * count)

        async with self._rate_semaphore:
            resp = await self._client.market_data.get_candles(
                figi=figi, from_=from_dt, to=now, interval=t_interval)

        candles = []
        for c in resp.candles:
            candles.append(BrokerCandle(
                datetime=c.time,
                open=_quotation_to_float(c.open),
                high=_quotation_to_float(c.high),
                low=_quotation_to_float(c.low),
                close=_quotation_to_float(c.close),
                volume=c.volume,
            ))
        return candles[-count:]

    async def subscribe_quotes(self, tickers: list[str]) -> AsyncIterator[BrokerQuote]:
        from tinkoff.invest import MarketDataRequest, SubscribeLastPriceRequest, SubscriptionAction, LastPriceInstrument

        figis = [await self._resolve_figi(t) for t in tickers]
        instruments = [LastPriceInstrument(figi=f) for f in figis]

        async def _request_gen():
            yield MarketDataRequest(
                subscribe_last_price=SubscribeLastPriceRequest(
                    subscription_action=SubscriptionAction.SUBSCRIPTION_ACTION_SUBSCRIBE,
                    instruments=instruments,
                )
            )
            while True:
                await asyncio.sleep(3600)

        async for response in self._client.market_data_stream.market_data_stream(_request_gen()):
            if response.last_price:
                lp = response.last_price
                ticker = self._figi_to_ticker(lp.figi)
                price = _quotation_to_float(lp.price)
                yield BrokerQuote(
                    ticker=ticker, bid=price, ask=price, last=price,
                    volume=0, timestamp=lp.time or datetime.now(timezone.utc),
                )

    async def get_accounts(self) -> list[dict[str, Any]]:
        resp = await self._client.users.get_accounts()
        return [{"id": a.id, "name": a.name, "type": a.type.name} for a in resp.accounts]
