from __future__ import annotations
import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional
import httpx
from loguru import logger
from .base_agent import BaseAgent, AgentSignal, AgentRole, Action
from ..core.config_loader import get_agent_params
from ..core.execution_engine import ExecutionEngine


@dataclass
class AgentAllocation:
    agent_name: str
    capital_pct: float
    current_pnl: float = 0.0
    win_rate: float = 0.0
    sharpe: float = 0.0


class Orchestrator(BaseAgent):
    """Chief Agent that coordinates all trading agents."""

    def __init__(
        self,
        config: dict,
        data_feed: Any = None,
        order_manager: Any = None,
        db: Any = None,
        execution_engine: ExecutionEngine | None = None,
    ):
        super().__init__("orchestrator", AgentRole.ORCHESTRATOR, config, data_feed, order_manager, db, loop_interval=5.0)
        self.agents: dict[str, BaseAgent] = {}
        self.allocations: dict[str, AgentAllocation] = {}
        self.pending_signals: list[AgentSignal] = []
        self.risk_agent: Optional[BaseAgent] = None
        self.signal_history: list[dict] = []
        self.execution_engine = execution_engine
        ai_cfg = config.get("ai", {})
        self.ollama_url = ai_cfg.get("base_url", "http://localhost:11434")
        self.ollama_model = ai_cfg.get("model", "llama3.1")
        orch_params = get_agent_params(config, "orchestrator")
        default_allocs = orch_params.get("allocations", {})
        if not default_allocs:
            default_allocs = {"scalping": 0.25, "day_trading": 0.35, "long_term": 0.25, "quant": 0.15}
        for name, pct in default_allocs.items():
            self.allocations[name] = AgentAllocation(agent_name=name, capital_pct=pct)

    def register_agent(self, agent: BaseAgent) -> None:
        self.agents[agent.name] = agent
        if agent.role == AgentRole.RISK:
            self.risk_agent = agent
        self.log.info(f"Registered agent: {agent.name} ({agent.role.value})")

    async def analyze(self) -> list[AgentSignal]:
        collected: list[AgentSignal] = []
        for name, agent in self.agents.items():
            while not agent.signals_queue.empty():
                try:
                    sig = agent.signals_queue.get_nowait()
                    collected.append(sig)
                except asyncio.QueueEmpty:
                    break
        if not collected:
            return []
        aggregated = self._aggregate_signals(collected)
        approved = []
        for sig in aggregated:
            if self.risk_agent and hasattr(self.risk_agent, "approve_signal"):
                ok = await self.risk_agent.approve_signal(sig)
                if not ok:
                    self.log.warning(f"Risk VETO on {sig.action.value} {sig.ticker}")
                    continue
            approved.append(sig)
        for sig in approved:
            self.signal_history.append({
                "timestamp": datetime.now().isoformat(),
                "ticker": sig.ticker,
                "action": sig.action.value,
                "agent": sig.agent_name,
                "confidence": sig.confidence,
            })
            if self.execution_engine:
                order_id = await self.execution_engine.execute_signal(sig)
                if order_id:
                    self.log.info("Order placed: {} for {} {}", order_id, sig.action.value, sig.ticker)
        return approved

    def _aggregate_signals(self, signals: list[AgentSignal]) -> list[AgentSignal]:
        by_ticker: dict[str, list[AgentSignal]] = {}
        for s in signals:
            by_ticker.setdefault(s.ticker, []).append(s)
        result = []
        for ticker, sigs in by_ticker.items():
            buy_score = sum(s.confidence for s in sigs if s.action == Action.BUY)
            sell_score = sum(s.confidence for s in sigs if s.action == Action.SELL)
            close_sigs = [s for s in sigs if s.action == Action.CLOSE]
            if close_sigs:
                best = max(close_sigs, key=lambda s: s.confidence)
                result.append(best)
                continue
            if buy_score > sell_score and buy_score > 0.3:
                best = max([s for s in sigs if s.action == Action.BUY], key=lambda s: s.confidence)
                best.confidence = min(buy_score / (buy_score + sell_score + 0.01), 1.0)
                result.append(best)
            elif sell_score > buy_score and sell_score > 0.3:
                best = max([s for s in sigs if s.action == Action.SELL], key=lambda s: s.confidence)
                best.confidence = min(sell_score / (buy_score + sell_score + 0.01), 1.0)
                result.append(best)
        return result

    async def rebalance_allocations(self) -> None:
        for name, agent in self.agents.items():
            if name in self.allocations:
                alloc = self.allocations[name]
                alloc.win_rate = agent.win_rate
                alloc.current_pnl = agent.performance["total_pnl"]
        total_score = 0.0
        scores: dict[str, float] = {}
        for name, alloc in self.allocations.items():
            score = max(0.1, alloc.win_rate * 0.5 + (1.0 if alloc.current_pnl > 0 else 0.3) * 0.5)
            scores[name] = score
            total_score += score
        if total_score > 0:
            for name in self.allocations:
                self.allocations[name].capital_pct = scores.get(name, 0.1) / total_score
        self.log.info(f"Rebalanced: {[(n, f'{a.capital_pct:.1%}') for n, a in self.allocations.items()]}")

    async def consult_llm(self, context: str) -> str:
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    f"{self.ollama_url}/api/generate",
                    json={"model": self.ollama_model, "prompt": context, "stream": False},
                )
                if resp.status_code == 200:
                    return resp.json().get("response", "")
        except Exception as e:
            self.log.debug(f"LLM unavailable: {e}")
        return ""

    async def get_status(self) -> dict:
        return {
            "name": self.name,
            "running": self._running,
            "agents_count": len(self.agents),
            "allocations": {n: a.capital_pct for n, a in self.allocations.items()},
            "signals_processed": len(self.signal_history),
            "orders_executed": self.execution_engine.executed_count if self.execution_engine else 0,
        }
