"""Value investing strategy: low P/E + P/B screening with dividend yield."""

from __future__ import annotations

from typing import Any

import pandas as pd

from ..base_strategy import BaseStrategy, Signal
from ...utils.logger import get_logger

log = get_logger("strategy.value_investing")


class ValueInvestingStrategy(BaseStrategy):
    """Screens for undervalued stocks and enters on technical support."""

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        super().__init__("value_investing", config)
        self._max_pe = self._config.get("max_pe", 12.0)
        self._max_pb = self._config.get("max_pb", 1.5)
        self._min_dividend_yield = self._config.get("min_dividend_yield", 4.0)
        self._support_lookback = self._config.get("support_lookback", 60)
        self._support_proximity_pct = self._config.get("support_proximity_pct", 2.0)
        self._stop_loss_pct = self._config.get("stop_loss_pct", 5.0)
        self._take_profit_pct = self._config.get("take_profit_pct", 15.0)

    def generate_signals(self, market_data: dict[str, Any]) -> list[Signal]:
        signals: list[Signal] = []
        ticker = market_data.get("ticker", "")
        fundamentals = market_data.get("fundamentals")
        df: pd.DataFrame | None = market_data.get("df")

        if fundamentals is None:
            return signals

        pe = fundamentals.get("pe_ratio")
        pb = fundamentals.get("pb_ratio")
        div_yield = fundamentals.get("dividend_yield", 0.0)

        if pe is None or pb is None:
            return signals
        if pe <= 0 or pe > self._max_pe:
            return signals
        if pb <= 0 or pb > self._max_pb:
            return signals
        if div_yield < self._min_dividend_yield:
            return signals

        if df is None or len(df) < self._support_lookback:
            return signals

        close = float(df["close"].iloc[-1])
        lookback = df["low"].iloc[-self._support_lookback:]
        support_level = float(lookback.min())

        proximity = (close - support_level) / close * 100 if close > 0 else 999
        if proximity > self._support_proximity_pct:
            return signals

        score = 0.0
        score += max(0, (self._max_pe - pe) / self._max_pe) * 0.3
        score += max(0, (self._max_pb - pb) / self._max_pb) * 0.3
        score += min(1.0, div_yield / 10.0) * 0.2
        score += max(0, (self._support_proximity_pct - proximity) / self._support_proximity_pct) * 0.2
        confidence = min(1.0, score)

        entry = close
        stop = entry * (1 - self._stop_loss_pct / 100)
        tp = entry * (1 + self._take_profit_pct / 100)

        signals.append(Signal(
            ticker=ticker, action="buy", confidence=confidence,
            entry_price=entry, stop_loss=stop, take_profit=tp,
            metadata={
                "pe": pe, "pb": pb, "dividend_yield": div_yield,
                "support_level": round(support_level, 4),
                "proximity_pct": round(proximity, 2),
                "type": "value_entry",
            },
        ))

        return signals
