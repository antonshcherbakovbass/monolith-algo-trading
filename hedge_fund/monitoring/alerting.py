"""Alert management with deduplication and cooldown."""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from ..utils.logger import get_logger

log = get_logger("monitoring.alerting")


class Severity(str, Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


@dataclass
class Alert:
    name: str
    severity: Severity
    message: str
    fired_at: float
    resolved: bool = False


class AlertManager:
    """Manages alerts with deduplication and cooldown."""

    def __init__(self, cooldown_seconds: float = 300.0) -> None:
        self._cooldown = cooldown_seconds
        self._last_fired: dict[str, float] = {}
        self._suppressed: dict[str, float] = {}  # name -> suppress_until timestamp
        self._active: dict[str, Alert] = {}
        self._history: list[Alert] = []
        self._telegram_callback: Any = None
        self._curator_callback: Any = None

    def set_telegram_callback(self, fn: Any) -> None:
        """Set async callback for Telegram notifications: fn(message: str)."""
        self._telegram_callback = fn

    def set_curator_callback(self, fn: Any) -> None:
        """Set async callback for curator notifications: fn(message: str)."""
        self._curator_callback = fn

    async def fire(
        self,
        name: str,
        severity: Severity,
        message: str,
        notify_telegram: bool = True,
        notify_curator: bool = False,
    ) -> None:
        """Fire an alert with deduplication and cooldown."""
        now = time.time()

        # Check suppression
        if name in self._suppressed and now < self._suppressed[name]:
            return

        # Check cooldown
        if name in self._last_fired:
            elapsed = now - self._last_fired[name]
            if elapsed < self._cooldown:
                return

        alert = Alert(name=name, severity=severity, message=message, fired_at=now)
        self._active[name] = alert
        self._history.append(alert)
        if len(self._history) > 1000:
            self._history = self._history[-500:]
        self._last_fired[name] = now

        icon = {"INFO": "ℹ️", "WARNING": "⚠️", "CRITICAL": "🚨"}[severity.value]
        formatted = f"{icon} [{severity.value}] {name}\n{message}"
        log.warning("Alert fired: {} - {}", name, message)

        if notify_telegram and self._telegram_callback:
            try:
                await self._telegram_callback(formatted)
            except Exception as exc:
                log.error("Failed to send Telegram alert: {}", exc)

        if notify_curator and self._curator_callback:
            try:
                await self._curator_callback(formatted)
            except Exception as exc:
                log.error("Failed to send curator alert: {}", exc)

    def suppress(self, name: str, duration: float) -> None:
        """Suppress an alert for N seconds."""
        self._suppressed[name] = time.time() + duration
        self._active.pop(name, None)

    def get_active_alerts(self) -> list[dict]:
        """Return currently active (unresolved) alerts."""
        return [
            {
                "name": a.name,
                "severity": a.severity.value,
                "message": a.message,
                "fired_at": a.fired_at,
            }
            for a in self._active.values()
        ]

    def get_alert_history(self, limit: int = 100) -> list[dict]:
        """Return recent alert history."""
        return [
            {
                "name": a.name,
                "severity": a.severity.value,
                "message": a.message,
                "fired_at": a.fired_at,
            }
            for a in self._history[-limit:]
        ]
