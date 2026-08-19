from __future__ import annotations
from typing import Any
import numpy as np
import pandas as pd
import httpx
from loguru import logger
from .base_agent import BaseAgent, AgentSignal, AgentRole, Action
from ..core.config_loader import get_agent_params


class LongTermAgent(BaseAgent):
    """Long-term investment agent (days to weeks) using fundamentals and trends."""

    def __init__(self, config: dict, data_feed: Any = None, order_manager: Any = None, db: Any = None):
        agent_cfg = get_agent_params(config, "long_term")
        super().__init__("long_term", AgentRole.LONG_TERM, config, data_feed, order_manager, db,
                         loop_interval=agent_cfg.get("loop_interval", 3600.0))
        self.instruments = config.get("instruments", {}).get("stocks", [])
        self.min_hold_days = agent_cfg.get("min_hold_days", 5)
        self.positions: dict[str, dict] = {}
        ai_cfg = config.get("ai", {})
        self.ollama_url = ai_cfg.get("base_url", "http://localhost:11434")
        self.ollama_model = ai_cfg.get("model", "llama3.1")

    async def analyze(self) -> list[AgentSignal]:
        signals: list[AgentSignal] = []
        if not self.data_feed:
            return signals
        for ticker in self.instruments:
            try:
                candles = await self.data_feed.get_candles(ticker, "1d", 200)
                if not candles or len(candles) < 50:
                    continue
                df = pd.DataFrame(candles)
                sig = self._trend_analysis(ticker, df)
                if sig:
                    signals.append(sig)
            except Exception as e:
                self.log.debug(f"Long-term error {ticker}: {e}")
        return signals

    def _trend_analysis(self, ticker: str, df: pd.DataFrame) -> AgentSignal | None:
        close = df["close"].values
        volume = df["volume"].values if "volume" in df else np.ones(len(close))

        ema20 = pd.Series(close).ewm(span=20).mean().iloc[-1]
        ema50 = pd.Series(close).ewm(span=50).mean().iloc[-1]
        ema200 = pd.Series(close).ewm(span=200).mean().iloc[-1] if len(close) >= 200 else ema50

        # ADX approximation
        high = df["high"].values if "high" in df else close * 1.01
        low = df["low"].values if "low" in df else close * 0.99
        tr = np.maximum(high[1:] - low[1:], np.maximum(abs(high[1:] - close[:-1]), abs(low[1:] - close[:-1])))
        atr14 = np.mean(tr[-14:]) if len(tr) >= 14 else np.std(close)
        dm_plus = np.maximum(high[1:] - high[:-1], 0)
        dm_minus = np.maximum(low[:-1] - low[1:], 0)
        dm_plus = np.where(dm_plus > dm_minus, dm_plus, 0)
        dm_minus = np.where(dm_minus > dm_plus, dm_minus, 0)
        di_plus = np.mean(dm_plus[-14:]) / max(atr14, 1e-10) * 100
        di_minus = np.mean(dm_minus[-14:]) / max(atr14, 1e-10) * 100
        adx = abs(di_plus - di_minus) / max(di_plus + di_minus, 1e-10) * 100

        score = 0.0
        reasons = []

        # Golden/Death cross
        if ema20 > ema50 > ema200:
            score += 0.4
            reasons.append("Bullish EMA alignment (20>50>200)")
        elif ema20 < ema50 < ema200:
            score -= 0.4
            reasons.append("Bearish EMA alignment")

        # Strong trend
        if adx > 25:
            if di_plus > di_minus:
                score += 0.3
                reasons.append(f"Strong uptrend ADX={adx:.0f}")
            else:
                score -= 0.3
                reasons.append(f"Strong downtrend ADX={adx:.0f}")

        # Pullback to EMA in uptrend
        if ema20 > ema50 and close[-1] < ema20 and close[-1] > ema50:
            score += 0.2
            reasons.append("Pullback to EMA support")

        # 52-week position
        high_52 = max(close[-min(252, len(close)):])
        low_52 = min(close[-min(252, len(close)):])
        range_pos = (close[-1] - low_52) / max(high_52 - low_52, 1e-10)
        if range_pos < 0.3 and score > 0:
            score += 0.15
            reasons.append(f"Near 52w low ({range_pos:.0%})")

        # Volume trend
        vol_recent = np.mean(volume[-5:])
        vol_avg = np.mean(volume[-20:])
        if vol_recent > vol_avg * 1.3 and score > 0:
            score += 0.1
            reasons.append("Rising volume")

        if abs(score) < 0.35:
            return None

        action = Action.BUY if score > 0 else Action.SELL
        confidence = min(abs(score), 0.9)
        price = close[-1]
        sl = price - atr14 * 3 if action == Action.BUY else price + atr14 * 3
        tp = price + atr14 * 5 if action == Action.BUY else price - atr14 * 5

        return AgentSignal(
            ticker=ticker, action=action, confidence=confidence,
            qty=1, price=price, stop_loss=round(sl, 2), take_profit=round(tp, 2),
            reasoning="; ".join(reasons), strategy_name="trend_following",
        )

    async def get_status(self) -> dict:
        return {
            "name": self.name, "running": self._running,
            "tracked_instruments": len(self.instruments),
            "positions": len(self.positions),
            "performance": self.performance,
        }
