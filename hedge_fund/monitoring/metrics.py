"""Lightweight metrics collection (no external dependencies like Prometheus)."""
from __future__ import annotations

import statistics
import time
import threading
from collections import defaultdict, deque
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Generator

from ..utils.logger import get_logger

log = get_logger("monitoring.metrics")


@dataclass
class MetricPoint:
    name: str
    value: float
    timestamp: float
    labels: dict[str, str] = field(default_factory=dict)


class MetricsCollector:
    """Thread-safe metrics collector with in-memory storage."""

    _instance: MetricsCollector | None = None
    _lock_cls = threading.Lock()

    def __new__(cls) -> MetricsCollector:
        with cls._lock_cls:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self) -> None:
        if self._initialized:
            return
        self._initialized = True
        self._lock = threading.Lock()
        self._counters: dict[str, float] = defaultdict(float)
        self._gauges: dict[str, float] = {}
        self._histograms: dict[str, deque[float]] = defaultdict(lambda: deque(maxlen=10000))
        self._points: dict[str, list[MetricPoint]] = defaultdict(list)
        self._max_points = 10000

    def counter(self, name: str, value: float = 1.0, labels: dict[str, str] | None = None) -> None:
        """Increment a counter metric."""
        key = self._make_key(name, labels)
        with self._lock:
            self._counters[key] += value
            self._record(name, self._counters[key], labels)

    def gauge(self, name: str, value: float, labels: dict[str, str] | None = None) -> None:
        """Set a gauge metric to an absolute value."""
        key = self._make_key(name, labels)
        with self._lock:
            self._gauges[key] = value
            self._record(name, value, labels)

    def histogram(self, name: str, value: float, labels: dict[str, str] | None = None) -> None:
        """Record a value in a histogram (for latency distributions, etc.)."""
        key = self._make_key(name, labels)
        with self._lock:
            self._histograms[key].append(value)
            self._record(name, value, labels)

    @contextmanager
    def timer(self, name: str, labels: dict[str, str] | None = None) -> Generator[None, None, None]:
        """Context manager that measures duration in ms and records to histogram."""
        start = time.perf_counter()
        try:
            yield
        finally:
            elapsed_ms = (time.perf_counter() - start) * 1000
            self.histogram(name, elapsed_ms, labels)

    def get_all(self) -> dict[str, list[MetricPoint]]:
        """Return all recorded metric points."""
        with self._lock:
            return dict(self._points)

    def get_summary(self) -> dict[str, dict]:
        """Return aggregated summary: count, avg, min, max, p50, p95, p99."""
        with self._lock:
            result: dict[str, dict] = {}

            for key, val in self._counters.items():
                result[key] = {"type": "counter", "value": val}

            for key, val in self._gauges.items():
                result[key] = {"type": "gauge", "value": val}

            for key, values in self._histograms.items():
                if not values:
                    continue
                sorted_vals = sorted(values)
                n = len(sorted_vals)
                result[key] = {
                    "type": "histogram",
                    "count": n,
                    "avg": statistics.mean(sorted_vals),
                    "min": sorted_vals[0],
                    "max": sorted_vals[-1],
                    "p50": sorted_vals[int(n * 0.5)],
                    "p95": sorted_vals[min(int(n * 0.95), n - 1)],
                    "p99": sorted_vals[min(int(n * 0.99), n - 1)],
                }

            return result

    def reset(self) -> None:
        """Clear all metrics."""
        with self._lock:
            self._counters.clear()
            self._gauges.clear()
            self._histograms.clear()
            self._points.clear()

    def _make_key(self, name: str, labels: dict[str, str] | None) -> str:
        if not labels:
            return name
        label_str = ",".join(f"{k}={v}" for k, v in sorted(labels.items()))
        return f"{name}{{{label_str}}}"

    def _record(self, name: str, value: float, labels: dict[str, str] | None) -> None:
        point = MetricPoint(
            name=name,
            value=value,
            timestamp=time.time(),
            labels=labels or {},
        )
        points_list = self._points[name]
        if len(points_list) >= self._max_points:
            points_list.pop(0)
        points_list.append(point)
