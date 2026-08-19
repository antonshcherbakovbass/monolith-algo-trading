"""Order-book imbalance scalping strategy."""

from __future__ import annotations

from typing import Any

from ..base_strategy import BaseStrategy, Signal
from ...utils.logger import get_logger

log = get_logger("strategy.orderbook_scalp")


class OrderbookScalpStrategy(BaseStrategy):
    """Enters when bid/ask volume imbalance exceeds threshold, exits quickly."""

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        super().__init__("orderbook_scalp", config)
        self._imbalance_threshold = self._config.get("imbalance_threshold", 0.6)
        self._take_profit_pct = self._config.get("take_profit_pct", 0.1)
        self._stop_loss_pct = self._config.get("stop_loss_pct", 0.05)
        self._min_spread_pct = self._config.get("min_spread_pct", 0.02)
        self._min_volume = self._config.get("min_volume", 100)
        self._max_hold_seconds = self._config.get("max_hold_seconds", 120)

    def generate_signals(self, market_data: dict[str, Any]) -> list[Signal]:
        signals: list[Signal] = []
        ticker = market_data.get("ticker", "")
        orderbook = market_data.get("orderbook")
        last_price = market_data.get("last_price", 0.0)

        if not orderbook or last_price <= 0:
            return signals

        bids = orderbook.get("bids", [])
        asks = orderbook.get("asks", [])
        if not bids or not asks:
            return signals

        bid_vol = sum(b.get("quantity", b.get("qty", 0)) for b in bids[:5])
        ask_vol = sum(a.get("quantity", a.get("qty", 0)) for a in asks[:5])
        total_vol = bid_vol + ask_vol

        if total_vol < self._min_volume:
            return signals

        imbalance = (bid_vol - ask_vol) / total_vol if total_vol > 0 else 0.0

        best_bid = bids[0].get("price", 0.0)
        best_ask = asks[0].get("price", 0.0)
        spread_pct = (best_ask - best_bid) / last_price * 100 if last_price > 0 else 0

        if spread_pct < self._min_spread_pct:
            return signals

        if imbalance > self._imbalance_threshold:
            entry = best_ask
            stop = entry * (1 - self._stop_loss_pct / 100)
            tp = entry * (1 + self._take_profit_pct / 100)
            confidence = min(1.0, abs(imbalance))
            signals.append(Signal(
                ticker=ticker, action="buy", confidence=confidence,
                entry_price=entry, stop_loss=stop, take_profit=tp,
                metadata={
                    "imbalance": round(imbalance, 4),
                    "bid_vol": bid_vol, "ask_vol": ask_vol,
                    "spread_pct": round(spread_pct, 4),
                    "max_hold_seconds": self._max_hold_seconds,
                },
            ))
        elif imbalance < -self._imbalance_threshold:
            entry = best_bid
            stop = entry * (1 + self._stop_loss_pct / 100)
            tp = entry * (1 - self._take_profit_pct / 100)
            confidence = min(1.0, abs(imbalance))
            signals.append(Signal(
                ticker=ticker, action="sell", confidence=confidence,
                entry_price=entry, stop_loss=stop, take_profit=tp,
                metadata={
                    "imbalance": round(imbalance, 4),
                    "bid_vol": bid_vol, "ask_vol": ask_vol,
                    "spread_pct": round(spread_pct, 4),
                    "max_hold_seconds": self._max_hold_seconds,
                },
            ))

        return signals
