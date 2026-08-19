"""Short-term momentum burst scalping strategy."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from ..base_strategy import BaseStrategy, Signal
from ...utils.logger import get_logger

log = get_logger("strategy.momentum_scalp")


class MomentumScalpStrategy(BaseStrategy):
    """Detects volume spikes paired with directional moves for quick entries."""

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        super().__init__("momentum_scalp", config)
        self._volume_spike_mult = self._config.get("volume_spike_mult", 2.0)
        self._min_move_pct = self._config.get("min_move_pct", 0.15)
        self._take_profit_pct = self._config.get("take_profit_pct", 0.2)
        self._stop_loss_pct = self._config.get("stop_loss_pct", 0.1)
        self._lookback = self._config.get("lookback", 20)
        self._confirmation_bars = self._config.get("confirmation_bars", 3)

    def generate_signals(self, market_data: dict[str, Any]) -> list[Signal]:
        signals: list[Signal] = []
        df: pd.DataFrame | None = market_data.get("df")
        ticker = market_data.get("ticker", "")
        last_price = market_data.get("last_price", 0.0)

        if df is None or len(df) < self._lookback + self._confirmation_bars:
            return signals

        vol_ma = df["volume"].rolling(self._lookback).mean()
        current_vol = df["volume"].iloc[-1]
        avg_vol = vol_ma.iloc[-1]

        if avg_vol <= 0 or current_vol / avg_vol < self._volume_spike_mult:
            return signals

        recent = df["close"].iloc[-self._confirmation_bars:]
        move_pct = (recent.iloc[-1] - recent.iloc[0]) / recent.iloc[0] * 100 if recent.iloc[0] > 0 else 0

        if abs(move_pct) < self._min_move_pct:
            return signals

        direction_consistent = all(recent.diff().dropna() > 0) or all(recent.diff().dropna() < 0)
        if not direction_consistent:
            return signals

        vol_ratio = current_vol / avg_vol
        confidence = min(1.0, 0.5 + (vol_ratio - self._volume_spike_mult) * 0.15 + abs(move_pct) * 0.5)

        if move_pct > 0:
            entry = last_price
            stop = entry * (1 - self._stop_loss_pct / 100)
            tp = entry * (1 + self._take_profit_pct / 100)
            signals.append(Signal(
                ticker=ticker, action="buy", confidence=confidence,
                entry_price=entry, stop_loss=stop, take_profit=tp,
                metadata={
                    "volume_ratio": round(vol_ratio, 2),
                    "move_pct": round(move_pct, 4),
                    "type": "momentum_burst_long",
                },
            ))
        else:
            entry = last_price
            stop = entry * (1 + self._stop_loss_pct / 100)
            tp = entry * (1 - self._take_profit_pct / 100)
            signals.append(Signal(
                ticker=ticker, action="sell", confidence=confidence,
                entry_price=entry, stop_loss=stop, take_profit=tp,
                metadata={
                    "volume_ratio": round(vol_ratio, 2),
                    "move_pct": round(move_pct, 4),
                    "type": "momentum_burst_short",
                },
            ))

        return signals
