from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional, Sequence

from ..storage.database import Database, PositionRepository, PortfolioRepository, OrderRepository


@dataclass
class RiskCheckResult:
    approved: bool
    reasons: list[str] = field(default_factory=list)


@dataclass
class RiskReport:
    total_exposure: float
    cash_available: float
    max_drawdown_current: float
    daily_pnl: float
    open_positions_count: int
    largest_position_pct: float
    risk_utilization_pct: float
    warnings: list[str] = field(default_factory=list)


@dataclass
class CloseOrder:
    ticker: str
    side: str
    qty: int


@dataclass
class RiskLimitsConfig:
    max_drawdown_pct: float = 5.0
    max_position_concentration_pct: float = 15.0
    max_daily_loss: float = 50000.0
    max_open_positions: int = 10
    max_total_exposure_pct: float = 90.0
    max_correlation_exposure: float = 0.4
    portfolio_value: float = 1_000_000.0


class RiskLimits:
    def __init__(self, config: RiskLimitsConfig, db: Database) -> None:
        self.config = config
        self.db = db
        self._position_repo = PositionRepository(db)
        self._portfolio_repo = PortfolioRepository(db)
        self._order_repo = OrderRepository(db)
        self._current_exposure: float = 0.0
        self._current_drawdown: float = 0.0
        self._daily_pnl: float = 0.0
        self._positions: list[Any] = []

    async def update_state(self) -> None:
        self._positions = list(await self._position_repo.get_all_positions())
        self._current_exposure = sum(abs(p.qty * p.current_price) for p in self._positions)
        self._current_drawdown = await self._portfolio_repo.get_drawdown()

        snapshots = await self._portfolio_repo.get_history(limit=1)
        if snapshots:
            self._daily_pnl = snapshots[0].daily_pnl

    async def check_order(self, order: Any) -> RiskCheckResult:
        await self.update_state()
        reasons: list[str] = []

        if self._current_drawdown >= self.config.max_drawdown_pct:
            reasons.append(
                f"Max drawdown exceeded: {self._current_drawdown:.2f}% >= {self.config.max_drawdown_pct}%"
            )

        if abs(self._daily_pnl) >= self.config.max_daily_loss and self._daily_pnl < 0:
            reasons.append(
                f"Daily loss limit exceeded: {self._daily_pnl:.2f} >= {self.config.max_daily_loss}"
            )

        order_value = order.qty * order.price
        portfolio = self.config.portfolio_value
        if portfolio > 0:
            position_pct = order_value / portfolio * 100.0
            if position_pct > self.config.max_position_concentration_pct:
                reasons.append(
                    f"Position concentration too high: {position_pct:.1f}% > {self.config.max_position_concentration_pct}%"
                )

        open_count = len(self._positions)
        if order.side == "buy" and open_count >= self.config.max_open_positions:
            reasons.append(
                f"Max open positions reached: {open_count} >= {self.config.max_open_positions}"
            )

        new_exposure = self._current_exposure + order_value
        exposure_pct = new_exposure / portfolio * 100.0 if portfolio > 0 else 0
        if exposure_pct > self.config.max_total_exposure_pct:
            reasons.append(
                f"Total exposure too high: {exposure_pct:.1f}% > {self.config.max_total_exposure_pct}%"
            )

        return RiskCheckResult(approved=len(reasons) == 0, reasons=reasons)

    async def get_risk_report(self) -> RiskReport:
        await self.update_state()
        portfolio = self.config.portfolio_value

        largest_pct = 0.0
        for p in self._positions:
            val = abs(p.qty * p.current_price)
            pct = val / portfolio * 100.0 if portfolio > 0 else 0
            if pct > largest_pct:
                largest_pct = pct

        exposure_pct = self._current_exposure / portfolio * 100.0 if portfolio > 0 else 0
        risk_util = max(
            exposure_pct / self.config.max_total_exposure_pct * 100.0 if self.config.max_total_exposure_pct > 0 else 0,
            self._current_drawdown / self.config.max_drawdown_pct * 100.0 if self.config.max_drawdown_pct > 0 else 0,
        )

        warnings: list[str] = []
        if exposure_pct > self.config.max_total_exposure_pct * 0.8:
            warnings.append("Approaching max exposure limit")
        if self._current_drawdown > self.config.max_drawdown_pct * 0.7:
            warnings.append("Approaching max drawdown limit")
        if self._daily_pnl < 0 and abs(self._daily_pnl) > self.config.max_daily_loss * 0.7:
            warnings.append("Approaching daily loss limit")

        return RiskReport(
            total_exposure=round(self._current_exposure, 2),
            cash_available=round(portfolio - self._current_exposure, 2),
            max_drawdown_current=round(self._current_drawdown, 2),
            daily_pnl=round(self._daily_pnl, 2),
            open_positions_count=len(self._positions),
            largest_position_pct=round(largest_pct, 2),
            risk_utilization_pct=round(min(100.0, risk_util), 2),
            warnings=warnings,
        )

    async def emergency_close_all(self) -> list[CloseOrder]:
        await self.update_state()
        orders: list[CloseOrder] = []
        for p in self._positions:
            if p.qty != 0:
                side = "sell" if p.qty > 0 else "buy"
                orders.append(CloseOrder(ticker=p.ticker, side=side, qty=abs(p.qty)))
        return orders
