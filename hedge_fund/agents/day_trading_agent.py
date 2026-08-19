from __future__ import annotations
import asyncio
from typing import Any
import numpy as np
import pandas as pd
from loguru import logger
from .base_agent import BaseAgent, AgentSignal, AgentRole, Action
from ..core.config_loader import get_agent_params


class DayTradingAgent(BaseAgent):
    """Intraday trading agent using technical analysis on multiple timeframes."""

    def __init__(self, config: dict, data_feed: Any = None, order_manager: Any = None, db: Any = None):
        agent_cfg = get_agent_params(config, "day_trading")
        super().__init__("day_trading", AgentRole.DAY_TRADING, config, data_feed, order_manager, db,
                         loop_interval=agent_cfg.get("loop_interval", 60.0))
        self.timeframes = agent_cfg.get("timeframes", ["5m", "15m", "1h"])
        self.instruments = config.get("instruments", {}).get("stocks", [])[:10]
        self.daily_pnl = 0.0
        self.max_daily_loss = config.get("risk", {}).get("max_daily_loss_pct", 2.0)
        self.open_positions: dict[str, dict] = {}
        self.trading_stopped = False

    async def analyze(self) -> list[AgentSignal]:
        signals: list[AgentSignal] = []
        if self.trading_stopped or not self.data_feed:
            return signals
        for ticker in self.instruments:
            try:
                candles_5m = await self.data_feed.get_candles(ticker, "5m", 100)
                candles_15m = await self.data_feed.get_candles(ticker, "15m", 50)
                if not candles_5m or len(candles_5m) < 30:
                    continue
                df = pd.DataFrame(candles_5m)
                sig = self._technical_analysis(ticker, df)
                if sig:
                    signals.append(sig)
            except Exception as e:
                self.log.debug(f"Day trade error {ticker}: {e}")
        return signals

    def _technical_analysis(self, ticker: str, df: pd.DataFrame) -> AgentSignal | None:
        close = df["close"].values
        high = df["high"].values
        low = df["low"].values
        volume = df["volume"].values if "volume" in df else np.ones(len(close))

        # RSI
        deltas = np.diff(close)
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)
        avg_gain = pd.Series(gains).rolling(14).mean().iloc[-1]
        avg_loss = pd.Series(losses).rolling(14).mean().iloc[-1]
        rsi = 100 - (100 / (1 + avg_gain / max(avg_loss, 1e-10)))

        # MACD
        ema12 = pd.Series(close).ewm(span=12).mean()
        ema26 = pd.Series(close).ewm(span=26).mean()
        macd_line = ema12 - ema26
        signal_line = macd_line.ewm(span=9).mean()
        macd_hist = macd_line.iloc[-1] - signal_line.iloc[-1]
        macd_prev = macd_line.iloc[-2] - signal_line.iloc[-2]

        # Bollinger Bands
        sma20 = pd.Series(close).rolling(20).mean().iloc[-1]
        std20 = pd.Series(close).rolling(20).std().iloc[-1]
        bb_upper = sma20 + 2 * std20
        bb_lower = sma20 - 2 * std20
        bb_pos = (close[-1] - bb_lower) / max(bb_upper - bb_lower, 1e-10)

        # EMA trend
        ema20 = pd.Series(close).ewm(span=20).mean().iloc[-1]
        ema50 = pd.Series(close).ewm(span=50).mean().iloc[-1]
        trend_up = ema20 > ema50

        # ATR for stops
        tr = np.maximum(high[1:] - low[1:], np.maximum(abs(high[1:] - close[:-1]), abs(low[1:] - close[:-1])))
        atr = np.mean(tr[-14:]) if len(tr) >= 14 else np.std(close) * 1.5

        # Volume confirmation
        vol_avg = np.mean(volume[-20:]) if len(volume) >= 20 else np.mean(volume)
        vol_ratio = volume[-1] / max(vol_avg, 1) if vol_avg > 0 else 1.0

        score = 0.0
        reasons = []

        # MACD crossover
        if macd_hist > 0 and macd_prev <= 0:
            score += 0.3
            reasons.append("MACD bullish cross")
        elif macd_hist < 0 and macd_prev >= 0:
            score -= 0.3
            reasons.append("MACD bearish cross")

        # RSI
        if rsi < 30:
            score += 0.25
            reasons.append(f"RSI oversold ({rsi:.0f})")
        elif rsi > 70:
            score -= 0.25
            reasons.append(f"RSI overbought ({rsi:.0f})")

        # Bollinger
        if bb_pos < 0.1:
            score += 0.2
            reasons.append("Near BB lower")
        elif bb_pos > 0.9:
            score -= 0.2
            reasons.append("Near BB upper")

        # Trend alignment
        if trend_up and score > 0:
            score += 0.15
            reasons.append("Aligned with uptrend")
        elif not trend_up and score < 0:
            score -= 0.15
            reasons.append("Aligned with downtrend")

        # Volume confirmation
        if vol_ratio > 1.5:
            score *= 1.2
            reasons.append(f"High volume ({vol_ratio:.1f}x)")

        if abs(score) < 0.3:
            return None

        action = Action.BUY if score > 0 else Action.SELL
        confidence = min(abs(score), 0.95)
        price = close[-1]
        sl = price - atr * 2 if action == Action.BUY else price + atr * 2
        tp = price + atr * 3 if action == Action.BUY else price - atr * 3

        return AgentSignal(
            ticker=ticker, action=action, confidence=confidence,
            qty=1, price=price, stop_loss=round(sl, 2), take_profit=round(tp, 2),
            reasoning="; ".join(reasons), strategy_name="day_trading",
        )

    async def get_status(self) -> dict:
        return {
            "name": self.name, "running": self._running,
            "daily_pnl": self.daily_pnl,
            "trading_stopped": self.trading_stopped,
            "open_positions": len(self.open_positions),
            "performance": self.performance,
        }
