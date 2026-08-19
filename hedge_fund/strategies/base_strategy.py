"""Base strategy interface and shared types."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

from ..utils.logger import get_logger

log = get_logger("strategy.base")


@dataclass
class Signal:
    ticker: str
    action: str  # "buy" | "sell" | "close"
    confidence: float  # 0.0–1.0
    entry_price: float
    stop_loss: float
    take_profit: float
    qty: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class BacktestResult:
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    total_pnl: float = 0.0
    max_drawdown: float = 0.0
    sharpe_ratio: float = 0.0
    win_rate: float = 0.0
    avg_trade_pnl: float = 0.0
    trades: list[dict[str, Any]] = field(default_factory=list)


class BaseStrategy(ABC):
    """Abstract base for all trading strategies."""

    def __init__(self, name: str, config: dict[str, Any] | None = None) -> None:
        self.name = name
        self._config = config or {}
        self._log = get_logger(f"strategy.{name}")

    @abstractmethod
    def generate_signals(self, market_data: dict[str, Any]) -> list[Signal]:
        """Produce trading signals from current market data."""

    def validate_signal(self, signal: Signal) -> bool:
        """Basic sanity checks on a signal before submission."""
        if signal.confidence < 0 or signal.confidence > 1:
            self._log.warning("Invalid confidence {:.2f} for {}", signal.confidence, signal.ticker)
            return False
        if signal.entry_price <= 0:
            self._log.warning("Invalid entry price {:.4f} for {}", signal.entry_price, signal.ticker)
            return False
        if signal.stop_loss <= 0:
            self._log.warning("Invalid stop loss for {}", signal.ticker)
            return False
        if signal.action == "buy" and signal.stop_loss >= signal.entry_price:
            self._log.warning("Stop loss above entry for buy on {}", signal.ticker)
            return False
        if signal.action == "sell" and signal.stop_loss <= signal.entry_price:
            self._log.warning("Stop loss below entry for sell on {}", signal.ticker)
            return False
        return True

    def backtest(self, data: pd.DataFrame) -> BacktestResult:
        """Simple vectorised backtest over historical OHLCV data."""
        result = BacktestResult()
        equity = 0.0
        peak = 0.0
        max_dd = 0.0

        for i in range(1, len(data)):
            chunk = data.iloc[: i + 1]
            market_data = {
                "df": chunk,
                "ticker": data.attrs.get("ticker", "UNKNOWN"),
                "last_price": float(chunk["close"].iloc[-1]),
            }
            signals = self.generate_signals(market_data)
            for sig in signals:
                if not self.validate_signal(sig):
                    continue
                exit_price = float(data["close"].iloc[min(i + 5, len(data) - 1)])
                pnl = (exit_price - sig.entry_price) * sig.qty if sig.action == "buy" else (sig.entry_price - exit_price) * sig.qty
                equity += pnl
                peak = max(peak, equity)
                dd = peak - equity
                max_dd = max(max_dd, dd)

                result.total_trades += 1
                if pnl > 0:
                    result.winning_trades += 1
                else:
                    result.losing_trades += 1
                result.total_pnl += pnl
                result.trades.append({
                    "entry": sig.entry_price, "exit": exit_price,
                    "pnl": pnl, "action": sig.action,
                })

        result.max_drawdown = max_dd
        if result.total_trades > 0:
            result.win_rate = result.winning_trades / result.total_trades
            result.avg_trade_pnl = result.total_pnl / result.total_trades
            pnls = [t["pnl"] for t in result.trades]
            if np.std(pnls) > 0:
                result.sharpe_ratio = float(np.mean(pnls) / np.std(pnls) * np.sqrt(252))
        return result
