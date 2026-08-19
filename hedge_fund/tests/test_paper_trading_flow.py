"""Integration tests for the paper trading execution pipeline."""
from __future__ import annotations

import pytest

from hedge_fund.agents.base_agent import Action, AgentSignal
from hedge_fund.agents.orchestrator import Orchestrator
from hedge_fund.core.config_loader import agents_as_dict, get_agent_params, normalize_broker_name
from hedge_fund.core.execution_engine import ExecutionEngine
from hedge_fund.quik.order_manager import OrderManager
from hedge_fund.risk.daily_loss_lock import DailyLossLock
from hedge_fund.risk.position_sizer import PositionSizer


@pytest.fixture
def sample_config() -> dict:
    return {
        "agents": [
            {"name": "orchestrator", "enabled": True, "params": {"allocations": {"scalping": 1.0}}},
            {"name": "scalping", "enabled": True, "params": {"loop_interval": 1.0, "min_spread_pct": 0.05}},
        ],
        "instruments": {"stocks": ["SBER"], "futures": []},
        "risk": {"max_position_pct": 10.0},
    }


class TestConfigLoader:
    def test_agents_as_dict_from_list(self, sample_config):
        agents = agents_as_dict(sample_config)
        assert "scalping" in agents
        assert agents["scalping"]["enabled"] is True

    def test_get_agent_params(self, sample_config):
        params = get_agent_params(sample_config, "scalping")
        assert params["loop_interval"] == 1.0

    def test_normalize_broker_name(self):
        assert normalize_broker_name("sber") == "sber_quik"
        assert normalize_broker_name("tinkoff") == "tinkoff"


class TestExecutionEngine:
    @pytest.mark.asyncio
    async def test_paper_order_execution(self, sample_config):
        order_mgr = OrderManager(None, paper_trading=True)
        engine = ExecutionEngine(
            order_manager=order_mgr,
            position_sizer=PositionSizer(),
            config=sample_config,
            default_portfolio_value=1_000_000,
            paper=True,
        )
        sig = AgentSignal(
            ticker="SBER",
            action=Action.BUY,
            confidence=0.8,
            price=250.0,
            agent_name="scalping",
        )
        order_id = await engine.execute_signal(sig)
        assert order_id is not None
        assert engine.executed_count == 1

    @pytest.mark.asyncio
    async def test_daily_loss_lock_blocks_orders(self, sample_config):
        order_mgr = OrderManager(None, paper_trading=True)
        lock = DailyLossLock(max_daily_loss_pct=2.0, portfolio_value=1_000_000)
        lock.record_loss(25_000)
        engine = ExecutionEngine(
            order_manager=order_mgr,
            daily_loss_lock=lock,
            config=sample_config,
            paper=True,
        )
        sig = AgentSignal(ticker="SBER", action=Action.BUY, confidence=0.9, price=250.0, qty=10)
        assert lock.is_locked()
        assert await engine.execute_signal(sig) is None
        assert engine.executed_count == 0


class TestOrchestratorExecution:
    @pytest.mark.asyncio
    async def test_orchestrator_executes_approved_signal(self, sample_config):
        order_mgr = OrderManager(None, paper_trading=True)
        engine = ExecutionEngine(
            order_manager=order_mgr,
            position_sizer=PositionSizer(),
            config=sample_config,
            default_portfolio_value=1_000_000,
            paper=True,
        )
        orchestrator = Orchestrator(sample_config, None, order_mgr, None, execution_engine=engine)
        from hedge_fund.agents.scalping_agent import ScalpingAgent

        scalper = ScalpingAgent(sample_config, None, order_mgr, None)
        orchestrator.register_agent(scalper)
        sig = AgentSignal(
            ticker="SBER",
            action=Action.BUY,
            confidence=0.85,
            price=250.0,
            qty=5,
            agent_name="scalping",
        )
        await scalper.signals_queue.put(sig)
        approved = await orchestrator.analyze()
        assert len(approved) == 1
        assert engine.executed_count == 1
