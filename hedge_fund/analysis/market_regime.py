from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional

import numpy as np
import pandas as pd

from .technical import adx, atr, rsi


class MarketRegime(str, Enum):
    TRENDING_UP = "trending_up"
    TRENDING_DOWN = "trending_down"
    RANGING = "ranging"
    HIGH_VOLATILITY = "high_volatility"
    CRASH = "crash"


@dataclass
class RegimeTransition:
    timestamp: datetime
    from_regime: MarketRegime
    to_regime: MarketRegime


@dataclass
class StrategyRecommendation:
    regime: MarketRegime
    strategy_type: str
    description: str
    risk_multiplier: float


class MarketRegimeDetector:
    def __init__(
        self,
        adx_trend_threshold: float = 25.0,
        volatility_lookback: int = 20,
        crash_drawdown_pct: float = -5.0,
        crash_window: int = 5,
    ) -> None:
        self._adx_threshold = adx_trend_threshold
        self._vol_lookback = volatility_lookback
        self._crash_drawdown = crash_drawdown_pct
        self._crash_window = crash_window
        self._history: list[tuple[datetime, MarketRegime]] = []

    def detect(self, df: pd.DataFrame) -> MarketRegime:
        if len(df) < 30:
            return MarketRegime.RANGING

        adx_values = adx(df)
        current_adx = adx_values.iloc[-1]
        rsi_values = rsi(df["close"])
        current_rsi = rsi_values.iloc[-1]
        atr_values = atr(df)

        recent_returns = df["close"].pct_change(self._crash_window).iloc[-1] * 100.0
        if recent_returns <= self._crash_drawdown:
            regime = MarketRegime.CRASH
        else:
            vol_ratio = atr_values.iloc[-1] / atr_values.rolling(self._vol_lookback).mean().iloc[-1] if atr_values.rolling(self._vol_lookback).mean().iloc[-1] > 0 else 1.0
            if vol_ratio > 1.5:
                regime = MarketRegime.HIGH_VOLATILITY
            elif current_adx >= self._adx_threshold:
                ema_20 = df["close"].ewm(span=20, adjust=False).mean()
                if df["close"].iloc[-1] > ema_20.iloc[-1]:
                    regime = MarketRegime.TRENDING_UP
                else:
                    regime = MarketRegime.TRENDING_DOWN
            else:
                regime = MarketRegime.RANGING

        now = datetime.utcnow()
        if df.index.dtype == "datetime64[ns]" or hasattr(df.index[-1], "to_pydatetime"):
            try:
                now = df.index[-1].to_pydatetime()
            except Exception:
                pass

        if self._history and self._history[-1][1] != regime:
            self._history.append((now, regime))
        elif not self._history:
            self._history.append((now, regime))

        return regime

    def get_transitions(self) -> list[RegimeTransition]:
        transitions: list[RegimeTransition] = []
        for i in range(1, len(self._history)):
            transitions.append(
                RegimeTransition(
                    timestamp=self._history[i][0],
                    from_regime=self._history[i - 1][1],
                    to_regime=self._history[i][1],
                )
            )
        return transitions

    def get_regime_history(self) -> list[tuple[datetime, MarketRegime]]:
        return list(self._history)

    @staticmethod
    def get_optimal_strategy(regime: MarketRegime) -> StrategyRecommendation:
        strategies: dict[MarketRegime, StrategyRecommendation] = {
            MarketRegime.TRENDING_UP: StrategyRecommendation(
                regime=MarketRegime.TRENDING_UP,
                strategy_type="trend_following",
                description="Follow the trend with momentum strategies. Use trailing stops. Increase position sizes.",
                risk_multiplier=1.2,
            ),
            MarketRegime.TRENDING_DOWN: StrategyRecommendation(
                regime=MarketRegime.TRENDING_DOWN,
                strategy_type="short_or_hedge",
                description="Short selling or hedging with futures. Reduce long exposure. Consider put options.",
                risk_multiplier=0.7,
            ),
            MarketRegime.RANGING: StrategyRecommendation(
                regime=MarketRegime.RANGING,
                strategy_type="mean_reversion",
                description="Mean reversion at support/resistance levels. Sell at range top, buy at range bottom.",
                risk_multiplier=0.9,
            ),
            MarketRegime.HIGH_VOLATILITY: StrategyRecommendation(
                regime=MarketRegime.HIGH_VOLATILITY,
                strategy_type="volatility_adjusted",
                description="Reduce position sizes. Widen stops. Consider volatility strategies.",
                risk_multiplier=0.5,
            ),
            MarketRegime.CRASH: StrategyRecommendation(
                regime=MarketRegime.CRASH,
                strategy_type="capital_preservation",
                description="Close risky positions. Move to cash. Only take hedging trades.",
                risk_multiplier=0.2,
            ),
        }
        return strategies[regime]
