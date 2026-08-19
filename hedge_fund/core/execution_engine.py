"""Signal-to-order execution pipeline shared by orchestrator and tests."""
from __future__ import annotations

from typing import Any
from collections import deque

from ..agents.base_agent import Action, AgentSignal
from ..brokers.base import BaseBroker, OrderSide, OrderType
from ..core.event_bus import Event, EventType
from ..core.config_loader import class_code_for_ticker
from ..risk.daily_loss_lock import DailyLossLock
from ..risk.position_sizer import PositionSizer
from ..utils.logger import get_logger

log = get_logger("core.execution")


class ExecutionEngine:
    """Turns approved agent signals into broker orders."""

    def __init__(
        self,
        *,
        order_manager: Any = None,
        broker_api: BaseBroker | None = None,
        position_sizer: PositionSizer | None = None,
        daily_loss_lock: DailyLossLock | None = None,
        emergency_stop: Any = None,
        event_bus: Any = None,
        config: dict | None = None,
        default_portfolio_value: float = 1_000_000.0,
        paper: bool = True,
    ) -> None:
        self._order_manager = order_manager
        self._broker_api = broker_api
        self._position_sizer = position_sizer
        self._daily_loss_lock = daily_loss_lock
        self._emergency_stop = emergency_stop
        self._event_bus = event_bus
        self._config = config or {}
        self._default_portfolio_value = default_portfolio_value
        self._paper = paper
        self.executed_count = 0
        self.recent_executions: deque[dict[str, Any]] = deque(maxlen=50)

    async def get_portfolio_value(self) -> float:
        try:
            if self._order_manager is not None:
                value = await self._order_manager.get_portfolio_value()
                if value > 0:
                    return value
            if self._broker_api is not None:
                portfolio = await self._broker_api.get_portfolio()
                if portfolio.total_value > 0:
                    return portfolio.total_value
        except Exception as exc:
            log.debug("portfolio value lookup failed: {}", exc)
        return self._default_portfolio_value

    async def execute_signal(self, sig: AgentSignal) -> str | None:
        if self._emergency_stop and self._emergency_stop.is_active():
            log.warning("execution blocked — emergency stop active")
            return None

        if self._daily_loss_lock and self._daily_loss_lock.is_locked():
            log.warning("execution blocked — daily loss lock active")
            return None

        if sig.action == Action.HOLD:
            return None

        portfolio_value = await self.get_portfolio_value()
        if self._daily_loss_lock:
            self._daily_loss_lock.portfolio_value = portfolio_value

        price = sig.price
        if price <= 0:
            price = await self._resolve_price(sig.ticker) or (100.0 if self._paper else 0.0)
        if price <= 0:
            log.warning("cannot execute {} {} — no price", sig.action.value, sig.ticker)
            return None

        qty = sig.qty
        if qty <= 0 and self._position_sizer:
            atr = float(sig.metadata.get("atr", 0) or 0)
            sized = self._position_sizer.calculate(
                sig.ticker,
                portfolio_value,
                sig.confidence,
                volatility=atr,
                price=price,
            )
            qty = sized.recommended_qty

        if qty <= 0:
            log.warning("cannot execute {} {} — qty is zero", sig.action.value, sig.ticker)
            return None

        side = self._side_for_action(sig.action)
        if side is None:
            return None

        class_code = class_code_for_ticker(sig.ticker, self._config)
        idempotency_key = f"{sig.agent_name}:{sig.ticker}:{sig.action.value}:{sig.timestamp.isoformat()}"

        try:
            if self._broker_api is not None:
                order_id = await self._execute_via_broker(sig, side, qty, price)
            elif self._order_manager is not None:
                order_id = await self._order_manager.send_order(
                    class_code,
                    sig.ticker,
                    side,
                    qty,
                    price=price if sig.action != Action.CLOSE else None,
                    order_type="market" if sig.action == Action.CLOSE or sig.price <= 0 else "limit",
                    comment=f"{sig.agent_name}:{sig.strategy_name}",
                    idempotency_key=idempotency_key,
                )
            else:
                log.error("no order manager or broker configured")
                return None
        except Exception as exc:
            log.error("order execution failed for {} {}: {}", sig.action.value, sig.ticker, exc)
            if self._event_bus:
                await self._event_bus.publish(Event(
                    type=EventType.ORDER_REJECTED,
                    payload={"ticker": sig.ticker, "action": sig.action.value, "error": str(exc)},
                    source="execution_engine",
                ))
            return None

        self.executed_count += 1
        trade_value = qty * price
        self.recent_executions.append({
            "order_id": order_id,
            "ticker": sig.ticker,
            "side": side.upper(),
            "qty": qty,
            "price": price,
            "agent": sig.agent_name,
            "timestamp": sig.timestamp.isoformat(),
        })
        log.info(
            "EXECUTED {} {} x{} @ {:.2f} (= {:.0f} RUB) via {}",
            side.upper(),
            sig.ticker,
            qty,
            price,
            trade_value,
            sig.agent_name,
        )

        if self._event_bus:
            await self._event_bus.publish(Event(
                type=EventType.ORDER_EXECUTED,
                payload={
                    "order_id": order_id,
                    "ticker": sig.ticker,
                    "side": side,
                    "qty": qty,
                    "price": price,
                    "agent": sig.agent_name,
                    "paper": self._paper,
                },
                source="execution_engine",
            ))
        return order_id

    async def _resolve_price(self, ticker: str) -> float:
        if self._broker_api is not None:
            try:
                quote = await self._broker_api.get_quote(ticker)
                if quote.last > 0:
                    return quote.last
                if quote.bid > 0 and quote.ask > 0:
                    return (quote.bid + quote.ask) / 2
            except Exception:
                pass
        return 0.0

    async def _execute_via_broker(
        self,
        sig: AgentSignal,
        side: str,
        qty: int,
        price: float,
    ) -> str:
        assert self._broker_api is not None
        broker_side = OrderSide.BUY if side == "buy" else OrderSide.SELL
        order_type = OrderType.MARKET if sig.price <= 0 or sig.action == Action.CLOSE else OrderType.LIMIT
        order = await self._broker_api.place_order(
            sig.ticker,
            broker_side,
            qty,
            order_type=order_type,
            price=price if order_type == OrderType.LIMIT else None,
        )
        return order.order_id

    @staticmethod
    def _side_for_action(action: Action) -> str | None:
        if action == Action.BUY:
            return "buy"
        if action in (Action.SELL, Action.CLOSE):
            return "sell"
        return None
