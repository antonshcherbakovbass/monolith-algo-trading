from __future__ import annotations
import asyncio
from datetime import datetime
from typing import Any
import numpy as np
from loguru import logger
from .base_agent import BaseAgent, AgentSignal, AgentRole, Action
from ..core.config_loader import get_agent_params


class ScalpingAgent(BaseAgent):
    """High-frequency scalping agent operating on seconds-minutes timeframe."""

    def __init__(self, config: dict, data_feed: Any = None, order_manager: Any = None, db: Any = None):
        agent_cfg = get_agent_params(config, "scalping")
        super().__init__("scalping", AgentRole.SCALPING, config, data_feed, order_manager, db,
                         loop_interval=agent_cfg.get("loop_interval", 1.0))
        self.min_spread_pct = agent_cfg.get("min_spread_pct", 0.05)
        self.max_hold_seconds = agent_cfg.get("max_hold_seconds", 300)
        self.imbalance_threshold = agent_cfg.get("imbalance_threshold", 0.65)
        self.momentum_threshold = agent_cfg.get("momentum_threshold", 0.3)
        self.instruments = config.get("instruments", {}).get("stocks", [])[:5]
        self.tick_buffer: dict[str, list[dict]] = {}
        self.open_scalps: dict[str, dict] = {}

    async def analyze(self) -> list[AgentSignal]:
        signals: list[AgentSignal] = []
        if not self.data_feed:
            return signals
        for ticker in self.instruments:
            try:
                quote = await self.data_feed.get_quote(ticker)
                if not quote:
                    continue
                orderbook = await self.data_feed.get_orderbook(ticker)
                sig = self._analyze_ticker(ticker, quote, orderbook)
                if sig:
                    signals.append(sig)
            except Exception as e:
                self.log.debug(f"Scalp analysis error {ticker}: {e}")
        self._check_exits(signals)
        return signals

    def _analyze_ticker(self, ticker: str, quote: dict, orderbook: dict | None) -> AgentSignal | None:
        bid = quote.get("bid", 0)
        ask = quote.get("ask", 0)
        last = quote.get("last", 0)
        volume = quote.get("volume", 0)
        if not bid or not ask or bid >= ask:
            return None
        spread_pct = (ask - bid) / bid * 100
        if spread_pct < self.min_spread_pct:
            return None
        imbalance = 0.5
        if orderbook:
            bids_vol = sum(level.get("qty", 0) for level in orderbook.get("bids", [])[:5])
            asks_vol = sum(level.get("qty", 0) for level in orderbook.get("asks", [])[:5])
            total = bids_vol + asks_vol
            if total > 0:
                imbalance = bids_vol / total
        buf = self.tick_buffer.setdefault(ticker, [])
        buf.append({"price": last, "volume": volume, "time": datetime.now().timestamp()})
        if len(buf) > 100:
            buf.pop(0)
        momentum = 0.0
        if len(buf) >= 10:
            prices = [t["price"] for t in buf[-10:]]
            if prices[0] > 0:
                momentum = (prices[-1] - prices[0]) / prices[0] * 100
        confidence = 0.0
        action = Action.HOLD
        if imbalance > self.imbalance_threshold and momentum > 0:
            action = Action.BUY
            confidence = min((imbalance - 0.5) * 2 + abs(momentum) * 0.5, 0.95)
        elif imbalance < (1 - self.imbalance_threshold) and momentum < 0:
            action = Action.SELL
            confidence = min((0.5 - imbalance) * 2 + abs(momentum) * 0.5, 0.95)
        elif len(buf) >= 20:
            prices = np.array([t["price"] for t in buf[-20:]])
            vwap = np.average(prices, weights=np.arange(1, len(prices) + 1))
            dev = (last - vwap) / vwap * 100 if vwap > 0 else 0
            if dev < -0.15:
                action = Action.BUY
                confidence = min(abs(dev) * 2, 0.8)
            elif dev > 0.15:
                action = Action.SELL
                confidence = min(abs(dev) * 2, 0.8)
        if action == Action.HOLD or confidence < 0.4:
            return None
        atr_est = np.std([t["price"] for t in buf[-20:]]) if len(buf) >= 20 else last * 0.003
        sl = last - atr_est * 1.5 if action == Action.BUY else last + atr_est * 1.5
        tp = last + atr_est * 2.0 if action == Action.BUY else last - atr_est * 2.0
        return AgentSignal(
            ticker=ticker, action=action, confidence=confidence,
            qty=1, price=last, stop_loss=round(sl, 4), take_profit=round(tp, 4),
            reasoning=f"imbalance={imbalance:.2f} momentum={momentum:.3f}% spread={spread_pct:.3f}%",
            strategy_name="scalping",
        )

    def _check_exits(self, signals: list[AgentSignal]) -> None:
        now = datetime.now().timestamp()
        for ticker, scalp in list(self.open_scalps.items()):
            if now - scalp["entry_time"] > self.max_hold_seconds:
                signals.append(AgentSignal(
                    ticker=ticker, action=Action.CLOSE, confidence=1.0,
                    reasoning=f"Max hold time {self.max_hold_seconds}s exceeded",
                    strategy_name="scalping",
                ))
                del self.open_scalps[ticker]

    async def get_status(self) -> dict:
        return {
            "name": self.name, "running": self._running,
            "open_scalps": len(self.open_scalps),
            "tracked_tickers": len(self.tick_buffer),
            "performance": self.performance,
        }
