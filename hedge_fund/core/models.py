"""
Pydantic models for the MONOLITH algo trading platform.

These replace loose dicts with validated, typed data structures
used across all agents and the event bus pipeline.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Optional
from pydantic import BaseModel, Field, field_validator, model_validator


class Side(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


class OrderType(str, Enum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP = "STOP"
    STOP_LIMIT = "STOP_LIMIT"


class InstrumentType(str, Enum):
    STOCK = "STOCK"
    FUTURE = "FUTURE"
    BOND = "BOND"
    OPTION = "OPTION"
    ETF = "ETF"


class MarketRegime(str, Enum):
    BULLISH_EXPANSION = "bullish_expansion"
    BEARISH_CONTRACTION = "bearish_contraction"
    HIGH_VOL_SIDEWAYS = "high_vol_sideways"
    LOW_VOL_RANGING = "low_vol_ranging"
    GEOPOLITICAL_PANIC = "geopolitical_panic"
    RECOVERY = "recovery"


class RiskVerdict(str, Enum):
    APPROVED = "approved"
    REJECTED = "rejected"
    MODIFIED = "modified"  # approved with reduced size


class Quote(BaseModel):
    ticker: str
    bid: float = 0.0
    ask: float = 0.0
    last: float = 0.0
    volume: int = 0
    timestamp: datetime = Field(default_factory=datetime.now)
    bid_vol: int = 0
    ask_vol: int = 0
    spread_pct: float = 0.0

    @model_validator(mode="after")
    def calc_spread(self) -> "Quote":
        if self.spread_pct == 0 and self.bid > 0 and self.ask > self.bid:
            self.spread_pct = (self.ask - self.bid) / self.bid * 100
        return self


class OHLCV(BaseModel):
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int = 0


class OrderBookLevel(BaseModel):
    price: float
    qty: int


class OrderBook(BaseModel):
    ticker: str
    bids: list[OrderBookLevel] = Field(default_factory=list)
    asks: list[OrderBookLevel] = Field(default_factory=list)
    timestamp: datetime = Field(default_factory=datetime.now)

    @property
    def imbalance(self) -> float:
        """Bid/ask volume imbalance: >0.5 = bid-heavy, <0.5 = ask-heavy."""
        bid_vol = sum(l.qty for l in self.bids[:5])
        ask_vol = sum(l.qty for l in self.asks[:5])
        total = bid_vol + ask_vol
        return bid_vol / total if total > 0 else 0.5

    @property
    def mid_price(self) -> float:
        if self.bids and self.asks:
            return (self.bids[0].price + self.asks[0].price) / 2
        return 0.0


class MarketContext(BaseModel):
    """Snapshot of the current market state, shared across all agents."""
    regime: MarketRegime = MarketRegime.LOW_VOL_RANGING
    regime_confidence: float = 0.5
    overall_sentiment: float = 0.0  # -1 to 1
    vix_rvi: float = 0.0  # RVI analog for MOEX
    moex_index_change_pct: float = 0.0
    usd_rub: float = 0.0
    brent_price: float = 0.0
    key_rate_cbr: float = 0.0
    active_sanctions_risk: bool = False
    trading_session_active: bool = True
    timestamp: datetime = Field(default_factory=datetime.now)


class AlphaSignal(BaseModel):
    """Signal from any alpha-generating agent."""
    ticker: str
    side: Side
    confidence: float = Field(ge=0.0, le=1.0)
    strategy: str = ""
    agent: str = ""
    entry_price: float = 0.0
    stop_loss: float = 0.0
    take_profit: float = 0.0
    timeframe: str = ""  # "scalp", "intraday", "swing", "position"
    reasoning: str = ""
    urgency: float = Field(default=0.5, ge=0.0, le=1.0)
    metadata: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.now)


class CommissionBreakdown(BaseModel):
    exchange_fee: float = 0.0
    broker_fee: float = 0.0
    clearing_fee: float = 0.0

    @property
    def total(self) -> float:
        return self.exchange_fee + self.broker_fee + self.clearing_fee


class OrderProposal(BaseModel):
    """
    Complete order proposal that passes through the pipeline:
    Quant -> Execution -> Hedging -> Risk -> QUIK
    """
    proposal_id: str = Field(default="")
    ticker: str
    class_code: str = "TQBR"
    side: Side
    qty: int = Field(gt=0)
    price: float = 0.0
    order_type: OrderType = OrderType.LIMIT
    instrument_type: InstrumentType = InstrumentType.STOCK
    stop_loss: float = 0.0
    take_profit: float = 0.0
    agent: str = ""
    strategy: str = ""
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    reasoning: str = ""
    commissions: CommissionBreakdown = Field(default_factory=CommissionBreakdown)
    expected_pnl: float = 0.0
    risk_reward_ratio: float = 0.0
    hedge_orders: list[OrderProposal] = Field(default_factory=list)
    timestamp: datetime = Field(default_factory=datetime.now)

    @model_validator(mode="before")
    @classmethod
    def gen_id(cls, data: Any) -> Any:
        if isinstance(data, dict):
            proposal_id = data.get("proposal_id", "")
            if not proposal_id:
                import uuid
                data["proposal_id"] = str(uuid.uuid4())[:12]
        return data

    @property
    def is_profitable_after_fees(self) -> bool:
        return self.expected_pnl > self.commissions.total


class RiskValidationReceipt(BaseModel):
    """Result of the Risk Shield's evaluation of an OrderProposal."""
    proposal_id: str
    verdict: RiskVerdict
    original_qty: int
    approved_qty: int = 0
    checks_passed: list[str] = Field(default_factory=list)
    checks_failed: list[str] = Field(default_factory=list)
    max_drawdown_remaining_pct: float = 0.0
    daily_loss_remaining_pct: float = 0.0
    position_concentration_pct: float = 0.0
    portfolio_exposure_pct: float = 0.0
    margin_utilization_pct: float = 0.0
    reason: str = ""
    timestamp: datetime = Field(default_factory=datetime.now)

    @property
    def is_approved(self) -> bool:
        return self.verdict in (RiskVerdict.APPROVED, RiskVerdict.MODIFIED)


class PortfolioSnapshot(BaseModel):
    total_value: float = 0.0
    cash: float = 0.0
    positions_value: float = 0.0
    unrealized_pnl: float = 0.0
    realized_pnl_today: float = 0.0
    drawdown_pct: float = 0.0
    margin_used: float = 0.0
    margin_available: float = 0.0
    positions_count: int = 0
    long_exposure: float = 0.0
    short_exposure: float = 0.0
    net_delta: float = 0.0
    timestamp: datetime = Field(default_factory=datetime.now)


class SystemHealth(BaseModel):
    """Telemetry from the SRE/QA agent."""
    quik_connected: bool = False
    quik_latency_ms: float = 0.0
    ollama_available: bool = False
    event_bus_queue_size: int = 0
    event_bus_latency_ms: float = 0.0
    memory_usage_mb: float = 0.0
    cpu_usage_pct: float = 0.0
    agents_running: int = 0
    agents_total: int = 0
    uptime_seconds: float = 0.0
    errors_last_hour: int = 0
    timestamp: datetime = Field(default_factory=datetime.now)
