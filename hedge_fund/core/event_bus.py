"""
Asynchronous Event Bus for inter-agent communication.

All agents publish and subscribe to typed events through this bus,
ensuring loose coupling and a deterministic processing pipeline.
"""

from __future__ import annotations

import asyncio
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Coroutine, TypeVar
from loguru import logger


class EventType(str, Enum):
    # Market data
    QUOTE_UPDATE = "quote_update"
    ORDERBOOK_UPDATE = "orderbook_update"
    TRADE_TICK = "trade_tick"
    CANDLE_CLOSE = "candle_close"

    # Agent signals pipeline (strict order)
    MARKET_REGIME_CHANGE = "market_regime_change"
    ALPHA_SIGNAL = "alpha_signal"           # from Quant/Scalping/DayTrade/LongTerm
    ORDER_PROPOSAL = "order_proposal"       # from Execution Desk
    HEDGE_OVERLAY = "hedge_overlay"         # from Hedging Agent
    RISK_VERDICT = "risk_verdict"           # from Risk Shield (approve/reject)
    ORDER_EXECUTED = "order_executed"       # confirmed by QUIK
    ORDER_REJECTED = "order_rejected"

    # System
    AGENT_STATUS = "agent_status"
    RISK_ALERT = "risk_alert"
    TELEGRAM_REPORT = "telegram_report"
    SYSTEM_HEALTH = "system_health"
    EMERGENCY_SHUTDOWN = "emergency_shutdown"
    DAILY_RESET = "daily_reset"


@dataclass
class Event:
    type: EventType
    payload: dict[str, Any]
    source: str = ""
    timestamp: datetime = field(default_factory=datetime.now)
    priority: int = 5  # 1=highest, 10=lowest
    event_id: str = ""

    def __post_init__(self) -> None:
        if not self.event_id:
            import uuid
            self.event_id = str(uuid.uuid4())[:12]


# Callback type: async function taking Event, returning None
EventHandler = Callable[[Event], Coroutine[Any, Any, None]]


class EventBus:
    """
    Central async event bus with priority-based dispatching.

    Features:
    - Typed pub/sub with EventType enum
    - Priority queue: risk/emergency events processed first
    - Handler timeout protection (default 5s)
    - Dead letter queue for failed events
    - Metrics: events processed, latency, errors
    """

    def __init__(self, handler_timeout: float = 5.0, max_queue_size: int = 10_000) -> None:
        self._subscribers: dict[EventType, list[tuple[str, EventHandler, int]]] = defaultdict(list)
        self._queue: asyncio.PriorityQueue[tuple[int, float, Event]] = asyncio.PriorityQueue(maxsize=max_queue_size)
        self._running = False
        self._task: asyncio.Task | None = None
        self._handler_timeout = handler_timeout
        self._dead_letters: list[tuple[Event, str]] = []
        self._metrics = {
            "events_published": 0,
            "events_processed": 0,
            "events_failed": 0,
            "avg_latency_ms": 0.0,
        }
        self._latency_sum = 0.0
        self.log = logger.bind(component="event_bus")

    def subscribe(self, event_type: EventType, handler: EventHandler,
                  subscriber_name: str = "", priority: int = 5) -> None:
        """Subscribe a handler to an event type. Lower priority number = called first."""
        self._subscribers[event_type].append((subscriber_name, handler, priority))
        self._subscribers[event_type].sort(key=lambda x: x[2])
        self.log.debug("Subscribed {} to {} (priority={})", subscriber_name, event_type.value, priority)

    def unsubscribe(self, event_type: EventType, subscriber_name: str) -> None:
        self._subscribers[event_type] = [
            (name, h, p) for name, h, p in self._subscribers[event_type]
            if name != subscriber_name
        ]

    async def publish(self, event: Event) -> None:
        """Publish an event to the bus. Non-blocking."""
        self._metrics["events_published"] += 1
        try:
            self._queue.put_nowait((event.priority, event.timestamp.timestamp(), event))
        except asyncio.QueueFull:
            self.log.error("Event bus queue full! Dropping event {}", event.type.value)
            self._dead_letters.append((event, "queue_full"))

    async def start(self) -> None:
        self._running = True
        self._task = asyncio.create_task(self._dispatch_loop())
        self.log.info("Event bus started")

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        self.log.info("Event bus stopped. Processed={}, Failed={}",
                      self._metrics["events_processed"], self._metrics["events_failed"])

    async def _dispatch_loop(self) -> None:
        while self._running:
            try:
                priority, ts, event = await asyncio.wait_for(self._queue.get(), timeout=1.0)
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break

            handlers = self._subscribers.get(event.type, [])
            if not handlers:
                continue

            start = asyncio.get_event_loop().time()

            for subscriber_name, handler, _ in handlers:
                try:
                    await asyncio.wait_for(handler(event), timeout=self._handler_timeout)
                except asyncio.TimeoutError:
                    self.log.warning("Handler {} timed out for {}", subscriber_name, event.type.value)
                    self._metrics["events_failed"] += 1
                except Exception as exc:
                    self.log.error("Handler {} failed for {}: {}", subscriber_name, event.type.value, exc)
                    self._dead_letters.append((event, f"{subscriber_name}: {exc}"))
                    self._metrics["events_failed"] += 1

                # Stop pipeline if emergency
                if event.type == EventType.EMERGENCY_SHUTDOWN:
                    break

            elapsed_ms = (asyncio.get_event_loop().time() - start) * 1000
            self._metrics["events_processed"] += 1
            self._latency_sum += elapsed_ms
            self._metrics["avg_latency_ms"] = self._latency_sum / self._metrics["events_processed"]

    def get_metrics(self) -> dict[str, Any]:
        return {
            **self._metrics,
            "queue_size": self._queue.qsize(),
            "dead_letters": len(self._dead_letters),
            "subscribers": {et.value: len(hs) for et, hs in self._subscribers.items() if hs},
        }

    def get_dead_letters(self, limit: int = 50) -> list[tuple[Event, str]]:
        return self._dead_letters[-limit:]
