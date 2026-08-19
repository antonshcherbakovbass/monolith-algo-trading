"""Bollinger Band squeeze breakout strategy with volume confirmation."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from ..base_strategy import BaseStrategy, Signal
from ...analysis.technical import bollinger_bands, atr
from ...utils.logger import get_logger

log = get_logger("strategy.breakout")


class BreakoutStrategy(BaseStrategy):
    """Enters on BB squeeze breakout with volume confirmation. Targets 2× range."""

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        super().__init__("bb_breakout", config)
        self._bb_period = self._config.get("bb_period", 20)
        self._bb_std = self._config.get("bb_std", 2.0)
        self._squeeze_threshold = self._config.get("squeeze_threshold", 0.5)
        self._volume_mult = self._config.get("volume_mult", 1.5)
        self._atr_period = self._config.get("atr_period", 14)
        self._target_mult = self._config.get("target_mult", 2.0)
        self._stop_atr_mult = self._config.get("stop_atr_mult", 1.5)

    def generate_signals(self, market_data: dict[str, Any]) -> list[Signal]:
        signals: list[Signal] = []
        df: pd.DataFrame | None = market_data.get("df")
        ticker = market_data.get("ticker", "")

        if df is None or len(df) < self._bb_period + 10:
            return signals

        bb_upper, bb_middle, bb_lower = bollinger_bands(df["close"], self._bb_period, self._bb_std)
        atr_vals = atr(df, self._atr_period)

        bw = (bb_upper - bb_lower) / bb_middle.replace(0, np.nan)
        bw_avg = bw.rolling(self._bb_period).mean()

        last_idx = len(df) - 1
        current_bw = bw.iloc[last_idx]
        avg_bw = bw_avg.iloc[last_idx]
        close = df["close"].iloc[last_idx]
        prev_close = df["close"].iloc[last_idx - 1]
        current_atr = atr_vals.iloc[last_idx]

        if pd.isna(current_bw) or pd.isna(avg_bw) or avg_bw == 0:
            return signals

        was_squeezed = any(
            bw.iloc[i] < self._squeeze_threshold * avg_bw
            for i in range(max(0, last_idx - 5), last_idx)
        )
        if not was_squeezed:
            return signals

        vol_ma = df["volume"].rolling(20).mean()
        vol_ratio = df["volume"].iloc[last_idx] / vol_ma.iloc[last_idx] if vol_ma.iloc[last_idx] > 0 else 0
        if vol_ratio < self._volume_mult:
            return signals

        up_upper = bb_upper.iloc[last_idx]
        lo_lower = bb_lower.iloc[last_idx]
        bb_range = up_upper - lo_lower

        confidence = min(1.0, 0.6 + (vol_ratio - self._volume_mult) * 0.1)

        if close > up_upper and prev_close <= bb_upper.iloc[last_idx - 1]:
            entry = close
            stop = entry - self._stop_atr_mult * current_atr
            tp = entry + self._target_mult * bb_range
            signals.append(Signal(
                ticker=ticker, action="buy", confidence=confidence,
                entry_price=entry, stop_loss=stop, take_profit=tp,
                metadata={"type": "bb_squeeze_breakout_long", "vol_ratio": round(vol_ratio, 2)},
            ))

        elif close < lo_lower and prev_close >= bb_lower.iloc[last_idx - 1]:
            entry = close
            stop = entry + self._stop_atr_mult * current_atr
            tp = entry - self._target_mult * bb_range
            signals.append(Signal(
                ticker=ticker, action="sell", confidence=confidence,
                entry_price=entry, stop_loss=stop, take_profit=tp,
                metadata={"type": "bb_squeeze_breakout_short", "vol_ratio": round(vol_ratio, 2)},
            ))

        return signals
