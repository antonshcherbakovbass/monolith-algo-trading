"""Circuit breaker pattern for external service calls.

Prevents cascading failures by tracking consecutive errors and
temporarily rejecting calls when a failure threshold is exceeded.

States:
    CLOSED   — normal operation, calls pass through
    OPEN     — too many failures, calls rejected immediately
    HALF_OPEN — recovery probe: allow limited calls to test if service recovered
"""

from __future__ import annotations

import asyncio
import enum
import time
from collections import deque
from typing import Any, Callable, TypeVar

from ..utils.logger import get_logger

logger = get_logger("core.circuit_breaker")

T = TypeVar("T")


class CircuitState(str, enum.Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreakerOpen(Exception):
    """Raised when circuit is open and call is rejected."""

    def __init__(self, breaker_name: str, time_until_half_open: float) -> None:
        self.breaker_name = breaker_name
        self.time_until_half_open = time_until_half_open
        super().__init__(
            f"Circuit breaker '{breaker_name}' is OPEN, "
            f"retry in {time_until_half_open:.1f}s"
        )


class CircuitBreaker:
    """Circuit breaker pattern for external service calls.

    Parameters
    ----------
    name:
        Human-readable identifier for logging and metrics.
    failure_threshold:
        Consecutive failures before opening the circuit.
    recovery_timeout:
        Seconds to wait in OPEN state before transitioning to HALF_OPEN.
    half_open_max_calls:
        Maximum concurrent probe calls allowed in HALF_OPEN state.
    success_threshold:
        Consecutive successes in HALF_OPEN needed to close the circuit.
    excluded_exceptions:
        Exception types that should NOT count as failures (e.g. validation errors).
    """

    def __init__(
        self,
        name: str = "default",
        failure_threshold: int = 5,
        recovery_timeout: float = 30.0,
        half_open_max_calls: int = 1,
        success_threshold: int = 2,
        excluded_exceptions: tuple[type[BaseException], ...] = (),
    ) -> None:
        self._name = name
        self._failure_threshold = failure_threshold
        self._recovery_timeout = recovery_timeout
        self._half_open_max_calls = half_open_max_calls
        self._success_threshold = success_threshold
        self._excluded_exceptions = excluded_exceptions

        self._state = CircuitState.CLOSED
        self._consecutive_failures = 0
        self._consecutive_successes = 0
        self._half_open_in_flight = 0
        self._opened_at: float = 0.0
        self._lock = asyncio.Lock()

        # Metrics
        self._total_calls = 0
        self._total_successes = 0
        self._total_failures = 0
        self._total_rejected = 0
        self._failure_timestamps: deque[float] = deque(maxlen=100)
        self._last_failure_reason: str = ""
        self._state_changes: deque[tuple[float, CircuitState, CircuitState]] = deque(maxlen=50)

    @property
    def name(self) -> str:
        return self._name

    @property
    def state(self) -> CircuitState:
        if self._state == CircuitState.OPEN:
            if time.monotonic() - self._opened_at >= self._recovery_timeout:
                return CircuitState.HALF_OPEN
        return self._state

    async def call(self, func: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        """Execute *func* through the circuit breaker.

        Raises ``CircuitBreakerOpen`` if the circuit is open and the
        recovery timeout has not yet elapsed.
        """
        async with self._lock:
            current = self.state
            if current != self._state:
                self._transition(current)

            if current == CircuitState.OPEN:
                self._total_rejected += 1
                remaining = self._recovery_timeout - (time.monotonic() - self._opened_at)
                raise CircuitBreakerOpen(self._name, max(0.0, remaining))

            if current == CircuitState.HALF_OPEN:
                if self._half_open_in_flight >= self._half_open_max_calls:
                    self._total_rejected += 1
                    raise CircuitBreakerOpen(self._name, 1.0)
                self._half_open_in_flight += 1

        self._total_calls += 1
        try:
            if asyncio.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)
            await self._record_success()
            return result
        except BaseException as exc:
            if isinstance(exc, self._excluded_exceptions):
                await self._record_success()
                raise
            await self._record_failure(exc)
            raise

    async def _record_success(self) -> None:
        async with self._lock:
            self._total_successes += 1
            self._consecutive_failures = 0
            self._consecutive_successes += 1
            if self._state == CircuitState.HALF_OPEN:
                self._half_open_in_flight = max(0, self._half_open_in_flight - 1)
                if self._consecutive_successes >= self._success_threshold:
                    self._transition(CircuitState.CLOSED)

    async def _record_failure(self, exc: BaseException) -> None:
        async with self._lock:
            self._total_failures += 1
            self._consecutive_failures += 1
            self._consecutive_successes = 0
            self._failure_timestamps.append(time.monotonic())
            self._last_failure_reason = f"{type(exc).__name__}: {exc}"

            if self._state == CircuitState.HALF_OPEN:
                self._half_open_in_flight = max(0, self._half_open_in_flight - 1)
                self._transition(CircuitState.OPEN)
            elif self._consecutive_failures >= self._failure_threshold:
                self._transition(CircuitState.OPEN)

    def _transition(self, new_state: CircuitState) -> None:
        old = self._state
        self._state = new_state
        self._state_changes.append((time.monotonic(), old, new_state))

        if new_state == CircuitState.OPEN:
            self._opened_at = time.monotonic()
            self._consecutive_successes = 0
            logger.warning(
                "circuit '{}' OPEN after {} failures: {}",
                self._name, self._consecutive_failures, self._last_failure_reason,
            )
        elif new_state == CircuitState.HALF_OPEN:
            self._half_open_in_flight = 0
            self._consecutive_successes = 0
            logger.info("circuit '{}' HALF_OPEN, probing...", self._name)
        elif new_state == CircuitState.CLOSED:
            self._consecutive_failures = 0
            logger.info("circuit '{}' CLOSED, recovered", self._name)

    def reset(self) -> None:
        """Force-reset the breaker to CLOSED."""
        self._state = CircuitState.CLOSED
        self._consecutive_failures = 0
        self._consecutive_successes = 0
        self._half_open_in_flight = 0
        logger.info("circuit '{}' manually reset", self._name)

    def get_metrics(self) -> dict[str, Any]:
        now = time.monotonic()
        recent_failures = sum(1 for t in self._failure_timestamps if now - t < 60.0)
        return {
            "name": self._name,
            "state": self.state.value,
            "total_calls": self._total_calls,
            "total_successes": self._total_successes,
            "total_failures": self._total_failures,
            "total_rejected": self._total_rejected,
            "consecutive_failures": self._consecutive_failures,
            "failures_last_60s": recent_failures,
            "last_failure_reason": self._last_failure_reason,
        }
