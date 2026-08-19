"""
SRE & QA Agent (System Engineer).

Monitors infrastructure health: QUIK connection, memory usage,
latency, agent status. Sends telemetry to Telegram and can
recommend restarts or hotfixes.
"""

from __future__ import annotations

import asyncio
import os
import time
from datetime import datetime
from typing import Any

from loguru import logger

from .base_agent import BaseAgent, AgentSignal, AgentRole, Action
from ..core.config_loader import get_agent_params


class SREAgent(BaseAgent):
    """
    Automated System Reliability Engineer.
    
    Monitors:
    - QUIK connection health and latency
    - Memory usage and potential leaks
    - Agent responsiveness (heartbeat)
    - Event bus queue backpressure
    - Error rate tracking
    - Uptime and stability metrics
    
    Actions:
    - Sends alerts to Telegram on anomalies
    - Can trigger agent restarts
    - Logs detailed telemetry for debugging
    """

    def __init__(self, config: dict, data_feed: Any = None, order_manager: Any = None, db: Any = None):
        sre_cfg = get_agent_params(config, "sre")

        super().__init__("sre", AgentRole.RISK, config, data_feed, order_manager, db,
                         loop_interval=sre_cfg.get("loop_interval", 15.0))

        self.quik_connector: Any = None
        self.event_bus: Any = None
        self.telegram_reporter: Any = None
        self.agents_registry: dict[str, BaseAgent] = {}

        self.start_time = time.time()
        self.error_log: list[dict] = []
        self.latency_history: list[float] = []
        self.memory_history: list[float] = []
        self.health_history: list[dict] = []

        self.max_memory_mb = sre_cfg.get("max_memory_mb", 2048)
        self.max_latency_ms = sre_cfg.get("max_latency_ms", 500)
        self.max_errors_per_hour = sre_cfg.get("max_errors_per_hour", 50)
        self.alert_cooldown_sec = sre_cfg.get("alert_cooldown_sec", 300)
        self._last_alert_time: float = 0

    def register_connector(self, connector: Any) -> None:
        self.quik_connector = connector

    def register_event_bus(self, bus: Any) -> None:
        self.event_bus = bus

    def register_telegram(self, reporter: Any) -> None:
        self.telegram_reporter = reporter

    def register_agents(self, agents: dict[str, BaseAgent]) -> None:
        self.agents_registry = agents

    async def analyze(self) -> list[AgentSignal]:
        health = await self._collect_health()
        self.health_history.append(health)
        if len(self.health_history) > 1000:
            self.health_history = self.health_history[-500:]

        alerts: list[str] = []

        # Check QUIK connection
        if not health.get("quik_connected", False):
            alerts.append("QUIK disconnected!")

        # Check latency
        latency = health.get("quik_latency_ms", 0)
        if latency > self.max_latency_ms:
            alerts.append(f"High QUIK latency: {latency:.0f}ms (max {self.max_latency_ms}ms)")

        # Check memory
        memory_mb = health.get("memory_mb", 0)
        self.memory_history.append(memory_mb)
        if len(self.memory_history) > 100:
            self.memory_history = self.memory_history[-100:]
        if memory_mb > self.max_memory_mb:
            alerts.append(f"High memory usage: {memory_mb:.0f}MB (max {self.max_memory_mb}MB)")

        # Detect memory leak (linear growth over 50+ samples)
        if len(self.memory_history) >= 50:
            first_half = sum(self.memory_history[:25]) / 25
            second_half = sum(self.memory_history[-25:]) / 25
            growth_pct = (second_half - first_half) / max(first_half, 1) * 100
            if growth_pct > 20:
                alerts.append(f"Potential memory leak: +{growth_pct:.0f}% over monitoring window")

        # Check event bus
        bus_queue = health.get("event_bus_queue", 0)
        if bus_queue > 5000:
            alerts.append(f"Event bus backpressure: {bus_queue} events queued")

        # Check agent health
        dead_agents = health.get("dead_agents", [])
        if dead_agents:
            alerts.append(f"Dead agents: {', '.join(dead_agents)}")

        # Check error rate
        recent_errors = len([
            e for e in self.error_log
            if time.time() - e.get("time", 0) < 3600
        ])
        if recent_errors > self.max_errors_per_hour:
            alerts.append(f"High error rate: {recent_errors}/hour (max {self.max_errors_per_hour})")

        # Send alerts
        if alerts:
            await self._send_alert(alerts, health)

        # Log telemetry
        self.log.info(
            "Health: QUIK={} lat={:.0f}ms mem={:.0f}MB bus_q={} agents={}/{} errors/h={}",
            "OK" if health.get("quik_connected") else "DOWN",
            health.get("quik_latency_ms", 0),
            memory_mb,
            bus_queue,
            health.get("agents_running", 0),
            health.get("agents_total", 0),
            recent_errors,
        )

        return []  # SRE agent doesn't generate trading signals

    async def _collect_health(self) -> dict:
        health: dict[str, Any] = {
            "timestamp": datetime.now().isoformat(),
            "uptime_sec": time.time() - self.start_time,
        }

        # QUIK connection
        if self.quik_connector:
            try:
                connected = getattr(self.quik_connector, "_connected", False)
                health["quik_connected"] = connected
                # Measure latency with ping
                if connected and hasattr(self.quik_connector, "request"):
                    t0 = time.monotonic()
                    await asyncio.wait_for(self.quik_connector.request("get_info"), timeout=2.0)
                    health["quik_latency_ms"] = (time.monotonic() - t0) * 1000
                else:
                    health["quik_latency_ms"] = 0
            except Exception:
                health["quik_connected"] = False
                health["quik_latency_ms"] = 0
        else:
            health["quik_connected"] = False
            health["quik_latency_ms"] = 0

        # Memory usage
        try:
            import psutil
            proc = psutil.Process(os.getpid())
            mem = proc.memory_info()
            health["memory_mb"] = mem.rss / 1024 / 1024
            health["cpu_pct"] = proc.cpu_percent(interval=0.1)
        except ImportError:
            health["memory_mb"] = 0
            health["cpu_pct"] = 0

        # Event bus
        if self.event_bus and hasattr(self.event_bus, "get_metrics"):
            metrics = self.event_bus.get_metrics()
            health["event_bus_queue"] = metrics.get("queue_size", 0)
            health["event_bus_latency_ms"] = metrics.get("avg_latency_ms", 0)
            health["events_processed"] = metrics.get("events_processed", 0)
            health["events_failed"] = metrics.get("events_failed", 0)
        else:
            health["event_bus_queue"] = 0

        # Agent health
        running = 0
        dead_agents = []
        for name, agent in self.agents_registry.items():
            if agent._running:
                running += 1
            else:
                dead_agents.append(name)
        health["agents_running"] = running
        health["agents_total"] = len(self.agents_registry)
        health["dead_agents"] = dead_agents

        return health

    async def _send_alert(self, alerts: list[str], health: dict) -> None:
        now = time.time()
        if now - self._last_alert_time < self.alert_cooldown_sec:
            return
        self._last_alert_time = now

        text = "⚠️ *SRE Alert*\n\n"
        for a in alerts:
            text += f"• {a}\n"
        text += f"\n📊 Uptime: {health.get('uptime_sec', 0)/3600:.1f}h"
        text += f"\n💾 Memory: {health.get('memory_mb', 0):.0f}MB"
        text += f"\n🔌 QUIK: {'Connected' if health.get('quik_connected') else 'Disconnected'}"

        self.log.warning("SRE Alert: {}", "; ".join(alerts))

        if self.telegram_reporter and hasattr(self.telegram_reporter, "send_message"):
            try:
                await self.telegram_reporter.send_message(text)
            except Exception as e:
                self.log.error(f"Failed to send Telegram alert: {e}")

    def record_error(self, error: str, source: str = "") -> None:
        self.error_log.append({"time": time.time(), "error": error, "source": source})
        if len(self.error_log) > 5000:
            self.error_log = self.error_log[-3000:]

    async def get_full_report(self) -> dict:
        health = await self._collect_health()
        return {
            **health,
            "error_count_total": len(self.error_log),
            "memory_trend": self.memory_history[-10:] if self.memory_history else [],
            "latency_trend": self.latency_history[-10:] if self.latency_history else [],
        }

    async def get_status(self) -> dict:
        return {
            "name": self.name,
            "running": self._running,
            "uptime_hours": (time.time() - self.start_time) / 3600,
            "errors_tracked": len(self.error_log),
            "health_checks": len(self.health_history),
        }
