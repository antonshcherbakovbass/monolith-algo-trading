"""Tests for backtesting CLI and strategy adapters."""
from __future__ import annotations

from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import pytest

from hedge_fund.backtesting.cli import parse_period
from hedge_fund.backtesting.engine import BacktestEngine
from hedge_fund.backtesting.strategy_adapters import get_strategy, list_strategies


def _make_ohlcv(n: int = 200, seed: int = 42) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    base = 100.0 + np.cumsum(rng.normal(0, 0.5, n))
    start = datetime(2024, 1, 1)
    timestamps = [start + timedelta(days=i) for i in range(n)]
    return pd.DataFrame({
        "timestamp": timestamps,
        "open": base * 0.99,
        "high": base * 1.01,
        "low": base * 0.98,
        "close": base,
        "volume": rng.integers(1000, 10000, n),
    })


class TestBacktestCLI:
    def test_parse_period(self):
        start, end = parse_period("2024-01-01:2024-12-31")
        assert start == "2024-01-01"
        assert end == "2024-12-31"

    def test_parse_period_invalid(self):
        with pytest.raises(ValueError):
            parse_period("2024-01-01")

    def test_list_strategies(self):
        names = list_strategies()
        assert "mean_reversion" in names
        assert "momentum" in names

    def test_unknown_strategy(self):
        with pytest.raises(ValueError, match="Unknown strategy"):
            get_strategy("nonexistent")

    def test_mean_reversion_backtest_runs(self):
        data = {"SBER": _make_ohlcv()}
        engine = BacktestEngine(initial_capital=1_000_000)
        strategy_fn = get_strategy("mean_reversion")
        result = engine.run(data, strategy_fn, {"qty": 5, "strategy_name": "mean_reversion"})
        assert result.initial_capital == 1_000_000
        assert result.final_capital > 0
        assert isinstance(result.total_return_pct, float)

    def test_momentum_backtest_runs(self):
        data = {"GAZP": _make_ohlcv(seed=7)}
        engine = BacktestEngine(initial_capital=500_000)
        strategy_fn = get_strategy("momentum")
        result = engine.run(data, strategy_fn, {"qty": 10})
        assert result.total_trades >= 0
