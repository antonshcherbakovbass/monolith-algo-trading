from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any


@dataclass
class PositionSizeResult:
    recommended_qty: int
    max_loss: float
    position_value: float
    portfolio_fraction: float


@dataclass
class PositionSizerConfig:
    max_position_pct: float = 10.0   # max 10% of portfolio in one position
    default_risk_pct: float = 1.0    # risk 1% of portfolio per trade
    min_qty: int = 1
    lot_size: int = 1


class PositionSizer:
    def __init__(self, config: PositionSizerConfig | None = None) -> None:
        self.config = config or PositionSizerConfig()

    @staticmethod
    def kelly_criterion(win_rate: float, avg_win: float, avg_loss: float) -> float:
        if avg_loss == 0:
            return 0.0
        b = avg_win / avg_loss
        q = 1.0 - win_rate
        kelly = win_rate - q / b
        return max(0.0, kelly)

    def fixed_fractional(self, portfolio_value: float, risk_pct: float = 0.0) -> float:
        if risk_pct <= 0:
            risk_pct = self.config.default_risk_pct
        return portfolio_value * risk_pct / 100.0

    def volatility_based(
        self, portfolio_value: float, atr_value: float, risk_pct: float = 0.0
    ) -> int:
        if atr_value <= 0:
            return 0
        risk_amount = self.fixed_fractional(portfolio_value, risk_pct)
        qty = int(risk_amount / atr_value)
        return max(self.config.min_qty, qty)

    def calculate(
        self,
        ticker: str,
        portfolio_value: float,
        signal_confidence: float,
        volatility: float,
        price: float = 0.0,
    ) -> PositionSizeResult:
        if price <= 0 or portfolio_value <= 0:
            return PositionSizeResult(
                recommended_qty=0, max_loss=0.0, position_value=0.0, portfolio_fraction=0.0
            )

        max_position_value = portfolio_value * self.config.max_position_pct / 100.0
        risk_pct = self.config.default_risk_pct * signal_confidence
        risk_amount = portfolio_value * risk_pct / 100.0

        if volatility > 0:
            qty_by_vol = int(risk_amount / volatility)
        else:
            qty_by_vol = int(risk_amount / (price * 0.02))

        qty_by_max = int(max_position_value / price)
        qty = max(self.config.min_qty, min(qty_by_vol, qty_by_max))

        lot = self.config.lot_size
        qty = (qty // lot) * lot
        if qty < self.config.min_qty:
            qty = self.config.min_qty

        position_value = qty * price
        max_loss = risk_amount
        fraction = position_value / portfolio_value * 100.0

        return PositionSizeResult(
            recommended_qty=qty,
            max_loss=round(max_loss, 2),
            position_value=round(position_value, 2),
            portfolio_fraction=round(fraction, 2),
        )
