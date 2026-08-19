"""Performance and stress tests."""
from __future__ import annotations

import asyncio
import time
import tracemalloc

import numpy as np
import pandas as pd
import pytest

from hedge_fund.risk.commission import CommissionCalculator, CommissionConfig
from hedge_fund.core.event_bus import EventBus, EventType, Event
from hedge_fund.data.feature_engineer import FeatureEngineer
from hedge_fund.risk.position_sizer import PositionSizer, PositionSizerConfig


class TestPerformance:
    def test_commission_calc_speed(self):
        """1000 commission calcs < 10ms."""
        calc = CommissionCalculator(CommissionConfig())
        start = time.perf_counter()
        for _ in range(1000):
            calc.calculate(ticker="SBER", side="BUY", qty=10, price=250.0)
        elapsed_ms = (time.perf_counter() - start) * 1000
        assert elapsed_ms < 10, f"Commission calc took {elapsed_ms:.1f}ms for 1000 ops"

    def test_event_bus_throughput(self):
        """10000 events published/consumed < 1s."""
        bus = EventBus()
        received = []

        async def handler(event: Event):
            received.append(event)

        async def run():
            bus.subscribe(EventType.QUOTE_UPDATE, handler, subscriber_name="test")
            await bus.start()
            start = time.perf_counter()
            for i in range(10000):
                await bus.publish(Event(
                    type=EventType.QUOTE_UPDATE,
                    payload={"price": 100.0 + i * 0.01},
                ))
            # Wait for queue to drain
            while not bus._queue.empty():
                await asyncio.sleep(0.01)
            await asyncio.sleep(0.1)
            await bus.stop()
            elapsed = time.perf_counter() - start
            assert elapsed < 1.0, f"Event bus took {elapsed:.2f}s for 10000 events"
            assert len(received) == 10000

        asyncio.run(run())

    def test_feature_engineering_speed(self):
        """Feature engineering on 5000 rows < 2s."""
        np.random.seed(42)
        n = 5000
        df = pd.DataFrame({
            "datetime": pd.date_range("2024-01-01", periods=n, freq="1min"),
            "open": np.random.uniform(90, 110, n),
            "high": np.random.uniform(100, 120, n),
            "low": np.random.uniform(80, 100, n),
            "close": np.random.uniform(90, 110, n),
            "volume": np.random.randint(1000, 100000, n),
        })
        fe = FeatureEngineer()
        start = time.perf_counter()
        result = fe.create_features(df)
        elapsed = time.perf_counter() - start
        assert elapsed < 2.0, f"Feature engineering took {elapsed:.2f}s"
        assert len(result) == n

    @pytest.mark.asyncio
    async def test_concurrent_agents(self):
        """5 agents running concurrently without deadlock for 5s."""
        bus = EventBus()
        counters = {f"agent_{i}": 0 for i in range(5)}

        async def agent_loop(name: str):
            while True:
                await bus.publish(Event(
                    type=EventType.ALPHA_SIGNAL,
                    payload={"agent": name},
                ))
                counters[name] += 1
                await asyncio.sleep(0.01)

        tasks = [asyncio.create_task(agent_loop(f"agent_{i}")) for i in range(5)]
        await asyncio.sleep(5.0)
        for t in tasks:
            t.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)

        for name, count in counters.items():
            assert count > 50, f"{name} only ran {count} iterations in 5s"

    def test_risk_check_latency(self):
        """Single risk check < 1ms."""
        sizer = PositionSizer(PositionSizerConfig())
        start = time.perf_counter()
        sizer.calculate(
            ticker="SBER",
            portfolio_value=1_000_000.0,
            signal_confidence=0.8,
            volatility=0.02,
            price=250.0,
        )
        elapsed_ms = (time.perf_counter() - start) * 1000
        assert elapsed_ms < 1.0, f"Risk check took {elapsed_ms:.3f}ms"

    def test_position_sizer_batch(self):
        """Size 50 positions < 50ms."""
        sizer = PositionSizer(PositionSizerConfig())
        start = time.perf_counter()
        for i in range(50):
            price = 100.0 + i * 5
            sizer.calculate(
                ticker=f"TICK{i}",
                portfolio_value=1_000_000.0,
                signal_confidence=0.7,
                volatility=0.015,
                price=price,
            )
        elapsed_ms = (time.perf_counter() - start) * 1000
        assert elapsed_ms < 50, f"Batch sizing took {elapsed_ms:.1f}ms for 50 positions"

    def test_memory_under_load(self):
        """System doesn't leak memory after 10000 operations."""
        tracemalloc.start()
        bus = EventBus()
        received = []

        async def handler(event: Event):
            received.append(1)

        async def run():
            bus.subscribe(EventType.QUOTE_UPDATE, handler, subscriber_name="mem_test")
            await bus.start()
            for i in range(10000):
                await bus.publish(Event(
                    type=EventType.QUOTE_UPDATE,
                    payload={"price": float(i)},
                ))
            while not bus._queue.empty():
                await asyncio.sleep(0.01)
            await asyncio.sleep(0.1)
            await bus.stop()
            received.clear()

        asyncio.run(run())

        _, peak_kb = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        peak_mb = peak_kb / (1024 * 1024)
        assert peak_mb < 100, f"Peak memory {peak_mb:.1f}MB exceeds 100MB limit"
