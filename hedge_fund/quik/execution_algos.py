"""
Execution Algorithms: TWAP, VWAP, Iceberg.

Splits large orders into smaller chunks to minimize market impact.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Protocol
from loguru import logger


class OrderSender(Protocol):
    async def send_order(self, ticker: str, side: str, qty: int, price: float,
                         order_type: str = "limit") -> str: ...
    async def cancel_order(self, order_id: str) -> bool: ...


@dataclass
class ExecutionSlice:
    slice_id: int
    qty: int
    target_time: datetime
    executed_qty: int = 0
    executed_price: float = 0.0
    order_id: str = ""
    status: str = "pending"  # pending, sent, filled, cancelled


@dataclass
class ExecutionReport:
    algo: str
    ticker: str
    side: str
    total_qty: int
    filled_qty: int = 0
    avg_price: float = 0.0
    vwap: float = 0.0
    slices_total: int = 0
    slices_filled: int = 0
    start_time: datetime = field(default_factory=datetime.now)
    end_time: datetime | None = None
    market_impact_bps: float = 0.0

    @property
    def fill_rate(self) -> float:
        return self.filled_qty / max(self.total_qty, 1) * 100


class TWAPExecutor:
    """
    Time-Weighted Average Price execution.
    Splits order evenly over a time window.
    """

    def __init__(self, order_sender: OrderSender):
        self.sender = order_sender
        self.log = logger.bind(algo="TWAP")

    async def execute(
        self,
        ticker: str,
        side: str,
        total_qty: int,
        duration_minutes: int = 30,
        num_slices: int = 10,
        price_limit: float = 0.0,
    ) -> ExecutionReport:
        report = ExecutionReport(
            algo="TWAP", ticker=ticker, side=side, total_qty=total_qty,
            slices_total=num_slices,
        )
        slice_qty = total_qty // num_slices
        remainder = total_qty % num_slices
        interval = duration_minutes * 60 / num_slices

        total_cost = 0.0
        total_filled = 0

        for i in range(num_slices):
            qty = slice_qty + (1 if i < remainder else 0)
            if qty <= 0:
                continue

            try:
                order_type = "limit" if price_limit > 0 else "market"
                order_id = await self.sender.send_order(
                    ticker, side, qty, price_limit, order_type
                )
                # Assume immediate fill for simplicity; real impl would track
                total_filled += qty
                total_cost += qty * price_limit if price_limit > 0 else 0
                report.slices_filled += 1
                self.log.debug(f"TWAP slice {i+1}/{num_slices}: {qty} @ {price_limit}")
            except Exception as e:
                self.log.warning(f"TWAP slice {i+1} failed: {e}")

            if i < num_slices - 1:
                await asyncio.sleep(interval)

        report.filled_qty = total_filled
        report.avg_price = total_cost / max(total_filled, 1)
        report.end_time = datetime.now()
        return report


class VWAPExecutor:
    """
    Volume-Weighted Average Price execution.
    Distributes order according to historical volume profile.
    """

    # Typical MOEX intraday volume distribution (hourly buckets 10:00-18:00)
    MOEX_VOLUME_PROFILE = [
        0.15,  # 10:00-11:00 (high opening activity)
        0.12,  # 11:00-12:00
        0.10,  # 12:00-13:00
        0.08,  # 13:00-14:00 (lunch lull)
        0.08,  # 14:00-15:00
        0.10,  # 15:00-16:00
        0.12,  # 16:00-17:00 (US market overlap)
        0.13,  # 17:00-18:00
        0.12,  # 18:00-18:45 (closing auction ramp)
    ]

    def __init__(self, order_sender: OrderSender):
        self.sender = order_sender
        self.log = logger.bind(algo="VWAP")

    async def execute(
        self,
        ticker: str,
        side: str,
        total_qty: int,
        price_limit: float = 0.0,
        participation_rate: float = 0.1,
    ) -> ExecutionReport:
        report = ExecutionReport(
            algo="VWAP", ticker=ticker, side=side, total_qty=total_qty,
        )

        # Distribute qty according to volume profile
        profile = self.MOEX_VOLUME_PROFILE
        slices: list[int] = []
        for pct in profile:
            slices.append(max(1, int(total_qty * pct)))

        # Adjust to exact total
        diff = total_qty - sum(slices)
        if diff > 0:
            slices[0] += diff
        elif diff < 0:
            for i in range(len(slices)):
                reduce = min(slices[i] - 1, -diff)
                slices[i] -= reduce
                diff += reduce
                if diff >= 0:
                    break

        report.slices_total = len(slices)
        total_filled = 0
        interval = 3600 / max(len(slices), 1)  # space across the day

        for i, qty in enumerate(slices):
            if qty <= 0:
                continue
            try:
                order_type = "limit" if price_limit > 0 else "market"
                await self.sender.send_order(ticker, side, qty, price_limit, order_type)
                total_filled += qty
                report.slices_filled += 1
                self.log.debug(f"VWAP slice {i+1}/{len(slices)}: {qty} (vol_pct={profile[i]:.0%})")
            except Exception as e:
                self.log.warning(f"VWAP slice {i+1} failed: {e}")

            if i < len(slices) - 1:
                await asyncio.sleep(min(interval, 300))

        report.filled_qty = total_filled
        report.end_time = datetime.now()
        return report


class IcebergExecutor:
    """
    Iceberg order execution.
    Shows only a small visible portion, refills automatically.
    """

    def __init__(self, order_sender: OrderSender):
        self.sender = order_sender
        self.log = logger.bind(algo="Iceberg")

    async def execute(
        self,
        ticker: str,
        side: str,
        total_qty: int,
        visible_qty: int = 0,
        price: float = 0.0,
        refresh_interval_sec: float = 2.0,
    ) -> ExecutionReport:
        if visible_qty <= 0:
            visible_qty = max(1, total_qty // 20)

        report = ExecutionReport(
            algo="Iceberg", ticker=ticker, side=side, total_qty=total_qty,
        )

        remaining = total_qty
        total_filled = 0
        slice_count = 0

        while remaining > 0:
            show_qty = min(visible_qty, remaining)
            slice_count += 1

            try:
                order_id = await self.sender.send_order(
                    ticker, side, show_qty, price, "limit" if price > 0 else "market"
                )
                total_filled += show_qty
                remaining -= show_qty
                self.log.debug(f"Iceberg slice {slice_count}: {show_qty} (remaining={remaining})")
            except Exception as e:
                self.log.warning(f"Iceberg slice failed: {e}")
                break

            if remaining > 0:
                await asyncio.sleep(refresh_interval_sec)

        report.filled_qty = total_filled
        report.slices_total = slice_count
        report.slices_filled = slice_count
        report.end_time = datetime.now()
        return report


class SmartRouter:
    """
    Smart order router that picks the best execution algorithm
    based on order size, urgency, and market conditions.
    """

    def __init__(self, order_sender: OrderSender):
        self.twap = TWAPExecutor(order_sender)
        self.vwap = VWAPExecutor(order_sender)
        self.iceberg = IcebergExecutor(order_sender)
        self.log = logger.bind(component="smart_router")

    async def execute(
        self,
        ticker: str,
        side: str,
        qty: int,
        price: float = 0.0,
        urgency: float = 0.5,
        avg_daily_volume: int = 0,
    ) -> ExecutionReport:
        # Small orders: just send directly
        if qty <= 10:
            report = ExecutionReport(
                algo="direct", ticker=ticker, side=side, total_qty=qty,
            )
            try:
                await self.twap.sender.send_order(ticker, side, qty, price, "limit" if price > 0 else "market")
                report.filled_qty = qty
                report.slices_total = 1
                report.slices_filled = 1
            except Exception as e:
                self.log.warning(f"Direct order failed: {e}")
            report.end_time = datetime.now()
            return report

        # Large relative to ADV: use iceberg
        if avg_daily_volume > 0 and qty > avg_daily_volume * 0.05:
            self.log.info(f"Large order ({qty} vs ADV {avg_daily_volume}), using Iceberg")
            return await self.iceberg.execute(ticker, side, qty, price=price)

        # High urgency: TWAP over short window
        if urgency > 0.7:
            self.log.info(f"Urgent order, using TWAP (10min)")
            return await self.twap.execute(ticker, side, qty, duration_minutes=10, num_slices=5, price_limit=price)

        # Default: VWAP
        self.log.info(f"Standard order, using VWAP")
        return await self.vwap.execute(ticker, side, qty, price_limit=price)
