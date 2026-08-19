"""
Hedging & Insurance Agent.

Monitors portfolio delta/gamma/vega exposure and automatically
calculates and proposes hedging trades using MOEX liquid futures
and options. If other agents increase risk, this agent offsets it.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import numpy as np
from loguru import logger

from .base_agent import BaseAgent, AgentSignal, AgentRole, Action
from ..core.config_loader import get_agent_params


@dataclass
class PortfolioGreeks:
    net_delta: float = 0.0       # directional exposure
    net_gamma: float = 0.0       # convexity risk
    net_vega: float = 0.0        # volatility exposure
    beta_to_index: float = 1.0   # portfolio beta to MOEX index
    long_value: float = 0.0
    short_value: float = 0.0

    @property
    def net_exposure(self) -> float:
        return self.long_value - self.short_value

    @property
    def gross_exposure(self) -> float:
        return self.long_value + self.short_value

    @property
    def long_short_ratio(self) -> float:
        if self.short_value == 0:
            return float("inf") if self.long_value > 0 else 0
        return self.long_value / self.short_value


# Map stock tickers to their hedging futures
HEDGE_MAP: dict[str, str] = {
    "SBER": "SRZ4",   # Sberbank future
    "GAZP": "GZZ4",   # Gazprom future
    "LKOH": "LKZ4",   # Lukoil future (approx)
    "VTBR": "VBZ4",
    "ROSN": "RNZ4",
    # Index-based hedging for everything else
    "_INDEX": "RIZ4",  # RTS index future
    "_USD": "SiZ4",    # USD/RUB future for currency hedge
}

# Approximate betas of popular stocks to MOEX index
STOCK_BETAS: dict[str, float] = {
    "SBER": 1.15, "GAZP": 0.95, "LKOH": 0.90, "YNDX": 1.30,
    "GMKN": 0.80, "ROSN": 0.85, "VTBR": 1.25, "NVTK": 0.75,
    "MGNT": 0.70, "TATN": 0.85, "NLMK": 0.90, "ALRS": 0.95,
    "AFLT": 1.10, "CHMF": 0.85, "MOEX": 0.60, "PLZL": 0.50,
}


class HedgingAgent(BaseAgent):
    """
    Portfolio insurance agent that monitors exposure and auto-hedges.
    
    Strategies:
    - Delta hedging: neutralize directional exposure via futures
    - Beta hedging: reduce portfolio beta to target (e.g., 0.3)
    - Tail risk hedging: buy protective puts during high-vol regimes
    - Currency hedging: offset USD/RUB exposure for export-heavy portfolios
    """

    def __init__(self, config: dict, data_feed: Any = None, order_manager: Any = None, db: Any = None):
        hedging_cfg = get_agent_params(config, "hedging")

        super().__init__("hedging", AgentRole.RISK, config, data_feed, order_manager, db,
                         loop_interval=hedging_cfg.get("loop_interval", 30.0))

        self.target_beta = hedging_cfg.get("target_beta", 0.5)
        self.max_delta_pct = hedging_cfg.get("max_delta_pct", 30.0)
        self.hedge_threshold_pct = hedging_cfg.get("hedge_threshold_pct", 15.0)
        self.greeks = PortfolioGreeks()
        self.hedge_positions: dict[str, dict] = {}
        self.instruments = config.get("instruments", {}).get("stocks", [])

    async def analyze(self) -> list[AgentSignal]:
        signals: list[AgentSignal] = []
        if not self.order_manager:
            return signals

        try:
            positions = await self.order_manager.get_positions()
            portfolio_value = await self.order_manager.get_portfolio_value()
            if portfolio_value <= 0:
                return signals

            self._calc_greeks(positions, portfolio_value)

            # Check if delta hedging needed
            delta_pct = abs(self.greeks.net_delta) / max(portfolio_value, 1) * 100
            if delta_pct > self.max_delta_pct:
                hedge_signals = self._delta_hedge(portfolio_value)
                signals.extend(hedge_signals)

            # Check beta hedging
            if abs(self.greeks.beta_to_index - self.target_beta) > 0.3:
                beta_signals = self._beta_hedge(portfolio_value)
                signals.extend(beta_signals)

            # Check long/short imbalance
            if self.greeks.gross_exposure > 0:
                imbalance = self.greeks.net_exposure / self.greeks.gross_exposure * 100
                if abs(imbalance) > self.hedge_threshold_pct:
                    balance_signals = self._rebalance_exposure(portfolio_value)
                    signals.extend(balance_signals)

        except Exception as e:
            self.log.error(f"Hedging analysis error: {e}")

        return signals

    def _calc_greeks(self, positions: dict, portfolio_value: float) -> None:
        long_val = 0.0
        short_val = 0.0
        weighted_beta = 0.0
        net_delta = 0.0

        for ticker, pos in positions.items():
            qty = pos.get("qty", 0) if isinstance(pos, dict) else getattr(pos, "qty", 0)
            price = pos.get("current_price", 0) if isinstance(pos, dict) else getattr(pos, "current_price", 0)
            if price == 0:
                price = pos.get("avg_price", 0) if isinstance(pos, dict) else getattr(pos, "avg_price", 0)
            value = abs(qty * price)
            beta = STOCK_BETAS.get(ticker, 1.0)

            if qty > 0:
                long_val += value
                net_delta += value
            else:
                short_val += value
                net_delta -= value

            weight = value / max(portfolio_value, 1)
            weighted_beta += beta * weight * (1 if qty > 0 else -1)

        self.greeks.long_value = long_val
        self.greeks.short_value = short_val
        self.greeks.net_delta = net_delta
        self.greeks.beta_to_index = abs(weighted_beta)

    def _delta_hedge(self, portfolio_value: float) -> list[AgentSignal]:
        signals = []
        delta = self.greeks.net_delta
        if abs(delta) < portfolio_value * 0.05:
            return signals

        # Use RTS index future for broad delta hedge
        hedge_ticker = HEDGE_MAP["_INDEX"]
        # RTS future ~= 10 * MOEX index points, roughly 100k RUB per contract
        contract_value = 100_000.0
        contracts_needed = int(abs(delta) / contract_value)

        if contracts_needed > 0:
            side = Action.SELL if delta > 0 else Action.BUY
            signals.append(AgentSignal(
                ticker=hedge_ticker,
                action=side,
                confidence=0.85,
                qty=contracts_needed,
                reasoning=f"Delta hedge: net_delta={delta:,.0f} RUB, hedging {contracts_needed} contracts",
                strategy_name="delta_hedge",
            ))
            self.log.info(f"Delta hedge: {side.value} {contracts_needed}x {hedge_ticker} (delta={delta:,.0f})")

        return signals

    def _beta_hedge(self, portfolio_value: float) -> list[AgentSignal]:
        signals = []
        current_beta = self.greeks.beta_to_index
        target = self.target_beta
        beta_diff = current_beta - target

        if abs(beta_diff) < 0.2:
            return signals

        # Hedge beta using RTS future
        hedge_value = portfolio_value * beta_diff
        contract_value = 100_000.0
        contracts = int(abs(hedge_value) / contract_value)

        if contracts > 0:
            side = Action.SELL if beta_diff > 0 else Action.BUY
            signals.append(AgentSignal(
                ticker=HEDGE_MAP["_INDEX"],
                action=side,
                confidence=0.7,
                qty=contracts,
                reasoning=f"Beta hedge: current={current_beta:.2f} target={target:.2f}, {contracts} contracts",
                strategy_name="beta_hedge",
            ))

        return signals

    def _rebalance_exposure(self, portfolio_value: float) -> list[AgentSignal]:
        signals = []
        net = self.greeks.net_exposure
        gross = self.greeks.gross_exposure
        if gross == 0:
            return signals

        # Reduce the dominant side using index future
        hedge_value = abs(net) * 0.5  # hedge half the imbalance
        contract_value = 100_000.0
        contracts = int(hedge_value / contract_value)

        if contracts > 0:
            side = Action.SELL if net > 0 else Action.BUY
            signals.append(AgentSignal(
                ticker=HEDGE_MAP["_INDEX"],
                action=side,
                confidence=0.6,
                qty=contracts,
                reasoning=f"Exposure rebalance: L/S ratio={self.greeks.long_short_ratio:.1f}, net={net:,.0f}",
                strategy_name="exposure_hedge",
            ))

        return signals

    async def overlay_hedge(self, proposal_signals: list[AgentSignal]) -> list[AgentSignal]:
        """
        Called by orchestrator before risk check.
        Evaluates proposed orders and adds offsetting hedges if they
        would push portfolio exposure beyond thresholds.
        """
        additional_delta = 0.0
        for sig in proposal_signals:
            est_value = sig.price * sig.qty if sig.price > 0 else 50_000.0
            if sig.action == Action.BUY:
                additional_delta += est_value
            elif sig.action == Action.SELL:
                additional_delta -= est_value

        new_total_delta = self.greeks.net_delta + additional_delta
        portfolio_value = self.greeks.long_value + self.greeks.short_value
        if portfolio_value == 0:
            portfolio_value = 1_000_000

        new_delta_pct = abs(new_total_delta) / portfolio_value * 100
        if new_delta_pct <= self.max_delta_pct:
            return []

        # Need to hedge the excess
        excess = abs(new_total_delta) - portfolio_value * self.max_delta_pct / 100
        contract_value = 100_000.0
        contracts = max(1, int(excess / contract_value))
        side = Action.SELL if new_total_delta > 0 else Action.BUY

        hedge = AgentSignal(
            ticker=HEDGE_MAP["_INDEX"],
            action=side,
            confidence=0.8,
            qty=contracts,
            reasoning=f"Hedge overlay: proposed trades push delta to {new_delta_pct:.1f}%, capping at {self.max_delta_pct}%",
            strategy_name="hedge_overlay",
        )
        self.log.info(f"Hedge overlay: {side.value} {contracts}x RIZ4")
        return [hedge]

    async def get_status(self) -> dict:
        return {
            "name": self.name,
            "running": self._running,
            "greeks": {
                "net_delta": self.greeks.net_delta,
                "beta": self.greeks.beta_to_index,
                "long_value": self.greeks.long_value,
                "short_value": self.greeks.short_value,
                "net_exposure": self.greeks.net_exposure,
            },
            "target_beta": self.target_beta,
            "hedge_positions": len(self.hedge_positions),
            "performance": self.performance,
        }
