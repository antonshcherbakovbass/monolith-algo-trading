"""
Multi-Account Manager.

Manages multiple QUIK broker accounts simultaneously,
distributing trades and tracking P&L per account.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Protocol
from loguru import logger


@dataclass
class AccountConfig:
    account_id: str
    client_code: str
    name: str = ""
    capital: float = 0.0
    allocation_pct: float = 100.0  # % of signals to apply
    max_position_pct: float = 10.0
    enabled: bool = True
    paper_mode: bool = True


@dataclass
class AccountState:
    account_id: str
    cash: float = 0.0
    portfolio_value: float = 0.0
    positions: dict[str, dict] = field(default_factory=dict)
    daily_pnl: float = 0.0
    total_pnl: float = 0.0
    trades_today: int = 0
    last_updated: datetime = field(default_factory=datetime.now)


class OrderSender(Protocol):
    async def send_order(self, ticker: str, side: str, qty: int, price: float,
                         order_type: str, account: str, client_code: str) -> str: ...


class MultiAccountManager:
    """
    Manages multiple trading accounts through a single QUIK connection.
    
    Features:
    - Route signals to multiple accounts proportionally
    - Per-account risk limits and P&L tracking
    - Account-level allocation percentages
    - Aggregate and per-account reporting
    - Paper/live mode per account
    """

    def __init__(self, connector: Any = None):
        self.connector = connector
        self.accounts: dict[str, AccountConfig] = {}
        self.states: dict[str, AccountState] = {}
        self.log = logger.bind(component="multi_account")

    def add_account(self, config: AccountConfig) -> None:
        self.accounts[config.account_id] = config
        self.states[config.account_id] = AccountState(
            account_id=config.account_id,
            cash=config.capital,
            portfolio_value=config.capital,
        )
        self.log.info(f"Account added: {config.account_id} ({config.name}) alloc={config.allocation_pct}%")

    def remove_account(self, account_id: str) -> None:
        self.accounts.pop(account_id, None)
        self.states.pop(account_id, None)

    async def distribute_order(
        self,
        ticker: str,
        side: str,
        total_qty: int,
        price: float = 0.0,
        order_type: str = "limit",
    ) -> dict[str, str]:
        """Distribute an order across all enabled accounts proportionally."""
        results: dict[str, str] = {}  # account_id -> order_id
        enabled = {aid: acc for aid, acc in self.accounts.items() if acc.enabled}
        if not enabled:
            self.log.warning("No enabled accounts")
            return results

        total_alloc = sum(a.allocation_pct for a in enabled.values())
        if total_alloc <= 0:
            return results

        for account_id, config in enabled.items():
            proportion = config.allocation_pct / total_alloc
            account_qty = max(1, int(total_qty * proportion))

            # Check per-account position limit
            state = self.states.get(account_id)
            if state and state.portfolio_value > 0:
                position_value = account_qty * price if price > 0 else account_qty * 100
                if position_value / state.portfolio_value * 100 > config.max_position_pct:
                    account_qty = int(state.portfolio_value * config.max_position_pct / 100 / max(price, 1))
                    if account_qty <= 0:
                        self.log.info(f"Account {account_id}: position limit reached, skipping")
                        continue

            try:
                if config.paper_mode:
                    order_id = f"PAPER_{account_id}_{datetime.now().strftime('%H%M%S%f')}"
                    self.log.info(f"Paper order: {account_id} {side} {account_qty}x {ticker} @ {price}")
                elif self.connector:
                    order_id = await self.connector.request("send_order", {
                        "ticker": ticker, "side": side, "qty": account_qty,
                        "price": price, "order_type": order_type,
                        "account": config.account_id, "client_code": config.client_code,
                    })
                else:
                    order_id = ""

                results[account_id] = order_id

                # Update state
                if state:
                    state.trades_today += 1
                    state.last_updated = datetime.now()

            except Exception as e:
                self.log.error(f"Order failed for {account_id}: {e}")

        return results

    async def get_all_positions(self) -> dict[str, dict]:
        """Get positions for all accounts."""
        all_positions: dict[str, dict] = {}
        for account_id in self.accounts:
            state = self.states.get(account_id)
            if state:
                all_positions[account_id] = {
                    "cash": state.cash,
                    "portfolio_value": state.portfolio_value,
                    "positions": state.positions,
                    "daily_pnl": state.daily_pnl,
                }
        return all_positions

    def get_aggregate_pnl(self) -> dict[str, float]:
        total_value = sum(s.portfolio_value for s in self.states.values())
        total_daily = sum(s.daily_pnl for s in self.states.values())
        total_pnl = sum(s.total_pnl for s in self.states.values())
        return {
            "total_portfolio_value": total_value,
            "total_daily_pnl": total_daily,
            "total_pnl": total_pnl,
            "accounts_count": len(self.accounts),
            "active_accounts": sum(1 for a in self.accounts.values() if a.enabled),
        }

    def update_account_state(self, account_id: str, cash: float, positions: dict, portfolio_value: float) -> None:
        state = self.states.get(account_id)
        if state:
            old_value = state.portfolio_value
            state.cash = cash
            state.positions = positions
            state.portfolio_value = portfolio_value
            state.daily_pnl += portfolio_value - old_value
            state.last_updated = datetime.now()

    def reset_daily(self) -> None:
        for state in self.states.values():
            state.daily_pnl = 0.0
            state.trades_today = 0

    def get_report(self) -> list[dict]:
        report = []
        for account_id, config in self.accounts.items():
            state = self.states.get(account_id, AccountState(account_id=account_id))
            report.append({
                "account_id": account_id,
                "name": config.name,
                "enabled": config.enabled,
                "paper_mode": config.paper_mode,
                "allocation_pct": config.allocation_pct,
                "portfolio_value": state.portfolio_value,
                "daily_pnl": state.daily_pnl,
                "total_pnl": state.total_pnl,
                "trades_today": state.trades_today,
                "positions_count": len(state.positions),
            })
        return report
