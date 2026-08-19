"""Backtesting package — engine, optimizer, and CLI."""

from .cli import main, run_backtest
from .engine import BacktestEngine, BacktestResult, BacktestTrade
from .strategy_adapters import get_strategy, list_strategies

__all__ = [
    "BacktestEngine",
    "BacktestResult",
    "BacktestTrade",
    "get_strategy",
    "list_strategies",
    "main",
    "run_backtest",
]
