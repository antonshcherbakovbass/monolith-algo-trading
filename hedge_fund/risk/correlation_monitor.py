"""
Real-time Correlation Matrix Monitor.

Tracks rolling correlations between all portfolio instruments
to prevent cluster risk accumulation.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
import numpy as np
import pandas as pd
from loguru import logger


class CorrelationMonitor:
    """
    Monitors inter-asset correlations in real time.
    
    Features:
    - Rolling correlation matrix (configurable window)
    - Cluster detection (groups of highly correlated assets)
    - Correlation regime change alerts
    - Portfolio diversification score
    - Concentration risk warnings
    """

    def __init__(self, window: int = 60, alert_threshold: float = 0.7):
        self.window = window
        self.alert_threshold = alert_threshold
        self.returns_buffer: dict[str, list[float]] = {}
        self.last_matrix: pd.DataFrame | None = None
        self.correlation_history: list[dict] = []
        self.log = logger.bind(component="correlation_monitor")

    def update(self, ticker: str, price: float) -> None:
        buf = self.returns_buffer.setdefault(ticker, [])
        buf.append(price)
        if len(buf) > self.window + 10:
            self.returns_buffer[ticker] = buf[-(self.window + 5):]

    def compute_matrix(self) -> pd.DataFrame | None:
        eligible = {t: v for t, v in self.returns_buffer.items() if len(v) >= self.window + 1}
        if len(eligible) < 2:
            return None

        returns_dict = {}
        for ticker, prices in eligible.items():
            p = np.array(prices[-(self.window+1):])
            rets = np.diff(p) / p[:-1]
            returns_dict[ticker] = rets[-self.window:]

        df = pd.DataFrame(returns_dict)
        corr = df.corr()
        self.last_matrix = corr
        return corr

    def detect_clusters(self, threshold: float | None = None) -> list[list[str]]:
        if self.last_matrix is None:
            self.compute_matrix()
        if self.last_matrix is None:
            return []

        thresh = threshold or self.alert_threshold
        tickers = list(self.last_matrix.columns)
        visited = set()
        clusters = []

        for t in tickers:
            if t in visited:
                continue
            cluster = [t]
            visited.add(t)
            for other in tickers:
                if other in visited:
                    continue
                if abs(self.last_matrix.loc[t, other]) > thresh:
                    cluster.append(other)
                    visited.add(other)
            if len(cluster) > 1:
                clusters.append(cluster)

        return clusters

    def diversification_score(self) -> float:
        """0=fully correlated, 1=fully diversified."""
        if self.last_matrix is None:
            self.compute_matrix()
        if self.last_matrix is None or len(self.last_matrix) < 2:
            return 1.0

        n = len(self.last_matrix)
        upper = []
        for i in range(n):
            for j in range(i + 1, n):
                upper.append(abs(self.last_matrix.iloc[i, j]))

        if not upper:
            return 1.0
        avg_corr = np.mean(upper)
        return max(0.0, 1.0 - avg_corr)

    def get_high_correlations(self) -> list[tuple[str, str, float]]:
        if self.last_matrix is None:
            return []
        result = []
        tickers = list(self.last_matrix.columns)
        for i in range(len(tickers)):
            for j in range(i + 1, len(tickers)):
                corr = self.last_matrix.iloc[i, j]
                if abs(corr) > self.alert_threshold:
                    result.append((tickers[i], tickers[j], round(corr, 3)))
        result.sort(key=lambda x: abs(x[2]), reverse=True)
        return result

    def get_alerts(self, position_tickers: list[str]) -> list[str]:
        alerts = []
        clusters = self.detect_clusters()
        for cluster in clusters:
            in_portfolio = [t for t in cluster if t in position_tickers]
            if len(in_portfolio) > 1:
                alerts.append(
                    f"Cluster risk: {', '.join(in_portfolio)} highly correlated "
                    f"(cluster of {len(cluster)} assets)"
                )

        score = self.diversification_score()
        if score < 0.3:
            alerts.append(f"Low diversification score: {score:.2f} (target > 0.5)")

        return alerts

    def get_report(self) -> dict[str, Any]:
        self.compute_matrix()
        return {
            "diversification_score": self.diversification_score(),
            "clusters": self.detect_clusters(),
            "high_correlations": self.get_high_correlations()[:10],
            "instruments_tracked": len(self.returns_buffer),
            "matrix_size": len(self.last_matrix) if self.last_matrix is not None else 0,
        }
