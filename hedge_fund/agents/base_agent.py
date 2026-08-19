from __future__ import annotations
import asyncio
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional
from loguru import logger


class Action(str, Enum):
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"
    CLOSE = "CLOSE"


class MarketSession(str, Enum):
    PRE_MARKET = "PRE_MARKET"
    MAIN = "MAIN"
    EVENING = "EVENING"
    CLOSED = "CLOSED"


class AgentRole(str, Enum):
    ORCHESTRATOR = "orchestrator"
    SCALPING = "scalping"
    DAY_TRADING = "day_trading"
    LONG_TERM = "long_term"
    NEWS = "news"
    RISK = "risk"
    QUANT = "quant"


@dataclass
class AgentSignal:
    ticker: str
    action: Action
    confidence: float
    qty: int = 0
    price: float = 0.0
    stop_loss: float = 0.0
    take_profit: float = 0.0
    reasoning: str = ""
    agent_name: str = ""
    strategy_name: str = ""
    urgency: float = 0.5
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: dict[str, Any] = field(default_factory=dict)


class BaseAgent(ABC):
    def __init__(
        self,
        name: str,
        role: AgentRole,
        config: dict,
        data_feed: Any = None,
        order_manager: Any = None,
        db: Any = None,
        loop_interval: float = 60.0,
    ):
        self.name = name
        self.role = role
        self.config = config
        self.data_feed = data_feed
        self.order_manager = order_manager
        self.db = db
        self.loop_interval = loop_interval
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self.signals_queue: asyncio.Queue[AgentSignal] = asyncio.Queue()
        self.performance = {"trades": 0, "wins": 0, "total_pnl": 0.0}
        self.log = logger.bind(agent=name)

    async def start(self) -> None:
        self._running = True
        self._task = asyncio.create_task(self._run_loop())
        self.log.info(f"Agent {self.name} started (interval={self.loop_interval}s)")

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        self.log.info(f"Agent {self.name} stopped")

    async def _run_loop(self) -> None:
        while self._running:
            try:
                signals = await self.analyze()
                for sig in signals:
                    sig.agent_name = self.name
                    await self.signals_queue.put(sig)
                    self.log.info(f"Signal: {sig.action.value} {sig.ticker} conf={sig.confidence:.2f}")
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.log.error(f"Analysis error: {e}")
            await asyncio.sleep(self.loop_interval)

    async def emit_signal(self, signal: AgentSignal) -> None:
        signal.agent_name = self.name
        await self.signals_queue.put(signal)

    def update_performance(self, pnl: float) -> None:
        self.performance["trades"] += 1
        self.performance["total_pnl"] += pnl
        if pnl > 0:
            self.performance["wins"] += 1

    @property
    def win_rate(self) -> float:
        if self.performance["trades"] == 0:
            return 0.0
        return self.performance["wins"] / self.performance["trades"]

    @abstractmethod
    async def analyze(self) -> list[AgentSignal]:
        ...

    @abstractmethod
    async def get_status(self) -> dict:
        ...
