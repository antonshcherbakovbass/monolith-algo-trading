"""Order execution engine for QUIK integration.

Supports live and paper trading modes, maintains an order state machine,
and provides position tracking, execution reporting, partial fill handling,
order timeout, retry logic, idempotency, audit logging, and concurrent
order limits.
"""

from __future__ import annotations

import asyncio
import enum
import random
import time
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Protocol

from ..core.graceful_degradation import GracefulDegradation
from ..utils.logger import get_logger
from .connector import QuikConnector

logger = get_logger("trade.order_manager")


class OrderSide(enum.Enum):
    BUY = "B"
    SELL = "S"


class OrderType(enum.Enum):
    LIMIT = "L"
    MARKET = "M"


class OrderStatus(enum.Enum):
    PENDING = "pending"
    SENT = "sent"
    ACTIVE = "active"
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"

    @property
    def is_terminal(self) -> bool:
        return self in (OrderStatus.FILLED, OrderStatus.CANCELLED, OrderStatus.REJECTED)


class CommissionCalculator(Protocol):
    def calculate(self, class_code: str, sec_code: str, price: float, qty: int, side: OrderSide) -> float: ...


@dataclass
class ExecutionReport:
    order_id: str
    status: OrderStatus
    filled_qty: int
    avg_price: float
    commission: float
    timestamp: float
    message: str = ""


@dataclass
class AuditEntry:
    """Immutable record of an order state transition."""
    timestamp: float
    order_id: str
    old_status: OrderStatus
    new_status: OrderStatus
    detail: str = ""


@dataclass
class Order:
    order_id: str
    class_code: str
    sec_code: str
    side: OrderSide
    order_type: OrderType
    price: float
    qty: int
    status: OrderStatus = OrderStatus.PENDING
    filled_qty: int = 0
    avg_fill_price: float = 0.0
    quik_order_num: str = ""
    trans_id: int = 0
    account: str = ""
    client_code: str = ""
    commission: float = 0.0
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    reports: list[ExecutionReport] = field(default_factory=list)
    idempotency_key: str = ""
    retry_count: int = 0
    max_retries: int = 2
    timeout_seconds: float = 0.0

    @property
    def remaining_qty(self) -> int:
        return self.qty - self.filled_qty

    @property
    def is_terminal(self) -> bool:
        return self.status.is_terminal

    @property
    def fill_ratio(self) -> float:
        return self.filled_qty / self.qty if self.qty > 0 else 0.0


@dataclass
class Position:
    sec_code: str
    class_code: str
    qty: int
    avg_price: float
    market_value: float = 0.0
    unrealized_pnl: float = 0.0


