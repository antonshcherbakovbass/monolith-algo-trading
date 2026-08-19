"""Manages system behaviour when components fail.

Tracks per-component health, decides whether trading is allowed, and
produces a human-readable degradation report (Russian-language, matching
the MOEX trading context).
"""

from __future__ import annotations

import enum
import time
from dataclasses import dataclass, field
from typing import Any

from ..utils.logger import get_logger

logger = get_logger("core.degradation")


class ComponentStatus(str, enum.Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    FAILED = "failed"


_STATUS_LABELS_RU: dict[ComponentStatus, str] = {
    ComponentStatus.HEALTHY: "✅ Работает",
    ComponentStatus.DEGRADED: "⚠️ Деградация",
    ComponentStatus.FAILED: "❌ Сбой",
}

# Components whose FAILED status prevents new order submission.
CRITICAL_COMPONENTS: frozenset[str] = frozenset({
    "quik_connector",
    "risk_engine",
    "order_manager",
})


@dataclass
class _ComponentRecord:
    status: ComponentStatus
    reason: str
    updated_at: float
    history: list[tuple[float, ComponentStatus, str]] = field(default_factory=list)


class GracefulDegradation:
    """Central component-health registry.

    Any subsystem calls :meth:`report_status` to publish its current
    health.  The order pipeline checks :meth:`is_trading_allowed` before
    sending new orders.
    """

    def __init__(
        self,
        critical_components: frozenset[str] | None = None,
    ) -> None:
        self._critical = critical_components or CRITICAL_COMPONENTS
        self._components: dict[str, _ComponentRecord] = {}

    def report_status(
        self,
        component: str,
        status: ComponentStatus,
        reason: str = "",
    ) -> None:
        """Update the status of *component*."""
        now = time.time()
        rec = self._components.get(component)
        if rec is None:
            rec = _ComponentRecord(status=status, reason=reason, updated_at=now)
            self._components[component] = rec
        else:
            if rec.status != status:
                rec.history.append((now, rec.status, rec.reason))
                if len(rec.history) > 50:
                    rec.history = rec.history[-50:]
            rec.status = status
            rec.reason = reason
            rec.updated_at = now

        if status == ComponentStatus.FAILED:
            logger.error("component '{}' FAILED: {}", component, reason)
        elif status == ComponentStatus.DEGRADED:
            logger.warning("component '{}' DEGRADED: {}", component, reason)

    def is_trading_allowed(self) -> bool:
        """Return ``False`` if any critical component is in FAILED state."""
        for name in self._critical:
            rec = self._components.get(name)
            if rec is not None and rec.status == ComponentStatus.FAILED:
                return False
        return True

    def get_system_health(self) -> dict[str, ComponentStatus]:
        return {name: rec.status for name, rec in self._components.items()}

    def get_component_detail(self, component: str) -> dict[str, Any] | None:
        rec = self._components.get(component)
        if rec is None:
            return None
        return {
            "status": rec.status.value,
            "reason": rec.reason,
            "updated_at": rec.updated_at,
            "history_len": len(rec.history),
        }

    def get_degradation_report(self) -> str:
        """Return a Russian-language summary suitable for Telegram/dashboard."""
        if not self._components:
            return "Нет данных о компонентах."

        lines: list[str] = ["📊 Состояние системы:", ""]
        for name, rec in sorted(self._components.items()):
            label = _STATUS_LABELS_RU[rec.status]
            line = f"  {label}  {name}"
            if rec.reason:
                line += f" — {rec.reason}"
            lines.append(line)

        trading = self.is_trading_allowed()
        lines.append("")
        if trading:
            lines.append("🟢 Торговля разрешена.")
        else:
            failed = [
                n for n in self._critical
                if (r := self._components.get(n)) is not None
                and r.status == ComponentStatus.FAILED
            ]
            lines.append(
                f"🔴 Торговля ЗАПРЕЩЕНА — критические сбои: {', '.join(failed)}"
            )
        return "\n".join(lines)
