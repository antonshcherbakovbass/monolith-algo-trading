"""Token-bucket rate limiter for QUIK API calls.

Allows a sustained rate of *max_rate* tokens/second with short bursts
up to *burst* tokens.  All methods are asyncio-safe.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any

from ..utils.logger import get_logger

logger = get_logger("core.rate_limiter")


class RateLimiter:
    """Token bucket rate limiter.

    Parameters
    ----------
    max_rate:
        Sustained tokens per second.
    burst:
        Maximum token bucket capacity (allows short bursts above *max_rate*).
    """

    def __init__(self, max_rate: float = 50.0, burst: int = 10) -> None:
        if max_rate <= 0:
            raise ValueError("max_rate must be positive")
        if burst < 1:
            raise ValueError("burst must be >= 1")
        self._max_rate = max_rate
        self._burst = float(burst)
        self._tokens = float(burst)
        self._last_refill = time.monotonic()
        self._lock = asyncio.Lock()

        # Metrics
        self._total_acquired = 0
        self._total_waited_s = 0.0

    def _refill(self) -> None:
        now = time.monotonic()
        elapsed = now - self._last_refill
        self._tokens = min(self._burst, self._tokens + elapsed * self._max_rate)
        self._last_refill = now

    async def acquire(self, tokens: int = 1) -> float:
        """Wait until *tokens* are available and consume them.

        Returns the total seconds spent waiting (0.0 if tokens were
        immediately available).
        """
        if tokens < 1:
            raise ValueError("tokens must be >= 1")
        total_wait = 0.0
        async with self._lock:
            self._refill()
            while self._tokens < tokens:
                deficit = tokens - self._tokens
                wait = deficit / self._max_rate
                total_wait += wait
                await asyncio.sleep(wait)
                self._refill()
            self._tokens -= tokens
            self._total_acquired += tokens
            self._total_waited_s += total_wait
        return total_wait

    @property
    def available_tokens(self) -> float:
        """Current token count (approximate, no lock)."""
        elapsed = time.monotonic() - self._last_refill
        return min(self._burst, self._tokens + elapsed * self._max_rate)

    def get_metrics(self) -> dict[str, Any]:
        return {
            "max_rate": self._max_rate,
            "burst": self._burst,
            "available_tokens": round(self.available_tokens, 2),
            "total_acquired": self._total_acquired,
            "total_waited_s": round(self._total_waited_s, 4),
        }
