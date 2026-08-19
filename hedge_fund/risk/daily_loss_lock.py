"""
Daily Loss Lock — halts all trading when cumulative intraday losses exceed a threshold.

The lock resets automatically at the start of the next Moscow trading day (10:00 MSK).
"""
from __future__ import annotations

from datetime import datetime, timezone, timedelta

from ..utils.logger import get_logger

logger = get_logger("risk.daily_loss_lock")

MOSCOW_TZ = timezone(timedelta(hours=3))


class DailyLossLock:
    """Tracks cumulative daily losses and locks trading when the limit is hit."""

    def __init__(self, max_daily_loss_pct: float, portfolio_value: float) -> None:
        self.max_daily_loss_pct: float = max_daily_loss_pct
        self.portfolio_value: float = portfolio_value
        self._cumulative_loss: float = 0.0
        self._locked: bool = False
        self._lock_time: datetime | None = None
        logger.info(
            "DailyLossLock init — limit {:.2f}% of {:.0f} RUB",
            max_daily_loss_pct,
            portfolio_value,
        )

    @property
    def _max_loss_absolute(self) -> float:
        return self.portfolio_value * self.max_daily_loss_pct / 100.0

    def record_loss(self, amount: float) -> None:
        """Record a loss (positive value = loss). Locks trading if limit exceeded."""
        if amount <= 0:
            return
        self._cumulative_loss += amount
        logger.debug("Loss recorded: {:.2f} RUB (cumulative {:.2f})", amount, self._cumulative_loss)
        if self._cumulative_loss >= self._max_loss_absolute and not self._locked:
            self._locked = True
            self._lock_time = datetime.now(MOSCOW_TZ)
            logger.warning(
                "DAILY LOSS LOCK ACTIVATED — cumulative {:.2f} >= limit {:.2f}",
                self._cumulative_loss,
                self._max_loss_absolute,
            )

    def is_locked(self) -> bool:
        """Return *True* when daily loss exceeds the configured limit."""
        return self._locked

    def get_remaining_budget(self) -> float:
        """How much more can be lost today before the lock triggers."""
        return max(self._max_loss_absolute - self._cumulative_loss, 0.0)

    def reset(self) -> None:
        """Reset counters — call at the start of a new trading day."""
        self._cumulative_loss = 0.0
        self._locked = False
        self._lock_time = None
        logger.info("DailyLossLock reset for new trading day")

    def lock_reason(self) -> str:
        """Human-readable lock explanation in Russian."""
        if not self._locked:
            return ""
        return (
            f"Торговля приостановлена: дневной убыток ({self._cumulative_loss:,.0f} ₽) "
            f"превысил лимит ({self._max_loss_absolute:,.0f} ₽ / "
            f"{self.max_daily_loss_pct:.1f}% портфеля). "
            f"Разблокировка в 10:00 МСК следующего торгового дня."
        )

    def time_until_unlock(self) -> str:
        """Time remaining until the next Moscow trading day open (10:00 MSK)."""
        now = datetime.now(MOSCOW_TZ)
        next_open = now.replace(hour=10, minute=0, second=0, microsecond=0)
        if now >= next_open:
            next_open += timedelta(days=1)
        # Skip weekends
        while next_open.weekday() >= 5:
            next_open += timedelta(days=1)
        delta = next_open - now
        hours, remainder = divmod(int(delta.total_seconds()), 3600)
        minutes = remainder // 60
        return f"{hours}ч {minutes}мин до открытия (10:00 МСК)"
