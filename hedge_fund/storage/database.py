from __future__ import annotations

import json
from contextlib import asynccontextmanager
from datetime import datetime, date
from typing import AsyncGenerator, Optional, Sequence

from sqlalchemy import (
    Column, Integer, String, Float, DateTime, Text, Enum as SAEnum,
    select, and_, func,
)
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    AsyncEngine,
    create_async_engine,
    async_sessionmaker,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
import enum


class Base(DeclarativeBase):
    pass


class SideEnum(str, enum.Enum):
    BUY = "buy"
    SELL = "sell"


class OrderStatusEnum(str, enum.Enum):
    PENDING = "pending"
    ACTIVE = "active"
    FILLED = "filled"
    PARTIALLY_FILLED = "partially_filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"


class OrderTypeEnum(str, enum.Enum):
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    STOP_LIMIT = "stop_limit"


class Trade(Base):
    __tablename__ = "trades"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    ticker: Mapped[str] = mapped_column(String(20), index=True)
    side: Mapped[str] = mapped_column(String(4))
    qty: Mapped[int] = mapped_column(Integer)
    price: Mapped[float] = mapped_column(Float)
    commission: Mapped[float] = mapped_column(Float, default=0.0)
    pnl: Mapped[float] = mapped_column(Float, default=0.0)
    agent_name: Mapped[str] = mapped_column(String(50))
    strategy_name: Mapped[str] = mapped_column(String(50))
    order_type: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(20))


class Position(Base):
    __tablename__ = "positions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ticker: Mapped[str] = mapped_column(String(20), index=True, unique=True)
    qty: Mapped[int] = mapped_column(Integer)
    avg_price: Mapped[float] = mapped_column(Float)
    current_price: Mapped[float] = mapped_column(Float, default=0.0)
    unrealized_pnl: Mapped[float] = mapped_column(Float, default=0.0)
    opened_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    agent_name: Mapped[str] = mapped_column(String(50))


class PortfolioSnapshot(Base):
    __tablename__ = "portfolio_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    total_value: Mapped[float] = mapped_column(Float)
    cash: Mapped[float] = mapped_column(Float)
    positions_value: Mapped[float] = mapped_column(Float)
    daily_pnl: Mapped[float] = mapped_column(Float, default=0.0)
    drawdown_pct: Mapped[float] = mapped_column(Float, default=0.0)


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    quik_order_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    ticker: Mapped[str] = mapped_column(String(20), index=True)
    side: Mapped[str] = mapped_column(String(4))
    qty: Mapped[int] = mapped_column(Integer)
    price: Mapped[float] = mapped_column(Float)
    order_type: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(20), default=OrderStatusEnum.PENDING.value)
    fill_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    fill_qty: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)


class AgentDecision(Base):
    __tablename__ = "agent_decisions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    agent_name: Mapped[str] = mapped_column(String(50), index=True)
    action: Mapped[str] = mapped_column(String(20))
    ticker: Mapped[str] = mapped_column(String(20))
    reasoning: Mapped[str] = mapped_column(Text)
    confidence: Mapped[float] = mapped_column(Float)
    approved_by_risk: Mapped[int] = mapped_column(Integer, default=0)


class MLModelVersion(Base):
    __tablename__ = "ml_model_versions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    model_name: Mapped[str] = mapped_column(String(100), index=True)
    version: Mapped[str] = mapped_column(String(20))
    trained_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    metrics_json: Mapped[str] = mapped_column(Text, default="{}")
    file_path: Mapped[str] = mapped_column(String(500))


class Database:
    def __init__(self, db_url: str = "sqlite+aiosqlite:///hedge_fund.db") -> None:
        self.engine: AsyncEngine = create_async_engine(db_url, echo=False)
        self.session_factory = async_sessionmaker(self.engine, expire_on_commit=False)

    async def init(self) -> None:
        await self.create_tables()

    async def create_tables(self) -> None:
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    @asynccontextmanager
    async def session(self) -> AsyncGenerator[AsyncSession, None]:
        async with self.session_factory() as sess:
            try:
                yield sess
                await sess.commit()
            except Exception:
                await sess.rollback()
                raise

    async def close(self) -> None:
        await self.engine.dispose()


class TradeRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    async def add_trade(
        self,
        ticker: str,
        side: str,
        qty: int,
        price: float,
        commission: float = 0.0,
        pnl: float = 0.0,
        agent_name: str = "",
        strategy_name: str = "",
        order_type: str = "market",
        status: str = "filled",
    ) -> Trade:
        trade = Trade(
            ticker=ticker,
            side=side,
            qty=qty,
            price=price,
            commission=commission,
            pnl=pnl,
            agent_name=agent_name,
            strategy_name=strategy_name,
            order_type=order_type,
            status=status,
        )
        async with self.db.session() as sess:
            sess.add(trade)
            await sess.flush()
            return trade

    async def get_trades(
        self,
        ticker: Optional[str] = None,
        agent_name: Optional[str] = None,
        strategy_name: Optional[str] = None,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        limit: int = 100,
    ) -> Sequence[Trade]:
        stmt = select(Trade)
        conditions = []
        if ticker:
            conditions.append(Trade.ticker == ticker)
        if agent_name:
            conditions.append(Trade.agent_name == agent_name)
        if strategy_name:
            conditions.append(Trade.strategy_name == strategy_name)
        if start:
            conditions.append(Trade.timestamp >= start)
        if end:
            conditions.append(Trade.timestamp <= end)
        if conditions:
            stmt = stmt.where(and_(*conditions))
        stmt = stmt.order_by(Trade.timestamp.desc()).limit(limit)
        async with self.db.session() as sess:
            result = await sess.execute(stmt)
            return result.scalars().all()

    async def get_pnl(
        self,
        period_start: Optional[datetime] = None,
        period_end: Optional[datetime] = None,
    ) -> float:
        stmt = select(func.sum(Trade.pnl))
        conditions = []
        if period_start:
            conditions.append(Trade.timestamp >= period_start)
        if period_end:
            conditions.append(Trade.timestamp <= period_end)
        if conditions:
            stmt = stmt.where(and_(*conditions))
        async with self.db.session() as sess:
            result = await sess.execute(stmt)
            val = result.scalar()
            return val if val is not None else 0.0


class PositionRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    async def update_position(
        self,
        ticker: str,
        qty: int,
        avg_price: float,
        current_price: float = 0.0,
        agent_name: str = "",
    ) -> Position:
        async with self.db.session() as sess:
            stmt = select(Position).where(Position.ticker == ticker)
            result = await sess.execute(stmt)
            pos = result.scalar_one_or_none()
            if pos is None:
                pos = Position(
                    ticker=ticker,
                    qty=qty,
                    avg_price=avg_price,
                    current_price=current_price,
                    unrealized_pnl=(current_price - avg_price) * qty,
                    agent_name=agent_name,
                )
                sess.add(pos)
            else:
                pos.qty = qty
                pos.avg_price = avg_price
                pos.current_price = current_price
                pos.unrealized_pnl = (current_price - avg_price) * qty
            await sess.flush()
            return pos

    async def get_all_positions(self) -> Sequence[Position]:
        async with self.db.session() as sess:
            result = await sess.execute(select(Position).where(Position.qty != 0))
            return result.scalars().all()

    async def get_position(self, ticker: str) -> Optional[Position]:
        async with self.db.session() as sess:
            result = await sess.execute(
                select(Position).where(Position.ticker == ticker)
            )
            return result.scalar_one_or_none()


class PortfolioRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    async def snapshot(
        self,
        total_value: float,
        cash: float,
        positions_value: float,
        daily_pnl: float = 0.0,
        drawdown_pct: float = 0.0,
    ) -> PortfolioSnapshot:
        snap = PortfolioSnapshot(
            total_value=total_value,
            cash=cash,
            positions_value=positions_value,
            daily_pnl=daily_pnl,
            drawdown_pct=drawdown_pct,
        )
        async with self.db.session() as sess:
            sess.add(snap)
            await sess.flush()
            return snap

    async def get_history(
        self,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        limit: int = 365,
    ) -> Sequence[PortfolioSnapshot]:
        stmt = select(PortfolioSnapshot)
        conditions = []
        if start:
            conditions.append(PortfolioSnapshot.timestamp >= start)
        if end:
            conditions.append(PortfolioSnapshot.timestamp <= end)
        if conditions:
            stmt = stmt.where(and_(*conditions))
        stmt = stmt.order_by(PortfolioSnapshot.timestamp.desc()).limit(limit)
        async with self.db.session() as sess:
            result = await sess.execute(stmt)
            return result.scalars().all()

    async def get_drawdown(self) -> float:
        async with self.db.session() as sess:
            stmt = select(PortfolioSnapshot).order_by(
                PortfolioSnapshot.timestamp.desc()
            ).limit(1)
            result = await sess.execute(stmt)
            latest = result.scalar_one_or_none()
            if latest is None:
                return 0.0
            return latest.drawdown_pct


class OrderRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    async def add_order(
        self,
        ticker: str,
        side: str,
        qty: int,
        price: float,
        order_type: str = "market",
        quik_order_id: Optional[str] = None,
    ) -> Order:
        order = Order(
            ticker=ticker,
            side=side,
            qty=qty,
            price=price,
            order_type=order_type,
            quik_order_id=quik_order_id,
        )
        async with self.db.session() as sess:
            sess.add(order)
            await sess.flush()
            return order

    async def update_status(
        self,
        order_id: int,
        status: str,
        fill_price: Optional[float] = None,
        fill_qty: Optional[int] = None,
    ) -> Optional[Order]:
        async with self.db.session() as sess:
            result = await sess.execute(select(Order).where(Order.id == order_id))
            order = result.scalar_one_or_none()
            if order is None:
                return None
            order.status = status
            if fill_price is not None:
                order.fill_price = fill_price
            if fill_qty is not None:
                order.fill_qty = fill_qty
            await sess.flush()
            return order

    async def get_active_orders(self) -> Sequence[Order]:
        async with self.db.session() as sess:
            stmt = select(Order).where(
                Order.status.in_([
                    OrderStatusEnum.PENDING.value,
                    OrderStatusEnum.ACTIVE.value,
                    OrderStatusEnum.PARTIALLY_FILLED.value,
                ])
            )
            result = await sess.execute(stmt)
            return result.scalars().all()
