"""Strategy adapters for the backtesting engine."""

from __future__ import annotations

from typing import Any, Callable

import pandas as pd

from ..strategies.arbitrage.stat_arb import StatArbStrategy
from ..strategies.base_strategy import Signal
from ..strategies.day_trade.breakout import BreakoutStrategy
from ..strategies.day_trade.mean_reversion import MeanReversionStrategy
from ..strategies.scalping.momentum_scalp import MomentumScalpStrategy

StrategyFn = Callable[[dict[str, pd.DataFrame], int, dict[str, Any]], list[dict]]

STRATEGY_NAMES = ("mean_reversion", "momentum", "breakout", "stat_arb")


def list_strategies() -> list[str]:
    return list(STRATEGY_NAMES)


def get_strategy(name: str) -> StrategyFn:
    key = name.lower().replace("-", "_")
    registry: dict[str, StrategyFn] = {
        "mean_reversion": _make_single_ticker(MeanReversionStrategy),
        "momentum": _make_single_ticker(MomentumScalpStrategy),
        "breakout": _make_single_ticker(BreakoutStrategy),
        "stat_arb": _stat_arb_adapter,
    }
    if key not in registry:
        available = ", ".join(registry)
        raise ValueError(f"Unknown strategy '{name}'. Available: {available}")
    return registry[key]


def _signal_to_backtest(sig: Signal, params: dict[str, Any]) -> dict[str, Any] | None:
    action = sig.action.lower()
    side_map = {"buy": "BUY", "sell": "SELL", "close": "CLOSE"}
    side = side_map.get(action)
    if side is None:
        return None
    return {
        "ticker": sig.ticker,
        "side": side,
        "qty": int(params.get("qty", 10)),
        "strategy": params.get("strategy_name", ""),
    }


def _make_single_ticker(strategy_cls: type) -> StrategyFn:
    def adapter(
        data: dict[str, pd.DataFrame],
        bar_index: int,
        params: dict[str, Any],
    ) -> list[dict]:
        strategy = strategy_cls(params)
        signals: list[dict] = []
        for ticker, df in data.items():
            if len(df) < 30:
                continue
            market_data = {
                "df": df,
                "ticker": ticker,
                "last_price": float(df["close"].iloc[-1]),
            }
            for sig in strategy.generate_signals(market_data):
                converted = _signal_to_backtest(sig, params)
                if converted:
                    converted["strategy"] = strategy.name
                    signals.append(converted)
        return signals

    return adapter


def _stat_arb_adapter(
    data: dict[str, pd.DataFrame],
    bar_index: int,
    params: dict[str, Any],
) -> list[dict]:
    strategy = StatArbStrategy(params)
    prices = {ticker: df["close"].reset_index(drop=True) for ticker, df in data.items()}
    raw = strategy.generate_signals({"prices": prices})
    signals: list[dict] = []
    for sig in raw:
        converted = _signal_to_backtest(sig, params)
        if converted:
            converted["strategy"] = strategy.name
            signals.append(converted)
    return signals
