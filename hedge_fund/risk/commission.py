from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class InstrumentType(str, Enum):
    STOCK = "stock"       # TQBR
    FUTURES = "futures"   # RFUD
    BOND = "bond"         # TQCB
    ETF = "etf"           # TQTF


@dataclass
class CommissionBreakdown:
    exchange_fee: float
    broker_fee: float
    clearing_fee: float
    total: float


@dataclass
class CommissionConfig:
    broker_stock_pct: float = 0.06   # 0.06% "Самостоятельный"
    exchange_stock_pct: float = 0.01  # 0.01% MOEX
    clearing_stock_pct: float = 0.01

    broker_futures_per_contract: float = 0.5  # rubles per contract
    exchange_futures_per_contract: float = 1.0
    clearing_futures_per_contract: float = 0.5

    broker_bond_pct: float = 0.06
    exchange_bond_pct: float = 0.01
    clearing_bond_pct: float = 0.01

    broker_etf_pct: float = 0.06
    exchange_etf_pct: float = 0.01
    clearing_etf_pct: float = 0.01


class CommissionCalculator:
    def __init__(self, config: CommissionConfig | None = None) -> None:
        self.config = config or CommissionConfig()

    def calculate(
        self,
        ticker: str,
        side: str,
        qty: int,
        price: float,
        instrument_type: InstrumentType = InstrumentType.STOCK,
    ) -> CommissionBreakdown:
        turnover = qty * price

        if instrument_type == InstrumentType.FUTURES:
            exchange_fee = self.config.exchange_futures_per_contract * qty
            broker_fee = self.config.broker_futures_per_contract * qty
            clearing_fee = self.config.clearing_futures_per_contract * qty
        elif instrument_type == InstrumentType.BOND:
            exchange_fee = turnover * self.config.exchange_bond_pct / 100.0
            broker_fee = turnover * self.config.broker_bond_pct / 100.0
            clearing_fee = turnover * self.config.clearing_bond_pct / 100.0
        elif instrument_type == InstrumentType.ETF:
            exchange_fee = turnover * self.config.exchange_etf_pct / 100.0
            broker_fee = turnover * self.config.broker_etf_pct / 100.0
            clearing_fee = turnover * self.config.clearing_etf_pct / 100.0
        else:
            exchange_fee = turnover * self.config.exchange_stock_pct / 100.0
            broker_fee = turnover * self.config.broker_stock_pct / 100.0
            clearing_fee = turnover * self.config.clearing_stock_pct / 100.0

        return CommissionBreakdown(
            exchange_fee=round(exchange_fee, 2),
            broker_fee=round(broker_fee, 2),
            clearing_fee=round(clearing_fee, 2),
            total=round(exchange_fee + broker_fee + clearing_fee, 2),
        )

    def is_profitable(
        self,
        entry_price: float,
        target_price: float,
        qty: int,
        ticker: str,
        instrument_type: InstrumentType = InstrumentType.STOCK,
    ) -> bool:
        entry_comm = self.calculate(ticker, "buy", qty, entry_price, instrument_type)
        exit_comm = self.calculate(ticker, "sell", qty, target_price, instrument_type)
        gross_pnl = (target_price - entry_price) * qty
        net_pnl = gross_pnl - entry_comm.total - exit_comm.total
        return net_pnl > 0

    def min_profitable_move(
        self,
        ticker: str,
        qty: int,
        price: float,
        instrument_type: InstrumentType = InstrumentType.STOCK,
    ) -> float:
        entry_comm = self.calculate(ticker, "buy", qty, price, instrument_type)
        exit_comm = self.calculate(ticker, "sell", qty, price, instrument_type)
        total_fees = entry_comm.total + exit_comm.total
        if qty == 0:
            return 0.0
        return total_fees / qty
