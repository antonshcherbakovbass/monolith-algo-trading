"""VWAP mean-reversion strategy with RSI confirmation."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from ..base_strategy import BaseStrategy, Signal
from ...analysis.technical import rsi, vwap, atr
from ...utils.logger import get_logger

log = get_logger("strategy.mean_reversion")


class MeanReversionStrategy(BaseStrategy):
    """Enters when price deviates > 2 std from VWAP; exits on reversion. RSI confirms."""

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        super().__init__("vwap_mean_reversion", config)
        self._std_threshold = self._config.get("std_threshold", 2.0)
        self._rsi_oversold = self._config.get("rsi_oversold", 30)
        self._rsi_overbought = self._config.get("rsi_overbought", 70)
        self._atr_period = self._config.get("atr_period", 14)
        self._stop_atr_mult = self._config.get("stop_atr_mult", 2.0)

    def generate_signals(self, market_data: dict[str, Any]) -> list[Signal]:
        signals: list[Signal] = []
        df: pd.DataFrame | None = market_data.get("df")
        ticker = market_data.get("ticker", "")

        if df is None or len(df) < 30:
            return signals

        vwap_vals = vwap(df)
        rsi_vals = rsi(df["close"], period=14)
        atr_vals = atr(df, self._atr_period)

        deviation = df["close"] - vwap_vals
        std_dev = deviation.rolling(20).std().replace(0, np.nan)
        z_score = deviation / std_dev

        last_idx = len(df) - 1
        z = z_score.iloc[last_idx]
        current_rsi = rsi_vals.iloc[last_idx]
        current_atr = atr_vals.iloc[last_idx]
        close = df["close"].iloc[last_idx]
        current_vwap = vwap_vals.iloc[last_idx]

        if pd.isna(z) or pd.isna(current_rsi) or pd.isna(current_atr):
            return signals

        if z < -self._std_threshold and current_rsi < self._rsi_oversold:
            entry = close
            stop = entry - self._stop_atr_mult * current_atr
            tp = current_vwap
            confidence = min(1.0, 0.5 + abs(z) * 0.1 + (self._rsi_oversold - current_rsi) / 100)
            signals.append(Signal(
                ticker=ticker, action="buy", confidence=confidence,
                entry_price=entry, stop_loss=stop, take_profit=tp,
                metadata={
                    "z_score": round(float(z), 3),
                    "rsi": round(float(current_rsi), 2),
                    "vwap": round(float(current_vwap), 4),
                    "type": "vwap_reversion_long",
                },
            ))

        elif z > self._std_threshold and current_rsi > self._rsi_overbought:
            entry = close
            stop = entry + self._stop_atr_mult * current_atr
            tp = current_vwap
            confidence = min(1.0, 0.5 + abs(z) * 0.1 + (current_rsi - self._rsi_overbought) / 100)
            signals.append(Signal(
                ticker=ticker, action="sell", confidence=confidence,
                entry_price=entry, stop_loss=stop, take_profit=tp,
                metadata={
                    "z_score": round(float(z), 3),
                    "rsi": round(float(current_rsi), 2),
                    "vwap": round(float(current_vwap), 4),
                    "type": "vwap_reversion_short",
                },
            ))

        return signals
