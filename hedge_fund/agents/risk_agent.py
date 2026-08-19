from __future__ import annotations
import asyncio
from datetime import datetime, timedelta
from typing import Any, Optional
import numpy as np
from loguru import logger
from .base_agent import BaseAgent, AgentSignal, AgentRole, Action
from ..core.config_loader import get_agent_params


class RiskAgent(BaseAgent):
    """Risk management and security agent with veto power over all trades."""

    def __init__(self, config: dict, data_feed: Any = None, order_manager: Any = None, db: Any = None):
        agent_cfg = get_agent_params(config, "risk")
        risk_cfg = config.get("risk", {})
        super().__init__("risk", AgentRole.RISK, config, data_feed, order_manager, db,
                         loop_interval=agent_cfg.get("loop_interval", 10.0))
        self.max_drawdown_pct = risk_cfg.get("max_drawdown_pct", 5.0)
        self.max_position_pct = risk_cfg.get("max_position_pct", 10.0)
        self.max_daily_loss_pct = risk_cfg.get("max_daily_loss_pct", 2.0)
        self.max_open_positions = risk_cfg.get("max_open_positions", 20)
        self.max_correlation = risk_cfg.get("max_correlation", 0.7)
        self.veto_enabled = agent_cfg.get("veto_enabled", True)
        self.portfolio_peak = 0.0
        self.daily_start_value = 0.0
        self.current_value = 0.0
        self.daily_pnl = 0.0
        self.emergency_mode = False
        self.alerts: list[dict] = []
        self.telegram_reporter: Any = None

    async def analyze(self) -> list[AgentSignal]:
        signals: list[AgentSignal] = []
        if not self.order_manager:
            return signals
        try:
            positions = await self.order_manager.get_positions()
            portfolio_value = await self.order_manager.get_portfolio_value()
            self.current_value = portfolio_value
            self.portfolio_peak = max(self.portfolio_peak, portfolio_value)
            if self.daily_start_value == 0:
                self.daily_start_value = portfolio_value
            self.daily_pnl = (portfolio_value - self.daily_start_value) / max(self.daily_start_value, 1) * 100
            drawdown = (self.portfolio_peak - portfolio_value) / max(self.portfolio_peak, 1) * 100

            if drawdown > self.max_drawdown_pct:
                self.log.critical(f"MAX DRAWDOWN BREACHED: {drawdown:.2f}% > {self.max_drawdown_pct}%")
                self.emergency_mode = True
                await self._alert(f"EMERGENCY: Drawdown {drawdown:.2f}% exceeded limit!")
                for ticker in positions:
                    signals.append(AgentSignal(
                        ticker=ticker, action=Action.CLOSE, confidence=1.0,
                        reasoning=f"Emergency close: drawdown {drawdown:.2f}%",
                        strategy_name="risk_management", urgency=1.0,
                    ))
                return signals

            if self.daily_pnl < -self.max_daily_loss_pct:
                self.log.warning(f"Daily loss limit: {self.daily_pnl:.2f}%")
                self.emergency_mode = True
                await self._alert(f"Daily loss limit hit: {self.daily_pnl:.2f}%")

            if len(positions) > self.max_open_positions:
                self.log.warning(f"Too many positions: {len(positions)} > {self.max_open_positions}")
                await self._alert(f"Position count warning: {len(positions)}")

        except Exception as e:
            self.log.error(f"Risk monitoring error: {e}")
        return signals

    async def approve_signal(self, signal: AgentSignal) -> bool:
        if not self.veto_enabled:
            return True
        if self.emergency_mode:
            if signal.action != Action.CLOSE:
                self.log.warning(f"VETO (emergency mode): {signal.action.value} {signal.ticker}")
                return False
            return True
        if signal.confidence < 0.3:
            self.log.info(f"VETO (low confidence {signal.confidence:.2f}): {signal.ticker}")
            return False
        if self.order_manager:
            try:
                positions = await self.order_manager.get_positions()
                portfolio_value = await self.order_manager.get_portfolio_value()
                if signal.action in (Action.BUY, Action.SELL) and len(positions) >= self.max_open_positions:
                    self.log.info(f"VETO (max positions): {signal.ticker}")
                    return False
                if signal.ticker in positions and portfolio_value > 0:
                    pos_value = abs(positions[signal.ticker].get("value", 0))
                    if pos_value / portfolio_value * 100 > self.max_position_pct:
                        self.log.info(f"VETO (concentration {pos_value/portfolio_value*100:.1f}%): {signal.ticker}")
                        return False
            except Exception as e:
                self.log.debug(f"Position check error: {e}")
        if signal.stop_loss == 0 and signal.action in (Action.BUY, Action.SELL):
            self.log.info(f"VETO (no stop loss): {signal.ticker}")
            return False
        return True

    async def _alert(self, message: str) -> None:
        alert = {"timestamp": datetime.now().isoformat(), "message": message}
        self.alerts.append(alert)
        self.log.warning(f"RISK ALERT: {message}")
        if self.telegram_reporter and hasattr(self.telegram_reporter, "send_risk_alert"):
            try:
                await self.telegram_reporter.send_risk_alert(message)
            except Exception:
                pass

    def reset_daily(self) -> None:
        self.daily_start_value = self.current_value
        self.daily_pnl = 0.0
        self.emergency_mode = False
        self.log.info("Daily risk counters reset")

    async def stress_test(self, drop_pct: float = 5.0) -> dict:
        if not self.order_manager:
            return {"error": "No order manager"}
        try:
            positions = await self.order_manager.get_positions()
            portfolio_value = await self.order_manager.get_portfolio_value()
            simulated_loss = sum(
                abs(p.get("value", 0)) * drop_pct / 100 for p in positions.values()
            )
            return {
                "scenario": f"Market drop {drop_pct}%",
                "estimated_loss": simulated_loss,
                "portfolio_after": portfolio_value - simulated_loss,
                "drawdown_pct": simulated_loss / max(portfolio_value, 1) * 100,
            }
        except Exception as e:
            return {"error": str(e)}

    async def get_status(self) -> dict:
        return {
            "name": self.name, "running": self._running,
            "emergency_mode": self.emergency_mode,
            "daily_pnl_pct": self.daily_pnl,
            "portfolio_peak": self.portfolio_peak,
            "drawdown_pct": (self.portfolio_peak - self.current_value) / max(self.portfolio_peak, 1) * 100,
            "alerts_count": len(self.alerts),
            "recent_alerts": [a["message"] for a in self.alerts[-5:]],
        }
