from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, time, timedelta
from typing import Any, Awaitable, Callable
from zoneinfo import ZoneInfo

from hedge_fund.utils.logger import get_logger

log = get_logger("scheduler")

MSK = ZoneInfo("Europe/Moscow")

MAIN_SESSION_START = time(10, 0)
MAIN_SESSION_END = time(18, 45)
EVENING_SESSION_START = time(19, 5)
EVENING_SESSION_END = time(23, 50)

MOEX_HOLIDAYS_2024 = {
    datetime(2024, 1, 1).date(),
    datetime(2024, 1, 2).date(),
    datetime(2024, 1, 3).date(),
    datetime(2024, 1, 4).date(),
    datetime(2024, 1, 5).date(),
    datetime(2024, 1, 8).date(),
    datetime(2024, 2, 23).date(),
    datetime(2024, 3, 8).date(),
    datetime(2024, 5, 1).date(),
    datetime(2024, 5, 9).date(),
    datetime(2024, 6, 12).date(),
    datetime(2024, 11, 4).date(),
    datetime(2024, 12, 31).date(),
}


def _is_moex_trading_day(dt: datetime) -> bool:
    d = dt.date()
    if d.weekday() >= 5:
        return False
    return d not in MOEX_HOLIDAYS_2024


def is_main_session(dt: datetime | None = None) -> bool:
    """Return *True* when *dt* falls inside the MOEX main trading session."""
    dt = dt or datetime.now(MSK)
    if not _is_moex_trading_day(dt):
        return False
    t = dt.timetz()
    return MAIN_SESSION_START <= t <= MAIN_SESSION_END


def is_evening_session(dt: datetime | None = None) -> bool:
    """Return *True* when *dt* falls inside the MOEX evening session."""
    dt = dt or datetime.now(MSK)
    if not _is_moex_trading_day(dt):
        return False
    t = dt.timetz()
    return EVENING_SESSION_START <= t <= EVENING_SESSION_END


def is_trading_hours(dt: datetime | None = None) -> bool:
    """Return *True* during any MOEX trading session."""
    dt = dt or datetime.now(MSK)
    return is_main_session(dt) or is_evening_session(dt)


@dataclass
class ScheduledTask:
    name: str
    callback: Callable[[], Awaitable[Any]]
    interval_seconds: float
    trading_hours_only: bool = False
    session: str = "any"  # "main", "evening", "any"
    _handle: asyncio.Task[None] | None = field(default=None, repr=False)


class AsyncScheduler:
    """Lightweight async scheduler that respects MOEX trading hours."""

    def __init__(self) -> None:
        self._tasks: dict[str, ScheduledTask] = {}
        self._running = False

    def add_task(
        self,
        name: str,
        callback: Callable[[], Awaitable[Any]],
        interval_seconds: float,
        *,
        trading_hours_only: bool = False,
        session: str = "any",
    ) -> None:
        if name in self._tasks:
            raise ValueError(f"Task '{name}' already registered")
        task = ScheduledTask(
            name=name,
            callback=callback,
            interval_seconds=interval_seconds,
            trading_hours_only=trading_hours_only,
            session=session,
        )
        self._tasks[name] = task
        if self._running:
            task._handle = asyncio.create_task(self._run_loop(task))
        log.info("Task '{}' added (interval={}s, trading_only={}, session={})",
                 name, interval_seconds, trading_hours_only, session)

    def remove_task(self, name: str) -> None:
        task = self._tasks.pop(name, None)
        if task is None:
            log.warning("Task '{}' not found for removal", name)
            return
        if task._handle and not task._handle.done():
            task._handle.cancel()
        log.info("Task '{}' removed", name)

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        for task in self._tasks.values():
            task._handle = asyncio.create_task(self._run_loop(task))
        log.info("Scheduler started with {} task(s)", len(self._tasks))

    async def stop(self) -> None:
        self._running = False
        for task in self._tasks.values():
            if task._handle and not task._handle.done():
                task._handle.cancel()
        pending = [t._handle for t in self._tasks.values() if t._handle and not t._handle.done()]
        if pending:
            await asyncio.gather(*pending, return_exceptions=True)
        log.info("Scheduler stopped")

    def _should_run(self, task: ScheduledTask) -> bool:
        if not task.trading_hours_only:
            return True
        now = datetime.now(MSK)
        if task.session == "main":
            return is_main_session(now)
        if task.session == "evening":
            return is_evening_session(now)
        return is_trading_hours(now)

    async def _run_loop(self, task: ScheduledTask) -> None:
        while self._running:
            try:
                await asyncio.sleep(task.interval_seconds)
                if not self._should_run(task):
                    continue
                await task.callback()
            except asyncio.CancelledError:
                break
            except Exception:
                log.exception("Error in scheduled task '{}'", task.name)

    async def _seconds_until_next_session(self) -> float:
        """Calculate seconds until the next MOEX trading session opens."""
        now = datetime.now(MSK)
        candidate = now
        for _ in range(10):
            if _is_moex_trading_day(candidate):
                main_open = datetime.combine(candidate.date(), MAIN_SESSION_START, tzinfo=MSK)
                if main_open > now:
                    return (main_open - now).total_seconds()
                evening_open = datetime.combine(candidate.date(), EVENING_SESSION_START, tzinfo=MSK)
                if evening_open > now:
                    return (evening_open - now).total_seconds()
            candidate = datetime.combine(
                candidate.date() + timedelta(days=1), time(0, 0), tzinfo=MSK
            )
        return 3600.0
