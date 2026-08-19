"""Periodic health checks for all system components."""
from __future__ import annotations

import asyncio
import platform
import shutil
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Awaitable, Callable

from ..utils.logger import get_logger

log = get_logger("monitoring.health")


@dataclass
class CheckResult:
    healthy: bool
    latency_ms: float
    last_check: str
    message: str


@dataclass
class RegisteredCheck:
    name: str
    check_fn: Callable[[], Awaitable[bool]]
    critical: bool = True


class HealthCheck:
    """Periodic health check for all system components."""

    def __init__(self, check_interval: float = 30.0) -> None:
        self._checks: list[RegisteredCheck] = []
        self._results: dict[str, CheckResult] = {}
        self._interval = check_interval
        self._running = False
        self._task: asyncio.Task | None = None

    def register_check(
        self,
        name: str,
        check_fn: Callable[[], Awaitable[bool]],
        critical: bool = True,
    ) -> None:
        """Register a health check function."""
        self._checks.append(RegisteredCheck(name=name, check_fn=check_fn, critical=critical))

    async def run_all(self) -> dict[str, dict]:
        """Run all registered checks and return results."""
        results: dict[str, dict] = {}
        for check in self._checks:
            start = time.perf_counter()
            try:
                healthy = await asyncio.wait_for(check.check_fn(), timeout=10.0)
                msg = "OK"
            except asyncio.TimeoutError:
                healthy = False
                msg = "Timeout (>10s)"
            except Exception as exc:
                healthy = False
                msg = str(exc)[:200]

            latency_ms = (time.perf_counter() - start) * 1000
            result = CheckResult(
                healthy=healthy,
                latency_ms=round(latency_ms, 2),
                last_check=datetime.now().isoformat(timespec="seconds"),
                message=msg,
            )
            self._results[check.name] = result
            results[check.name] = {
                "healthy": result.healthy,
                "latency_ms": result.latency_ms,
                "last_check": result.last_check,
                "message": result.message,
            }
        return results

    async def start_periodic(self) -> None:
        """Start background periodic health checks."""
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._loop())
        log.info("Health check loop started (interval={}s)", self._interval)

    async def stop(self) -> None:
        """Stop the background health check loop."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

    async def _loop(self) -> None:
        while self._running:
            try:
                await self.run_all()
            except Exception as exc:
                log.error("Health check loop error: {}", exc)
            await asyncio.sleep(self._interval)

    def get_status_page(self) -> str:
        """Return formatted status page string for Telegram/logs."""
        if not self._results:
            return "⚠️ Проверки ещё не запускались"

        lines = ["📊 СТАТУС СИСТЕМЫ", "─" * 30]
        all_healthy = True
        for check in self._checks:
            r = self._results.get(check.name)
            if r is None:
                lines.append(f"⏳ {check.name}: не проверен")
                continue
            icon = "✅" if r.healthy else ("🔴" if check.critical else "🟡")
            if not r.healthy:
                all_healthy = False
            lines.append(f"{icon} {check.name}: {r.message} ({r.latency_ms:.0f}ms)")

        lines.append("─" * 30)
        overall = "✅ Всё работает" if all_healthy else "⚠️ Есть проблемы"
        lines.append(overall)
        if self._results:
            last = max(r.last_check for r in self._results.values())
            lines.append(f"Последняя проверка: {last}")
        return "\n".join(lines)


# --- Built-in check factories ---

async def check_disk_space(min_gb: float = 1.0) -> bool:
    """Check that free disk space > min_gb."""
    if platform.system() == "Windows":
        usage = shutil.disk_usage("C:\\")
    else:
        usage = shutil.disk_usage("/")
    free_gb = usage.free / (1024**3)
    return free_gb > min_gb


async def check_memory_usage(max_pct: float = 80.0) -> bool:
    """Check that memory usage < max_pct%. Returns True if psutil unavailable."""
    try:
        import psutil
        return psutil.virtual_memory().percent < max_pct
    except ImportError:
        return True


async def check_ollama_reachable() -> bool:
    """Check that Ollama API responds."""
    try:
        import httpx
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.get("http://localhost:11434/api/tags")
            return r.status_code == 200
    except Exception:
        return False
