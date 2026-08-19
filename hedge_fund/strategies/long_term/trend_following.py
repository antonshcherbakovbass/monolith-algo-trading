"""EMA crossover trend-following strategy with ADX filter."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from ..base_strategy import BaseStrategy, Signal
from ...analysis.technical import ema, adx, atr
from ...utils.logger import get_logger

log = get_logger("strategy.trend_following")


class TrendFollowingStrategy(BaseStrategy):
    """EMA 20/50 crossover with ADX > 25 filter and ATR trailing stop."""

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        super().__init__("trend_following", config)
        self._fast_period = self._config.get("fast_period", 20)
        self._slow_period = self._config.get("slow_period", 50)
        self._adx_threshold = self._config.get("adx_threshold", 25)
        self._atr_period = self._config.get("atr_period", 14)
        self._atr_stop_mult = self._config.get("atr_stop_mult", 2.5)
        self._atr_tp_mult = self._config.get("atr_tp_mult", 4.0)

    def generate_signals(self, market_data: dict[str, Any]) -> list[Signal]:
        signals: list[Signal] = []
        df: pd.DataFrame | None = market_data.get("df")
        ticker = market_data.get("ticker", "")

        if df is None or len(df) < self._slow_period + 15:
            return signals

        ema_fast = ema(df["close"], self._fast_period)
        ema_slow = ema(df["close"], self._slow_period)
        adx_vals = adx(df, self._atr_period)
        atr_vals = atr(df, self._atr_period)

        last_idx = len(df) - 1
        current_adx = adx_vals.iloc[last_idx]
        current_atr = atr_vals.iloc[last_idx]
        close = df["close"].iloc[last_idx]

        if pd.isna(current_adx) or current_adx < self._adx_threshold:
            return signals

        fast_now = ema_fast.iloc[last_idx]
        fast_prev = ema_fast.iloc[last_idx - 1]
        slow_now = ema_slow.iloc[last_idx]
        slow_prev = ema_slow.iloc[last_idx - 1]

        confidence = min(1.0, 0.5 + (current_adx - self._adx_threshold) / 50)

        if fast_prev <= slow_prev and fast_now > slow_now:
            entry = close
            stop = entry - self._atr_stop_mult * current_atr
            tp = entry + self._atr_tp_mult * current_atr
            signals.append(Signal(
                ticker=ticker, action="buy", confidence=confidence,
                entry_price=entry, stop_loss=stop, take_profit=tp,
                metadata={
                    "adx": round(float(current_adx), 2),
                    "atr": round(float(current_atr), 4),
                    "type": "ema_crossover_long",
                },
            ))

        elif fast_prev >= slow_prev and fast_now < slow_now:
            entry = close
            stop = entry + self._atr_stop_mult * current_atr
            tp = entry - self._atr_tp_mult * current_atr
            signals.append(Signal(
                ticker=ticker, action="sell", confidence=confidence,
                entry_price=entry, stop_loss=stop, take_profit=tp,
                metadata={
                    "adx": round(float(current_adx), 2),
                    "atr": round(float(current_atr), 4),
                    "type": "ema_crossover_short",
                },
            ))

        return signals
