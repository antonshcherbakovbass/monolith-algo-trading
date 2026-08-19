import asyncio

import pytest

from hedge_fund.core.event_bus import Event, EventBus, EventType


@pytest.mark.asyncio
async def test_publish_subscribe():
    bus = EventBus()
    received = []

    async def handler(event: Event):
        received.append(event)

    bus.subscribe(EventType.QUOTE_UPDATE, handler, "test")
    await bus.start()
    await bus.publish(Event(type=EventType.QUOTE_UPDATE, payload={"ticker": "SBER"}))
    await asyncio.sleep(0.1)
    await bus.stop()
    assert len(received) == 1
    assert received[0].payload["ticker"] == "SBER"


@pytest.mark.asyncio
async def test_priority_ordering():
    bus = EventBus()
    order = []

    async def handler_low(event: Event):
        order.append("low")

    async def handler_high(event: Event):
        order.append("high")

    bus.subscribe(EventType.QUOTE_UPDATE, handler_low, "low", priority=10)
    bus.subscribe(EventType.QUOTE_UPDATE, handler_high, "high", priority=1)
    await bus.start()
    await bus.publish(Event(type=EventType.QUOTE_UPDATE, payload={}))
    await asyncio.sleep(0.1)
    await bus.stop()
    assert order == ["high", "low"]


@pytest.mark.asyncio
async def test_unsubscribe():
    bus = EventBus()
    received = []

    async def handler(event: Event):
        received.append(event)

    bus.subscribe(EventType.QUOTE_UPDATE, handler, "test")
    bus.unsubscribe(EventType.QUOTE_UPDATE, "test")
    await bus.start()
    await bus.publish(Event(type=EventType.QUOTE_UPDATE, payload={}))
    await asyncio.sleep(0.1)
    await bus.stop()
    assert len(received) == 0


@pytest.mark.asyncio
async def test_multiple_subscribers():
    bus = EventBus()
    counts = {"a": 0, "b": 0}

    async def handler_a(event: Event):
        counts["a"] += 1

    async def handler_b(event: Event):
        counts["b"] += 1

    bus.subscribe(EventType.ALPHA_SIGNAL, handler_a, "a")
    bus.subscribe(EventType.ALPHA_SIGNAL, handler_b, "b")
    await bus.start()
    await bus.publish(Event(type=EventType.ALPHA_SIGNAL, payload={}))
    await asyncio.sleep(0.1)
    await bus.stop()
    assert counts["a"] == 1
    assert counts["b"] == 1


@pytest.mark.asyncio
async def test_metrics_updated():
    bus = EventBus()

    async def handler(event: Event):
        pass

    bus.subscribe(EventType.QUOTE_UPDATE, handler, "m")
    await bus.start()
    await bus.publish(Event(type=EventType.QUOTE_UPDATE, payload={}))
    await asyncio.sleep(0.1)
    await bus.stop()
    metrics = bus.get_metrics()
    assert metrics["events_published"] == 1
    assert metrics["events_processed"] == 1


@pytest.mark.asyncio
async def test_handler_timeout_recorded():
    bus = EventBus(handler_timeout=0.05)

    async def slow_handler(event: Event):
        await asyncio.sleep(1.0)

    bus.subscribe(EventType.QUOTE_UPDATE, slow_handler, "slow")
    await bus.start()
    await bus.publish(Event(type=EventType.QUOTE_UPDATE, payload={}))
    await asyncio.sleep(0.2)
    await bus.stop()
    assert bus.get_metrics()["events_failed"] >= 1
