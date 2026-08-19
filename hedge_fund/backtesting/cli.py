"""Backtest CLI — run strategy simulations on historical MOEX data.

Usage:
    python -m hedge_fund.backtesting --strategy mean_reversion --tickers SBER GAZP \\
        --period 2024-01-01:2024-12-31

    python -m hedge_fund.backtesting --strategy momentum --tickers SBER \\
        --start-date 2023-06-01 --end-date 2024-06-01 --capital 500000
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from ..data.moex_loader import MOEXDataLoader
from ..utils.logger import get_logger
from .engine import BacktestEngine
from .strategy_adapters import get_strategy, list_strategies

log = get_logger("backtesting.cli")


def parse_period(period: str | None) -> tuple[str | None, str | None]:
    if not period:
        return None, None
    if ":" not in period:
        raise ValueError(f"Invalid period format '{period}', expected YYYY-MM-DD:YYYY-MM-DD")
    start, end = period.split(":", 1)
    return start.strip(), end.strip()


def normalize_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Ensure columns expected by BacktestEngine."""
    out = df.copy()
    if "timestamp" not in out.columns and "datetime" in out.columns:
        out = out.rename(columns={"datetime": "timestamp"})
    if "timestamp" in out.columns:
        out["timestamp"] = pd.to_datetime(out["timestamp"])
    required = {"open", "high", "low", "close", "volume"}
    missing = required - set(out.columns)
    if missing:
        raise ValueError(f"DataFrame missing columns: {sorted(missing)}")
    return out.reset_index(drop=True)


async def load_market_data(
    tickers: list[str],
    start_date: str,
    end_date: str | None,
) -> dict[str, pd.DataFrame]:
    loader = MOEXDataLoader()
    data: dict[str, pd.DataFrame] = {}
    for ticker in tickers:
        log.info("Loading {} ({} → {})", ticker, start_date, end_date or "now")
        df = await loader.fetch_candles(
            ticker,
            start_date=start_date,
            end_date=end_date,
        )
        if df.empty:
            log.warning("No data for {}", ticker)
            continue
        data[ticker] = normalize_dataframe(df)
        log.info("  {} bars loaded", len(data[ticker]))
    return data


async def run_backtest(
    strategy: str,
    tickers: list[str],
    start_date: str = "2022-01-01",
    end_date: str | None = None,
    capital: float = 1_000_000.0,
    qty: int = 10,
    commission_pct: float = 0.08,
    slippage_pct: float = 0.02,
    output: str | None = None,
    strategy_params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    data = await load_market_data(tickers, start_date, end_date)
    if not data:
        raise RuntimeError("No market data loaded for backtest")

    strategy_fn = get_strategy(strategy)
    params = dict(strategy_params or {})
    params.setdefault("qty", qty)
    params.setdefault("strategy_name", strategy)

    engine = BacktestEngine(
        initial_capital=capital,
        commission_pct=commission_pct,
        slippage_pct=slippage_pct,
    )
    result = engine.run(data, strategy_fn, params)

    summary = result.summary()
    print(summary)

    payload = {
        "strategy": strategy,
        "tickers": tickers,
        "start_date": result.start_date.isoformat(),
        "end_date": result.end_date.isoformat(),
        "initial_capital": result.initial_capital,
        "final_capital": result.final_capital,
        "total_return_pct": result.total_return_pct,
        "annual_return_pct": result.annual_return_pct,
        "sharpe_ratio": result.sharpe_ratio,
        "max_drawdown_pct": result.max_drawdown_pct,
        "total_trades": result.total_trades,
        "win_rate": result.win_rate,
        "profit_factor": result.profit_factor,
        "monthly_returns": result.monthly_returns,
    }

    if output:
        out_path = Path(output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        log.info("Report saved to {}", out_path)

    return payload


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run MOEX strategy backtests on historical data",
    )
    parser.add_argument(
        "--strategy",
        required=True,
        choices=list_strategies(),
        help="Strategy to backtest",
    )
    parser.add_argument(
        "--tickers",
        nargs="+",
        default=["SBER", "GAZP"],
        help="Ticker symbols (default: SBER GAZP)",
    )
    parser.add_argument(
        "--period",
        default=None,
        help="Date range as START:END (e.g. 2024-01-01:2024-12-31)",
    )
    parser.add_argument("--start-date", default="2022-01-01", help="Start date YYYY-MM-DD")
    parser.add_argument("--end-date", default=None, help="End date YYYY-MM-DD")
    parser.add_argument("--capital", type=float, default=1_000_000.0, help="Initial capital RUB")
    parser.add_argument("--qty", type=int, default=10, help="Shares per signal")
    parser.add_argument("--commission", type=float, default=0.08, help="Commission %%")
    parser.add_argument("--slippage", type=float, default=0.02, help="Slippage %%")
    parser.add_argument("--output", "-o", default=None, help="Save JSON report to path")
    parser.add_argument(
        "--list-strategies",
        action="store_true",
        help="List available strategies and exit",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.list_strategies:
        for name in list_strategies():
            print(name)
        return 0

    start_date = args.start_date
    end_date = args.end_date
    if args.period:
        try:
            p_start, p_end = parse_period(args.period)
            start_date = p_start or start_date
            end_date = p_end or end_date
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            return 2

    try:
        datetime.strptime(start_date, "%Y-%m-%d")
        if end_date:
            datetime.strptime(end_date, "%Y-%m-%d")
    except ValueError:
        print("Dates must be in YYYY-MM-DD format", file=sys.stderr)
        return 2

    try:
        asyncio.run(
            run_backtest(
                strategy=args.strategy,
                tickers=args.tickers,
                start_date=start_date,
                end_date=end_date,
                capital=args.capital,
                qty=args.qty,
                commission_pct=args.commission,
                slippage_pct=args.slippage,
                output=args.output,
            )
        )
    except Exception as exc:
        log.error("Backtest failed: {}", exc)
        print(f"Backtest failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
