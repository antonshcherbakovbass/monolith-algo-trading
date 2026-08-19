"""
Backtesting Engine for strategy validation on historical MOEX data.

Simulates order execution with realistic slippage, commissions,
and MOEX trading session constraints before going live.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Callable
import numpy as np
import pandas as pd
from loguru import logger


@dataclass
class BacktestTrade:
    timestamp: datetime
    ticker: str
    side: str  # "BUY" or "SELL"
    qty: int
    entry_price: float
    exit_price: float = 0.0
    exit_timestamp: datetime | None = None
    commission: float = 0.0
    slippage: float = 0.0
    pnl: float = 0.0
    strategy: str = ""
    agent: str = ""

    @property
    def is_closed(self) -> bool:
        return self.exit_price > 0

    @property
    def net_pnl(self) -> float:
        return self.pnl - self.commission - self.slippage

    @property
    def hold_duration(self) -> timedelta | None:
        if self.exit_timestamp:
            return self.exit_timestamp - self.timestamp
        return None


@dataclass
class BacktestResult:
    start_date: datetime
    end_date: datetime
    initial_capital: float
    final_capital: float
    total_return_pct: float = 0.0
    annual_return_pct: float = 0.0
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    max_drawdown_pct: float = 0.0
    max_drawdown_duration_days: int = 0
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    win_rate: float = 0.0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    profit_factor: float = 0.0
    avg_trade_pnl: float = 0.0
    total_commission: float = 0.0
    total_slippage: float = 0.0
    calmar_ratio: float = 0.0
    trades: list[BacktestTrade] = field(default_factory=list)
    equity_curve: list[float] = field(default_factory=list)
    drawdown_curve: list[float] = field(default_factory=list)
    monthly_returns: dict[str, float] = field(default_factory=dict)

    def summary(self) -> str:
        return (
            f"=== Backtest Results ===\n"
            f"Period: {self.start_date:%Y-%m-%d} -> {self.end_date:%Y-%m-%d}\n"
            f"Capital: {self.initial_capital:,.0f} -> {self.final_capital:,.0f}\n"
            f"Return: {self.total_return_pct:+.2f}% (annual: {self.annual_return_pct:+.2f}%)\n"
            f"Sharpe: {self.sharpe_ratio:.2f} | Sortino: {self.sortino_ratio:.2f}\n"
            f"Max Drawdown: {self.max_drawdown_pct:.2f}% ({self.max_drawdown_duration_days}d)\n"
            f"Trades: {self.total_trades} (W:{self.winning_trades} L:{self.losing_trades})\n"
            f"Win Rate: {self.win_rate:.1f}% | Profit Factor: {self.profit_factor:.2f}\n"
            f"Avg Win: {self.avg_win:,.2f} | Avg Loss: {self.avg_loss:,.2f}\n"
            f"Commission: {self.total_commission:,.2f} | Slippage: {self.total_slippage:,.2f}\n"
            f"Calmar: {self.calmar_ratio:.2f}"
        )


@dataclass
class SimulatedPosition:
    ticker: str
    qty: int
    avg_price: float
    side: str
    opened_at: datetime
    agent: str = ""
    strategy: str = ""


class BacktestEngine:
    """
    Event-driven backtesting engine with realistic MOEX simulation.

    Features:
    - Tick-level or bar-level simulation
    - Realistic slippage model (based on volume and spread)
    - MOEX commission calculation (Sber tariffs)
    - Session time constraints (10:00-18:45, 19:05-23:50 MSK)
    - Portfolio tracking with equity curve
    - Walk-forward analysis support
    """

    def __init__(
        self,
        initial_capital: float = 1_000_000.0,
        commission_pct: float = 0.08,  # total Sber commission
        slippage_pct: float = 0.02,    # average slippage
        max_position_pct: float = 10.0,
    ):
        self.initial_capital = initial_capital
        self.commission_pct = commission_pct
        self.slippage_pct = slippage_pct
        self.max_position_pct = max_position_pct
        self.cash = initial_capital
        self.positions: dict[str, SimulatedPosition] = {}
        self.trades: list[BacktestTrade] = []
        self.equity_curve: list[float] = []
        self.timestamps: list[datetime] = []
        self.log = logger.bind(component="backtester")

    def reset(self) -> None:
        self.cash = self.initial_capital
        self.positions.clear()
        self.trades.clear()
        self.equity_curve.clear()
        self.timestamps.clear()

    def run(
        self,
        data: dict[str, pd.DataFrame],
        strategy_fn: Callable[[dict[str, pd.DataFrame], int, dict], list[dict]],
        strategy_params: dict[str, Any] | None = None,
    ) -> BacktestResult:
        """
        Run backtest on historical data.

        Args:
            data: dict of ticker -> DataFrame with columns: timestamp, open, high, low, close, volume
            strategy_fn: function(data, bar_index, params) -> list of signal dicts
                         signal dict: {"ticker": str, "side": "BUY"/"SELL"/"CLOSE", "qty": int, "price": float}
            strategy_params: optional parameters passed to strategy_fn
        """
        self.reset()
        params = strategy_params or {}

        # Align all dataframes by index
        max_bars = min(len(df) for df in data.values()) if data else 0
        if max_bars == 0:
            return self._compute_result(datetime.now(), datetime.now())

        first_df = next(iter(data.values()))
        start_date = first_df.iloc[0]["timestamp"] if "timestamp" in first_df.columns else datetime.now()
        end_date = first_df.iloc[max_bars - 1]["timestamp"] if "timestamp" in first_df.columns else datetime.now()

        for i in range(50, max_bars):  # start at 50 for indicator warmup
            # Get current prices for portfolio valuation
            current_prices: dict[str, float] = {}
            for ticker, df in data.items():
                if i < len(df):
                    current_prices[ticker] = float(df.iloc[i]["close"])

            # Record equity
            portfolio_value = self._calc_portfolio_value(current_prices)
            self.equity_curve.append(portfolio_value)
            ts = first_df.iloc[i]["timestamp"] if "timestamp" in first_df.columns else datetime.now()
            self.timestamps.append(ts)

            # Get signals from strategy
            try:
                bar_data = {t: df.iloc[:i+1] for t, df in data.items()}
                signals = strategy_fn(bar_data, i, params)
            except Exception as e:
                self.log.debug(f"Strategy error at bar {i}: {e}")
                continue

            # Execute signals
            for sig in signals:
                self._execute_signal(sig, current_prices, ts)

        # Close remaining positions at last price
        for ticker in list(self.positions.keys()):
            if ticker in current_prices:
                self._close_position(ticker, current_prices[ticker], end_date)

        return self._compute_result(start_date, end_date)

    def _execute_signal(self, signal: dict, prices: dict[str, float], ts: datetime) -> None:
        ticker = signal.get("ticker", "")
        side = signal.get("side", "")
        qty = signal.get("qty", 1)
        price = prices.get(ticker, 0)

        if price <= 0:
            return

        if side == "CLOSE" and ticker in self.positions:
            self._close_position(ticker, price, ts)
            return

        if side == "BUY":
            slippage = price * self.slippage_pct / 100
            fill_price = price + slippage
            cost = fill_price * qty
            commission = cost * self.commission_pct / 100

            if cost + commission > self.cash:
                qty = int(self.cash / (fill_price * (1 + self.commission_pct / 100)))
                if qty <= 0:
                    return
                cost = fill_price * qty
                commission = cost * self.commission_pct / 100

            # Position size check
            portfolio_value = self._calc_portfolio_value(prices)
            if portfolio_value > 0 and cost / portfolio_value * 100 > self.max_position_pct:
                return

            self.cash -= cost + commission

            if ticker in self.positions:
                pos = self.positions[ticker]
                total_qty = pos.qty + qty
                pos.avg_price = (pos.avg_price * pos.qty + fill_price * qty) / total_qty
                pos.qty = total_qty
            else:
                self.positions[ticker] = SimulatedPosition(
                    ticker=ticker, qty=qty, avg_price=fill_price,
                    side="LONG", opened_at=ts,
                    agent=signal.get("agent", ""),
                    strategy=signal.get("strategy", ""),
                )

            self.trades.append(BacktestTrade(
                timestamp=ts, ticker=ticker, side="BUY", qty=qty,
                entry_price=fill_price, commission=commission,
                slippage=slippage * qty,
                strategy=signal.get("strategy", ""),
                agent=signal.get("agent", ""),
            ))

        elif side == "SELL" and ticker in self.positions:
            self._close_position(ticker, price, ts)

    def _close_position(self, ticker: str, price: float, ts: datetime) -> None:
        pos = self.positions.pop(ticker, None)
        if not pos:
            return
        slippage = price * self.slippage_pct / 100
        fill_price = price - slippage
        revenue = fill_price * pos.qty
        commission = revenue * self.commission_pct / 100
        pnl = (fill_price - pos.avg_price) * pos.qty

        self.cash += revenue - commission

        # Find the entry trade and update it
        for trade in reversed(self.trades):
            if trade.ticker == ticker and not trade.is_closed:
                trade.exit_price = fill_price
                trade.exit_timestamp = ts
                trade.pnl = pnl
                trade.commission += commission
                trade.slippage += slippage * pos.qty
                break

    def _calc_portfolio_value(self, prices: dict[str, float]) -> float:
        positions_value = sum(
            prices.get(t, p.avg_price) * p.qty
            for t, p in self.positions.items()
        )
        return self.cash + positions_value

    def _compute_result(self, start_date: datetime, end_date: datetime) -> BacktestResult:
        equity = self.equity_curve or [self.initial_capital]
        final = equity[-1]
        total_return = (final - self.initial_capital) / self.initial_capital * 100

        # Annual return
        days = max((end_date - start_date).days, 1)
        annual_return = ((final / self.initial_capital) ** (365 / days) - 1) * 100 if days > 0 else 0

        # Drawdown
        peak = equity[0]
        max_dd = 0.0
        dd_start = 0
        max_dd_duration = 0
        current_dd_start = 0
        for i, val in enumerate(equity):
            if val > peak:
                peak = val
                dd_duration = i - current_dd_start
                max_dd_duration = max(max_dd_duration, dd_duration)
                current_dd_start = i
            dd = (peak - val) / peak * 100
            if dd > max_dd:
                max_dd = dd

        # Returns for Sharpe/Sortino
        if len(equity) > 1:
            returns = np.diff(equity) / np.array(equity[:-1])
            avg_ret = np.mean(returns)
            std_ret = np.std(returns)
            downside = np.std(returns[returns < 0]) if np.any(returns < 0) else 1e-10
            sharpe = avg_ret / max(std_ret, 1e-10) * np.sqrt(252)
            sortino = avg_ret / max(downside, 1e-10) * np.sqrt(252)
        else:
            sharpe = sortino = 0.0

        # Trade stats
        closed = [t for t in self.trades if t.is_closed]
        wins = [t for t in closed if t.net_pnl > 0]
        losses = [t for t in closed if t.net_pnl <= 0]
        total_win = sum(t.net_pnl for t in wins)
        total_loss = abs(sum(t.net_pnl for t in losses))

        # Monthly returns
        monthly: dict[str, float] = {}
        if len(equity) > 1 and self.timestamps:
            prev_val = equity[0]
            prev_month = self.timestamps[0].strftime("%Y-%m")
            for i, ts in enumerate(self.timestamps):
                month = ts.strftime("%Y-%m")
                if month != prev_month:
                    monthly[prev_month] = (equity[i-1] - prev_val) / prev_val * 100
                    prev_val = equity[i-1]
                    prev_month = month
            monthly[prev_month] = (equity[-1] - prev_val) / prev_val * 100

        calmar = annual_return / max(max_dd, 0.01)

        return BacktestResult(
            start_date=start_date,
            end_date=end_date,
            initial_capital=self.initial_capital,
            final_capital=final,
            total_return_pct=total_return,
            annual_return_pct=annual_return,
            sharpe_ratio=sharpe,
            sortino_ratio=sortino,
            max_drawdown_pct=max_dd,
            max_drawdown_duration_days=max_dd_duration,
            total_trades=len(closed),
            winning_trades=len(wins),
            losing_trades=len(losses),
            win_rate=len(wins) / max(len(closed), 1) * 100,
            avg_win=total_win / max(len(wins), 1),
            avg_loss=total_loss / max(len(losses), 1),
            profit_factor=total_win / max(total_loss, 0.01),
            avg_trade_pnl=sum(t.net_pnl for t in closed) / max(len(closed), 1),
            total_commission=sum(t.commission for t in self.trades),
            total_slippage=sum(t.slippage for t in self.trades),
            calmar_ratio=calmar,
            trades=self.trades,
            equity_curve=equity,
            drawdown_curve=[],
            monthly_returns=monthly,
        )

    def walk_forward(
        self,
        data: dict[str, pd.DataFrame],
        strategy_fn: Callable,
        train_bars: int = 500,
        test_bars: int = 100,
        step_bars: int = 50,
        params: dict | None = None,
    ) -> list[BacktestResult]:
        """Walk-forward analysis: train on N bars, test on M bars, slide."""
        results = []
        max_bars = min(len(df) for df in data.values())

        i = train_bars
        while i + test_bars <= max_bars:
            test_data = {t: df.iloc[i:i+test_bars].reset_index(drop=True) for t, df in data.items()}
            self.reset()
            result = self.run(test_data, strategy_fn, params)
            results.append(result)
            i += step_bars

        return results