class OrderManager:
    """Order execution engine supporting live and paper trading.

    Enhancements:
    * Partial fill tracking with VWAP
    * Full order state machine with audit log
    * Split execution detection and merge
    * Configurable order timeout with auto-cancel
    * Retry logic for price-related rejections
    * Idempotency via deduplication keys
    * ``close_all_positions()`` for emergency flat
    * Concurrent pending order limit
    """

    def __init__(
        self,
        connector: QuikConnector | None,
        *,
        paper_trading: bool = False,
        account: str = "",
        client_code: str = "",
        firmid: str = "",
        max_orders_per_second: int = 10,
        default_slippage_bps: float = 5.0,
        commission_calculator: CommissionCalculator | None = None,
        max_concurrent_pending: int = 50,
        default_order_timeout: float = 60.0,
        max_retries_on_reject: int = 2,
        retry_price_adjust_bps: float = 10.0,
        degradation: GracefulDegradation | None = None,
    ) -> None:
        self._connector = connector
        self._paper = paper_trading
        self._account = account
        self._client_code = client_code
        self._firmid = firmid
        self._max_rate = max_orders_per_second
        self._slippage_bps = default_slippage_bps
        self._commission_calc = commission_calculator
        self._max_pending = max_concurrent_pending
        self._default_timeout = default_order_timeout
        self._max_retries = max_retries_on_reject
        self._retry_adjust_bps = retry_price_adjust_bps
        self._degradation = degradation

        self._orders: dict[str, Order] = {}
        self._trans_id_counter = int(time.time()) % 1_000_000
        self._trans_to_order: dict[int, str] = {}
        self._quik_to_order: dict[str, str] = {}
        self._idempotency_seen: set[str] = set()

        self._paper_positions: dict[str, Position] = {}
        self._paper_fills: list[ExecutionReport] = []
        self._paper_cash: float = 1_000_000.0

        self._rate_tokens = max_orders_per_second
        self._rate_last_refill = time.monotonic()
        self._rate_lock = asyncio.Lock()

        self._order_callbacks: list[Callable[[Order, ExecutionReport], Any]] = []
        self._audit_log: deque[AuditEntry] = deque(maxlen=10_000)
        self._timeout_tasks: dict[str, asyncio.Task[None]] = {}

        if connector is not None:
            connector.on_order(self._on_order_event)
            connector.on_trade(self._on_trade_event)
            connector.on_trans_reply(self._on_trans_reply_event)

    # ------------------------------------------------------------------
    # Audit log
    # ------------------------------------------------------------------

    def _audit(self, order: Order, old: OrderStatus, new: OrderStatus, detail: str = "") -> None:
        entry = AuditEntry(
            timestamp=time.time(),
            order_id=order.order_id,
            old_status=old,
            new_status=new,
            detail=detail,
        )
        self._audit_log.append(entry)
        logger.info(
            "order {} state {} → {} {}",
            order.order_id, old.value, new.value, detail,
        )

    def _set_status(self, order: Order, new: OrderStatus, detail: str = "") -> None:
        old = order.status
        if old == new:
            return
        order.status = new
        order.updated_at = time.time()
        self._audit(order, old, new, detail)

    def get_audit_log(self, order_id: str | None = None) -> list[AuditEntry]:
        if order_id is None:
            return list(self._audit_log)
        return [e for e in self._audit_log if e.order_id == order_id]

    # ------------------------------------------------------------------
    # Rate limiting
    # ------------------------------------------------------------------

    async def _acquire_rate_token(self) -> None:
        async with self._rate_lock:
            now = time.monotonic()
            elapsed = now - self._rate_last_refill
            if elapsed >= 1.0:
                self._rate_tokens = self._max_rate
                self._rate_last_refill = now
            if self._rate_tokens <= 0:
                wait = 1.0 - elapsed
                if wait > 0:
                    await asyncio.sleep(wait)
                self._rate_tokens = self._max_rate
                self._rate_last_refill = time.monotonic()
            self._rate_tokens -= 1

    # ------------------------------------------------------------------
    # Concurrent order limit
    # ------------------------------------------------------------------

    @property
    def _pending_count(self) -> int:
        return sum(
            1 for o in self._orders.values()
            if o.status in (OrderStatus.PENDING, OrderStatus.SENT, OrderStatus.ACTIVE, OrderStatus.PARTIALLY_FILLED)
        )

    # ------------------------------------------------------------------
    # Transaction ID
    # ------------------------------------------------------------------

    def _next_trans_id(self) -> int:
        self._trans_id_counter += 1
        return self._trans_id_counter

    # ------------------------------------------------------------------
    # Callbacks
    # ------------------------------------------------------------------

    def on_execution(self, callback: Callable[[Order, ExecutionReport], Any]) -> None:
        self._order_callbacks.append(callback)

    def _emit_report(self, order: Order, report: ExecutionReport) -> None:
        order.reports.append(report)
        order.updated_at = time.time()
        for cb in self._order_callbacks:
            try:
                cb(order, report)
            except Exception as exc:
                logger.error("execution callback error: {}", exc)

    # ------------------------------------------------------------------
    # Order timeout
    # ------------------------------------------------------------------

    def _schedule_timeout(self, order: Order) -> None:
        timeout = order.timeout_seconds
        if timeout <= 0:
            return

        async def _timeout_worker() -> None:
            await asyncio.sleep(timeout)
            if order.is_terminal:
                return
            if order.filled_qty > 0:
                logger.warning(
                    "order {} timed out with partial fill {}/{}",
                    order.order_id, order.filled_qty, order.qty,
                )
            else:
                logger.warning("order {} timed out, cancelling", order.order_id)
            try:
                await self.cancel_order(order.order_id)
            except Exception as exc:
                logger.error("auto-cancel failed for {}: {}", order.order_id, exc)

        task = asyncio.create_task(_timeout_worker(), name=f"timeout-{order.order_id}")
        self._timeout_tasks[order.order_id] = task

    def _cancel_timeout(self, order_id: str) -> None:
        task = self._timeout_tasks.pop(order_id, None)
        if task and not task.done():
            task.cancel()

    # ------------------------------------------------------------------
    # Paper trading simulation
    # ------------------------------------------------------------------

    def _simulate_fill(self, order: Order) -> None:
        slippage_mult = 1.0
        if order.side == OrderSide.BUY:
            slippage_mult = 1.0 + self._slippage_bps / 10_000
        else:
            slippage_mult = 1.0 - self._slippage_bps / 10_000

        if order.order_type == OrderType.MARKET:
            fill_price = order.price * slippage_mult if order.price > 0 else 100.0
        else:
            noise = random.uniform(-0.5, 0.5) * self._slippage_bps / 10_000
            fill_price = order.price * (1.0 + noise)

        fill_price = round(fill_price, 6)
        fill_qty = order.qty

        commission = 0.0
        if self._commission_calc:
            commission = self._commission_calc.calculate(
                order.class_code, order.sec_code, fill_price, fill_qty, order.side
            )

        order.filled_qty = fill_qty
        order.avg_fill_price = fill_price
        order.commission = commission
        self._set_status(order, OrderStatus.FILLED, "paper fill")
        order.quik_order_num = f"PAPER-{order.trans_id}"

        report = ExecutionReport(
            order_id=order.order_id,
            status=OrderStatus.FILLED,
            filled_qty=fill_qty,
            avg_price=fill_price,
            commission=commission,
            timestamp=time.time(),
            message="paper fill",
        )
        self._emit_report(order, report)
        self._update_paper_position(order, fill_price, fill_qty)

    def _update_paper_position(self, order: Order, price: float, qty: int) -> None:
        key = f"{order.class_code}:{order.sec_code}"
        pos = self._paper_positions.get(key)
        signed_qty = qty if order.side == OrderSide.BUY else -qty

        if pos is None:
            pos = Position(
                sec_code=order.sec_code,
                class_code=order.class_code,
                qty=signed_qty,
                avg_price=price,
            )
            self._paper_positions[key] = pos
        else:
            old_value = pos.qty * pos.avg_price
            new_value = signed_qty * price
            new_qty = pos.qty + signed_qty
            if new_qty == 0:
                pos.qty = 0
                pos.avg_price = 0.0
            elif (pos.qty >= 0 and signed_qty > 0) or (pos.qty <= 0 and signed_qty < 0):
                pos.avg_price = (old_value + new_value) / new_qty if new_qty != 0 else 0.0
                pos.qty = new_qty
            else:
                pos.qty = new_qty
                if abs(new_qty) > 0 and ((new_qty > 0) == (signed_qty > 0)):
                    pos.avg_price = price

    # ------------------------------------------------------------------
    # Retry logic for price rejections
    # ------------------------------------------------------------------

    _PRICE_REJECTION_KEYWORDS: frozenset[str] = frozenset({
        "price", "цена", "лимит", "limit", "вне диапазона", "out of range",
    })

    def _is_price_rejection(self, message: str) -> bool:
        lower = message.lower()
        return any(kw in lower for kw in self._PRICE_REJECTION_KEYWORDS)

    async def _retry_with_adjusted_price(self, order: Order, reject_msg: str) -> str | None:
        if order.retry_count >= order.max_retries:
            return None
        if order.order_type != OrderType.LIMIT:
            return None
        if not self._is_price_rejection(reject_msg):
            return None

        adjust = self._retry_adjust_bps / 10_000
        if order.side == OrderSide.BUY:
            new_price = round(order.price * (1 + adjust), 6)
        else:
            new_price = round(order.price * (1 - adjust), 6)

        logger.info(
            "retrying {} with adjusted price {} → {} (attempt {})",
            order.order_id, order.price, new_price, order.retry_count + 1,
        )
        return await self.send_order(
            class_code=order.class_code,
            sec_code=order.sec_code,
            side=order.side,
            qty=order.remaining_qty or order.qty,
            price=new_price,
            order_type=order.order_type,
            account=order.account or None,
            client_code=order.client_code or None,
            _retry_of=order.order_id,
        )

    # ------------------------------------------------------------------
    # Live QUIK event handlers
    # ------------------------------------------------------------------

    async def _on_trans_reply_event(self, data: dict[str, Any]) -> None:
        trans_id = data.get("trans_id", 0)
        order_id = self._trans_to_order.get(trans_id)
        if not order_id:
            return
        order = self._orders.get(order_id)
        if not order:
            return

        status_code = data.get("status", 0)
        order_num = data.get("order_num", "")
        msg = data.get("result_msg", "")

        if order_num:
            order.quik_order_num = str(order_num)
            self._quik_to_order[str(order_num)] = order_id

        if status_code in (3, 6):
            self._set_status(order, OrderStatus.ACTIVE, msg)
            report = ExecutionReport(
                order_id=order_id, status=OrderStatus.ACTIVE,
                filled_qty=0, avg_price=0.0, commission=0.0,
                timestamp=time.time(), message=msg,
            )
            self._emit_report(order, report)
        elif status_code in (4, 5, 10, 11, 12, 13):
            self._set_status(order, OrderStatus.REJECTED, msg)
            self._cancel_timeout(order_id)
            report = ExecutionReport(
                order_id=order_id, status=OrderStatus.REJECTED,
                filled_qty=0, avg_price=0.0, commission=0.0,
                timestamp=time.time(), message=msg,
            )
            self._emit_report(order, report)
            # Attempt auto-retry for price-related rejections
            asyncio.create_task(self._retry_with_adjusted_price(order, msg))

    async def _on_order_event(self, data: dict[str, Any]) -> None:
        order_num = str(data.get("order_num", ""))
        order_id = self._quik_to_order.get(order_num)
        if not order_id:
            trans_id = data.get("trans_id", 0)
            order_id = self._trans_to_order.get(trans_id)
        if not order_id:
            return
        order = self._orders.get(order_id)
        if not order:
            return

        status_str = data.get("status", "")
        balance = data.get("balance", 0)

        if status_str == "cancelled":
            self._set_status(order, OrderStatus.CANCELLED)
            self._cancel_timeout(order_id)
        elif status_str == "filled":
            self._set_status(order, OrderStatus.FILLED)
            order.filled_qty = order.qty
            self._cancel_timeout(order_id)
        elif balance is not None and 0 < balance < order.qty:
            self._set_status(order, OrderStatus.PARTIALLY_FILLED)
            order.filled_qty = order.qty - balance

        report = ExecutionReport(
            order_id=order_id, status=order.status,
            filled_qty=order.filled_qty, avg_price=order.avg_fill_price,
            commission=order.commission, timestamp=time.time(),
        )
        self._emit_report(order, report)

    async def _on_trade_event(self, data: dict[str, Any]) -> None:
        order_num = str(data.get("order_num", ""))
        order_id = self._quik_to_order.get(order_num)
        if not order_id:
            return
        order = self._orders.get(order_id)
        if not order:
            return

        trade_price = data.get("price", 0.0)
        trade_qty = data.get("qty", 0)
        if trade_qty <= 0:
            return

        # VWAP for partial fills
        old_filled = order.filled_qty
        new_filled = old_filled + trade_qty
        if new_filled > order.qty:
            logger.warning(
                "order {} overfill: filled {}+{} > qty {}",
                order.order_id, old_filled, trade_qty, order.qty,
            )
            new_filled = order.qty
            trade_qty = order.qty - old_filled
            if trade_qty <= 0:
                return

        if old_filled > 0 and order.avg_fill_price > 0:
            order.avg_fill_price = (
                order.avg_fill_price * old_filled + trade_price * trade_qty
            ) / new_filled
        else:
            order.avg_fill_price = trade_price
        order.filled_qty = new_filled

        if new_filled >= order.qty:
            self._set_status(order, OrderStatus.FILLED, f"filled @ {order.avg_fill_price:.4f}")
            self._cancel_timeout(order.order_id)
        else:
            self._set_status(order, OrderStatus.PARTIALLY_FILLED, f"{new_filled}/{order.qty}")

        commission = 0.0
        if self._commission_calc:
            commission = self._commission_calc.calculate(
                order.class_code, order.sec_code, trade_price, trade_qty, order.side
            )
            order.commission += commission

        report = ExecutionReport(
            order_id=order_id, status=order.status,
            filled_qty=trade_qty, avg_price=trade_price,
            commission=commission, timestamp=time.time(),
        )
        self._emit_report(order, report)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def send_order(
        self,
        class_code: str,
        sec_code: str,
        side: str | OrderSide,
        qty: int,
        price: float | None = None,
        order_type: str | OrderType = "limit",
        *,
        account: str | None = None,
        client_code: str | None = None,
        comment: str = "",
        idempotency_key: str = "",
        timeout: float | None = None,
        _retry_of: str = "",
    ) -> str:
        """Submit a new order. Returns internal order_id.

        Parameters
        ----------
        idempotency_key:
            If provided and already seen, raises ``ValueError`` to prevent
            duplicate submission.
        timeout:
            Seconds after which an unfilled order is automatically cancelled.
            Defaults to ``default_order_timeout`` (0 = no timeout).
        """
        # Idempotency check
        if idempotency_key:
            if idempotency_key in self._idempotency_seen:
                raise ValueError(f"duplicate order: idempotency_key={idempotency_key!r}")
            self._idempotency_seen.add(idempotency_key)

        # Graceful degradation check
        if self._degradation and not self._degradation.is_trading_allowed():
            raise RuntimeError("trading is disabled due to system degradation")

        # Concurrent order limit
        if self._pending_count >= self._max_pending:
            raise RuntimeError(
                f"concurrent pending order limit reached ({self._max_pending})"
            )

        if isinstance(side, str):
            side = OrderSide.BUY if side.lower() in ("buy", "b") else OrderSide.SELL
        if isinstance(order_type, str):
            order_type = OrderType.MARKET if order_type.lower() in ("market", "m") else OrderType.LIMIT

        await self._acquire_rate_token()

        trans_id = self._next_trans_id()
        order_id = f"ORD-{trans_id}"

        effective_price = price if price is not None else 0.0
        effective_timeout = timeout if timeout is not None else self._default_timeout

        order = Order(
            order_id=order_id,
            class_code=class_code,
            sec_code=sec_code,
            side=side,
            order_type=order_type,
            price=effective_price,
            qty=qty,
            trans_id=trans_id,
            account=account or self._account,
            client_code=client_code or self._client_code,
            idempotency_key=idempotency_key,
            timeout_seconds=effective_timeout,
        )

        # Link retry chain
        if _retry_of:
            parent = self._orders.get(_retry_of)
            if parent:
                order.retry_count = parent.retry_count + 1
                order.max_retries = parent.max_retries

        self._orders[order_id] = order
        self._trans_to_order[trans_id] = order_id

        if self._paper:
            self._simulate_fill(order)
            return order_id

        if self._connector is None:
            raise RuntimeError("No QUIK connector configured for live trading")

        quik_type = "M" if order_type == OrderType.MARKET else "L"
        operation = "B" if side == OrderSide.BUY else "S"

        transaction: dict[str, Any] = {
            "TRANS_ID": str(trans_id),
            "ACTION": "NEW_ORDER",
            "CLASSCODE": class_code,
            "SECCODE": sec_code,
            "TYPE": quik_type,
            "OPERATION": operation,
            "QUANTITY": str(qty),
            "PRICE": str(effective_price),
        }
        if order.account:
            transaction["ACCOUNT"] = order.account
        if order.client_code:
            transaction["CLIENT_CODE"] = order.client_code
        if comment:
            transaction["COMMENT"] = comment

        try:
            self._set_status(order, OrderStatus.SENT, f"{operation} {sec_code} {qty}@{effective_price}")
            await self._connector.send_order(transaction)
            logger.info("order sent: {} {} {} {} @ {}", order_id, operation, sec_code, qty, effective_price)
            self._schedule_timeout(order)
        except Exception as exc:
            self._set_status(order, OrderStatus.REJECTED, str(exc))
            report = ExecutionReport(
                order_id=order_id, status=OrderStatus.REJECTED,
                filled_qty=0, avg_price=0.0, commission=0.0,
                timestamp=time.time(), message=str(exc),
            )
            self._emit_report(order, report)
            raise

        return order_id

    async def cancel_order(self, order_id: str) -> None:
        """Cancel an active order."""
        order = self._orders.get(order_id)
        if not order:
            raise ValueError(f"unknown order: {order_id}")
        if order.is_terminal:
            raise ValueError(f"order {order_id} is already {order.status.value}")

        self._cancel_timeout(order_id)

        if self._paper:
            self._set_status(order, OrderStatus.CANCELLED, "paper cancel")
            report = ExecutionReport(
                order_id=order_id, status=OrderStatus.CANCELLED,
                filled_qty=0, avg_price=0.0, commission=0.0,
                timestamp=time.time(), message="paper cancel",
            )
            self._emit_report(order, report)
            return

        await self._acquire_rate_token()
        await self._connector.cancel_order(
            order_id=order.quik_order_num,
            class_code=order.class_code,
            sec_code=order.sec_code,
            trans_id=self._next_trans_id(),
            account=order.account or None,
        )

    async def modify_order(self, order_id: str, new_price: float, new_qty: int) -> str:
        """Modify an order by cancelling and re-submitting."""
        order = self._orders.get(order_id)
        if not order:
            raise ValueError(f"unknown order: {order_id}")
        if order.is_terminal:
            raise ValueError(f"order {order_id} is already {order.status.value}")

        await self.cancel_order(order_id)
        await asyncio.sleep(0.1)

        return await self.send_order(
            class_code=order.class_code,
            sec_code=order.sec_code,
            side=order.side,
            qty=new_qty,
            price=new_price,
            order_type=order.order_type,
            account=order.account or None,
            client_code=order.client_code or None,
        )

    async def close_all_positions(self) -> list[str]:
        """Market-order close every open position. Returns list of new order IDs.

        In paper mode closes paper positions; in live mode reads positions
        from QUIK and submits market orders for the opposite side.
        """
        order_ids: list[str] = []
        positions = await self.get_positions()

        for key, pos in positions.items():
            if pos.qty == 0:
                continue
            side = OrderSide.SELL if pos.qty > 0 else OrderSide.BUY
            try:
                oid = await self.send_order(
                    class_code=pos.class_code,
                    sec_code=pos.sec_code,
                    side=side,
                    qty=abs(pos.qty),
                    order_type=OrderType.MARKET,
                    comment="close_all_positions",
                    timeout=30.0,
                )
                order_ids.append(oid)
            except Exception as exc:
                logger.error("failed to close position {}: {}", key, exc)

        logger.warning("close_all_positions: submitted {} orders", len(order_ids))
        return order_ids

    def get_order_status(self, order_id: str) -> Order | None:
        return self._orders.get(order_id)

    async def get_positions(self) -> dict[str, Position]:
        """Get current positions (paper or live)."""
        if self._paper:
            return dict(self._paper_positions)

        data = await self._connector.get_positions(account=self._account, firmid=self._firmid)
        positions: dict[str, Position] = {}
        for p in data.get("positions", []):
            key = f"{p.get('class_code', '')}:{p['sec_code']}"
            net = p.get("current", p.get("net", 0))
            positions[key] = Position(
                sec_code=p["sec_code"],
                class_code=p.get("class_code", ""),
                qty=int(net),
                avg_price=float(p.get("awg_price", 0)),
            )
        return positions

    async def get_portfolio_value(self) -> float:
        """Get total portfolio value from money limits."""
        if self._paper:
            total = self._paper_cash
            for pos in self._paper_positions.values():
                total += abs(pos.qty) * pos.avg_price
            return total

        if self._connector is None:
            return self._paper_cash

        data = await self._connector.get_money(
            firmid=self._firmid,
            client_code=self._client_code,
        )
        return float(data.get("balance", 0.0))

    def get_all_orders(self, active_only: bool = False) -> list[Order]:
        orders = list(self._orders.values())
        if active_only:
            orders = [o for o in orders if not o.is_terminal]
        return sorted(orders, key=lambda o: o.created_at, reverse=True)
