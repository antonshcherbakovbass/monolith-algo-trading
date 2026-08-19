from __future__ import annotations
from typing import Any
import numpy as np
import pandas as pd
from loguru import logger
from .base_agent import BaseAgent, AgentSignal, AgentRole, Action
from ..core.config_loader import get_agent_params
from ..ml.inference import ModelRegistry


class QuantAgent(BaseAgent):
    """Quantitative agent: statistical arbitrage, pair trading, anomaly detection."""

    def __init__(self, config: dict, data_feed: Any = None, order_manager: Any = None, db: Any = None):
        agent_cfg = get_agent_params(config, "quant")
        super().__init__("quant", AgentRole.QUANT, config, data_feed, order_manager, db,
                         loop_interval=agent_cfg.get("loop_interval", 300.0))
        self.pairs = agent_cfg.get("pairs", [
            ["SBER", "VTBR"], ["GAZP", "ROSN"], ["LKOH", "TATN"],
            ["NLMK", "CHMF"], ["GMKN", "RUAL"],
        ])
        self.zscore_entry = agent_cfg.get("zscore_entry", 2.0)
        self.zscore_exit = agent_cfg.get("zscore_exit", 0.5)
        self.lookback = agent_cfg.get("lookback", 60)
        self.active_pairs: dict[str, dict] = {}
        self.spread_history: dict[str, list[float]] = {}
        ml_cfg = config.get("ml", {})
        self._ml = ModelRegistry(
            ml_cfg.get("models_dir"),
            drift_psi_threshold=float(ml_cfg.get("drift_psi_threshold", 0.2)),
        )
        self._ml_enabled = agent_cfg.get("ml_enabled", True)

    async def analyze(self) -> list[AgentSignal]:
        signals: list[AgentSignal] = []
        if not self.data_feed:
            return signals
        for pair in self.pairs:
            if len(pair) != 2:
                continue
            try:
                candles_a = await self.data_feed.get_candles(pair[0], "15m", self.lookback)
                candles_b = await self.data_feed.get_candles(pair[1], "15m", self.lookback)
                if not candles_a or not candles_b:
                    continue
                if len(candles_a) < 30 or len(candles_b) < 30:
                    continue
                min_len = min(len(candles_a), len(candles_b))
                prices_a = np.array([c["close"] for c in candles_a[-min_len:]], dtype=float)
                prices_b = np.array([c["close"] for c in candles_b[-min_len:]], dtype=float)
                pair_signals = self._analyze_pair(pair[0], pair[1], prices_a, prices_b)
                signals.extend(pair_signals)
            except Exception as e:
                self.log.debug(f"Pair analysis error {pair}: {e}")

        for ticker in (self.config.get("instruments", {}).get("stocks", [])[:10]):
            try:
                candles = await self.data_feed.get_candles(ticker, "5m", 100)
                if candles and len(candles) >= 50:
                    prices = np.array([c["close"] for c in candles], dtype=float)
                    volumes = np.array([c.get("volume", 1) for c in candles], dtype=float)
                    anomaly = self._detect_anomaly(ticker, prices, volumes)
                    if anomaly:
                        signals.append(anomaly)
            except Exception as e:
                self.log.debug(f"Anomaly detection error {ticker}: {e}")

        if self._ml_enabled and self._ml.has_models:
            signals.extend(await self._ml_signals())

        return signals

    async def _ml_signals(self) -> list[AgentSignal]:
        results: list[AgentSignal] = []
        tickers = self.config.get("instruments", {}).get("stocks", [])[:8]
        for ticker in tickers:
            try:
                candles = await self.data_feed.get_candles(ticker, "5m", 100)
                if not candles:
                    continue
                prediction = self._ml.predict_ticker(ticker, candles)
                if not prediction:
                    continue
                signal_tuple = self._ml.signal_from_prediction(prediction)
                if not signal_tuple:
                    continue
                action_str, confidence, reasoning = signal_tuple
                action = Action.BUY if action_str == "BUY" else Action.SELL
                results.append(AgentSignal(
                    ticker=ticker,
                    action=action,
                    confidence=confidence,
                    price=prediction.get("price", 0),
                    reasoning=reasoning,
                    strategy_name="ml_inference",
                    metadata={"ml": prediction},
                ))
            except Exception as e:
                self.log.debug(f"ML inference error {ticker}: {e}")
        return results

    def _analyze_pair(self, ticker_a: str, ticker_b: str, prices_a: np.ndarray, prices_b: np.ndarray) -> list[AgentSignal]:
        signals = []
        pair_key = f"{ticker_a}/{ticker_b}"
        if len(prices_a) < 20 or len(prices_b) < 20:
            return signals

        # Compute hedge ratio via OLS
        mean_a, mean_b = np.mean(prices_a), np.mean(prices_b)
        cov = np.sum((prices_a - mean_a) * (prices_b - mean_b))
        var_b = np.sum((prices_b - mean_b) ** 2)
        hedge_ratio = cov / max(var_b, 1e-10)

        spread = prices_a - hedge_ratio * prices_b
        spread_mean = np.mean(spread)
        spread_std = np.std(spread)
        if spread_std < 1e-10:
            return signals
        zscore = (spread[-1] - spread_mean) / spread_std

        hist = self.spread_history.setdefault(pair_key, [])
        hist.append(zscore)
        if len(hist) > 500:
            self.spread_history[pair_key] = hist[-300:]

        # Cointegration check (simplified ADF)
        spread_diff = np.diff(spread)
        if len(spread_diff) < 10:
            return signals
        corr_level_diff = np.corrcoef(spread[:-1], spread_diff)[0, 1] if np.std(spread[:-1]) > 0 else 0
        is_cointegrated = abs(corr_level_diff) > 0.3

        if not is_cointegrated:
            return signals

        confidence = min(abs(zscore) / 3.0, 0.9)

        if zscore > self.zscore_entry and pair_key not in self.active_pairs:
            # Spread too high: short A, long B
            signals.append(AgentSignal(
                ticker=ticker_a, action=Action.SELL, confidence=confidence,
                price=prices_a[-1], reasoning=f"Stat arb {pair_key} zscore={zscore:.2f} SHORT",
                strategy_name="stat_arb",
            ))
            signals.append(AgentSignal(
                ticker=ticker_b, action=Action.BUY, confidence=confidence,
                price=prices_b[-1], reasoning=f"Stat arb {pair_key} zscore={zscore:.2f} LONG",
                strategy_name="stat_arb",
            ))
            self.active_pairs[pair_key] = {"direction": "short_spread", "entry_zscore": zscore}

        elif zscore < -self.zscore_entry and pair_key not in self.active_pairs:
            signals.append(AgentSignal(
                ticker=ticker_a, action=Action.BUY, confidence=confidence,
                price=prices_a[-1], reasoning=f"Stat arb {pair_key} zscore={zscore:.2f} LONG",
                strategy_name="stat_arb",
            ))
            signals.append(AgentSignal(
                ticker=ticker_b, action=Action.SELL, confidence=confidence,
                price=prices_b[-1], reasoning=f"Stat arb {pair_key} zscore={zscore:.2f} SHORT",
                strategy_name="stat_arb",
            ))
            self.active_pairs[pair_key] = {"direction": "long_spread", "entry_zscore": zscore}

        elif pair_key in self.active_pairs and abs(zscore) < self.zscore_exit:
            signals.append(AgentSignal(
                ticker=ticker_a, action=Action.CLOSE, confidence=0.8,
                reasoning=f"Stat arb {pair_key} exit zscore={zscore:.2f}",
                strategy_name="stat_arb",
            ))
            signals.append(AgentSignal(
                ticker=ticker_b, action=Action.CLOSE, confidence=0.8,
                reasoning=f"Stat arb {pair_key} exit zscore={zscore:.2f}",
                strategy_name="stat_arb",
            ))
            del self.active_pairs[pair_key]

        return signals

    def _detect_anomaly(self, ticker: str, prices: np.ndarray, volumes: np.ndarray) -> AgentSignal | None:
        returns = np.diff(prices) / prices[:-1]
        vol_mean = np.mean(volumes[-20:])
        vol_std = np.std(volumes[-20:])
        price_std = np.std(returns[-20:])

        vol_zscore = (volumes[-1] - vol_mean) / max(vol_std, 1e-10)
        last_return = returns[-1]
        return_zscore = last_return / max(price_std, 1e-10)

        # Anomaly: huge volume but small price move (accumulation/distribution)
        if vol_zscore > 3.0 and abs(return_zscore) < 0.5:
            # Determine direction from recent order flow proxy
            recent_returns = returns[-5:]
            direction = np.sum(recent_returns)
            if abs(direction) > price_std * 0.5:
                action = Action.BUY if direction > 0 else Action.SELL
                return AgentSignal(
                    ticker=ticker, action=action,
                    confidence=min(vol_zscore / 5.0, 0.7),
                    price=prices[-1],
                    reasoning=f"Anomaly: vol_z={vol_zscore:.1f} ret_z={return_zscore:.2f} (hidden accumulation)",
                    strategy_name="anomaly_detection",
                )

        # Anomaly: extreme move that might revert
        if abs(return_zscore) > 3.0 and vol_zscore < 1.5:
            action = Action.SELL if return_zscore > 3 else Action.BUY
            return AgentSignal(
                ticker=ticker, action=action,
                confidence=min(abs(return_zscore) / 5.0, 0.65),
                price=prices[-1],
                reasoning=f"Anomaly: extreme move ret_z={return_zscore:.2f} low vol (likely revert)",
                strategy_name="anomaly_detection",
            )
        return None

    def reload_ml_models(self) -> bool:
        """Reload ML models from disk (called after scheduled retrain)."""
        return self._ml.reload()

    async def get_status(self) -> dict:
        return {
            "name": self.name, "running": self._running,
            "active_pairs": len(self.active_pairs),
            "tracked_pairs": len(self.pairs),
            "ml_models_loaded": self._ml.has_models,
            "performance": self.performance,
        }
