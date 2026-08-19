"""Statistical arbitrage on cointegrated pairs."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from ..base_strategy import BaseStrategy, Signal
from ...utils.logger import get_logger

log = get_logger("strategy.stat_arb")

_DEFAULT_PAIRS = [
    ("SBER", "VTBR"),
    ("GAZP", "ROSN"),
    ("LKOH", "NVTK"),
    ("GMKN", "RUAL"),
]


class StatArbStrategy(BaseStrategy):
    """Cointegration-based pairs trading with dynamic hedge ratios."""

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        super().__init__("stat_arb", config)
        self._pairs: list[tuple[str, str]] = [
            tuple(p) for p in self._config.get("pairs", _DEFAULT_PAIRS)
        ]
        self._coint_window = self._config.get("cointegration_window", 60)
        self._z_entry = self._config.get("z_score_entry", 2.0)
        self._z_exit = self._config.get("z_score_exit", 0.5)
        self._stop_z = self._config.get("z_score_stop", 3.5)
        self._min_half_life = self._config.get("min_half_life", 5)
        self._max_half_life = self._config.get("max_half_life", 60)
        self._hedge_ratios: dict[tuple[str, str], float] = {}

    def _compute_hedge_ratio(self, y: pd.Series, x: pd.Series) -> float:
        """OLS hedge ratio: y = beta * x + alpha."""
        if len(x) < 20 or x.std() == 0:
            return 1.0
        cov = np.cov(y, x)
        return float(cov[0, 1] / cov[1, 1]) if cov[1, 1] != 0 else 1.0

    def _compute_spread(self, y: pd.Series, x: pd.Series, beta: float) -> pd.Series:
        return y - beta * x

    def _compute_half_life(self, spread: pd.Series) -> float:
        """Mean-reversion half-life via AR(1)."""
        lagged = spread.shift(1).dropna()
        delta = spread.diff().dropna()
        common = lagged.index.intersection(delta.index)
        if len(common) < 10:
            return float("inf")
        lagged = lagged.loc[common]
        delta = delta.loc[common]
        cov_ld = np.cov(lagged, delta)
        if cov_ld[0, 0] == 0:
            return float("inf")
        phi = cov_ld[0, 1] / cov_ld[0, 0]
        if phi >= 0:
            return float("inf")
        return float(-np.log(2) / phi)

    def _test_cointegration(self, y: pd.Series, x: pd.Series) -> bool:
        """Simplified cointegration test via spread stationarity heuristic."""
        beta = self._compute_hedge_ratio(y, x)
        spread = self._compute_spread(y, x, beta)
        hl = self._compute_half_life(spread)
        return self._min_half_life <= hl <= self._max_half_life

    def generate_signals(self, market_data: dict[str, Any]) -> list[Signal]:
        signals: list[Signal] = []
        prices: dict[str, pd.Series] = market_data.get("prices", {})

        for leg_a, leg_b in self._pairs:
            if leg_a not in prices or leg_b not in prices:
                continue

            y = prices[leg_a].dropna()
            x = prices[leg_b].dropna()
            common_idx = y.index.intersection(x.index)
            if len(common_idx) < self._coint_window:
                continue
            y = y.loc[common_idx[-self._coint_window:]]
            x = x.loc[common_idx[-self._coint_window:]]

            if not self._test_cointegration(y, x):
                continue

            beta = self._compute_hedge_ratio(y, x)
            self._hedge_ratios[(leg_a, leg_b)] = beta
            spread = self._compute_spread(y, x, beta)

            mean = spread.mean()
            std = spread.std()
            if std == 0:
                continue
            z = (spread.iloc[-1] - mean) / std

            last_y = float(y.iloc[-1])
            last_x = float(x.iloc[-1])
            confidence = min(1.0, abs(float(z)) / self._stop_z)

            if z > self._z_entry:
                signals.append(Signal(
                    ticker=leg_a, action="sell", confidence=confidence,
                    entry_price=last_y,
                    stop_loss=last_y * 1.03,
                    take_profit=last_y * (1 - self._z_exit * std / last_y) if last_y > 0 else last_y * 0.98,
                    metadata={
                        "pair": f"{leg_a}/{leg_b}", "z_score": round(float(z), 3),
                        "hedge_ratio": round(beta, 4), "leg": "short_a",
                    },
                ))
                signals.append(Signal(
                    ticker=leg_b, action="buy", confidence=confidence,
                    entry_price=last_x,
                    stop_loss=last_x * 0.97,
                    take_profit=last_x * (1 + self._z_exit * std / (beta * last_x)) if last_x > 0 and beta > 0 else last_x * 1.02,
                    metadata={
                        "pair": f"{leg_a}/{leg_b}", "z_score": round(float(z), 3),
                        "hedge_ratio": round(beta, 4), "leg": "long_b",
                    },
                ))

            elif z < -self._z_entry:
                signals.append(Signal(
                    ticker=leg_a, action="buy", confidence=confidence,
                    entry_price=last_y,
                    stop_loss=last_y * 0.97,
                    take_profit=last_y * (1 + self._z_exit * std / last_y) if last_y > 0 else last_y * 1.02,
                    metadata={
                        "pair": f"{leg_a}/{leg_b}", "z_score": round(float(z), 3),
                        "hedge_ratio": round(beta, 4), "leg": "long_a",
                    },
                ))
                signals.append(Signal(
                    ticker=leg_b, action="sell", confidence=confidence,
                    entry_price=last_x,
                    stop_loss=last_x * 1.03,
                    take_profit=last_x * (1 - self._z_exit * std / (beta * last_x)) if last_x > 0 and beta > 0 else last_x * 0.98,
                    metadata={
                        "pair": f"{leg_a}/{leg_b}", "z_score": round(float(z), 3),
                        "hedge_ratio": round(beta, 4), "leg": "short_b",
                    },
                ))

        return signals
