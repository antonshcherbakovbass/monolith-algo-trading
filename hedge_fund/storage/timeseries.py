from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional, Sequence

from sqlalchemy import (
    Column, Integer, Float, String, DateTime, Table, MetaData,
    select, and_, text, delete,
)
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine, async_sessionmaker


@dataclass
class Candle:
    timestamp: datetime
    ticker: str
    open: float
    high: float
    low: float
    close: float
    volume: float


TIMEFRAMES = ("1m", "5m", "15m", "1h", "1d")

RETENTION_DAYS: dict[str, int] = {
    "1m": 7,
    "5m": 30,
    "15m": 90,
    "1h": 365,
    "1d": 3650,
}


def _table_name(tf: str) -> str:
    return f"candles_{tf}"


class TimeSeriesStorage:
    def __init__(self, db_url: str = "sqlite+aiosqlite:///market_data.db") -> None:
        self.engine: AsyncEngine = create_async_engine(db_url, echo=False)
        self.session_factory = async_sessionmaker(self.engine, expire_on_commit=False)
        self.metadata = MetaData()
        self._tables: dict[str, Table] = {}
        for tf in TIMEFRAMES:
            tbl = Table(
                _table_name(tf),
                self.metadata,
                Column("id", Integer, primary_key=True, autoincrement=True),
                Column("timestamp", DateTime, index=True),
                Column("ticker", String(20), index=True),
                Column("open", Float),
                Column("high", Float),
                Column("low", Float),
                Column("close", Float),
                Column("volume", Float),
            )
            self._tables[tf] = tbl

    async def init(self) -> None:
        async with self.engine.begin() as conn:
            await conn.run_sync(self.metadata.create_all)

    async def close(self) -> None:
        await self.engine.dispose()

    def _get_table(self, tf: str) -> Table:
        if tf not in self._tables:
            raise ValueError(f"Unknown timeframe: {tf}. Supported: {TIMEFRAMES}")
        return self._tables[tf]

    async def store_candles(self, ticker: str, tf: str, candles: Sequence[Candle]) -> int:
        if not candles:
            return 0
        tbl = self._get_table(tf)
        rows = [
            {
                "timestamp": c.timestamp,
                "ticker": ticker,
                "open": c.open,
                "high": c.high,
                "low": c.low,
                "close": c.close,
                "volume": c.volume,
            }
            for c in candles
        ]
        async with self.engine.begin() as conn:
            await conn.execute(tbl.insert(), rows)
        return len(rows)

    async def get_candles(
        self,
        ticker: str,
        tf: str,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        limit: int = 1000,
    ) -> list[Candle]:
        tbl = self._get_table(tf)
        conditions = [tbl.c.ticker == ticker]
        if start:
            conditions.append(tbl.c.timestamp >= start)
        if end:
            conditions.append(tbl.c.timestamp <= end)
        stmt = (
            select(tbl)
            .where(and_(*conditions))
            .order_by(tbl.c.timestamp.asc())
            .limit(limit)
        )
        async with self.session_factory() as sess:
            result = await sess.execute(stmt)
            return [
                Candle(
                    timestamp=row.timestamp,
                    ticker=row.ticker,
                    open=row.open,
                    high=row.high,
                    low=row.low,
                    close=row.close,
                    volume=row.volume,
                )
                for row in result.fetchall()
            ]

    async def get_latest(self, ticker: str, tf: str, count: int = 100) -> list[Candle]:
        tbl = self._get_table(tf)
        stmt = (
            select(tbl)
            .where(tbl.c.ticker == ticker)
            .order_by(tbl.c.timestamp.desc())
            .limit(count)
        )
        async with self.session_factory() as sess:
            result = await sess.execute(stmt)
            rows = result.fetchall()
        candles = [
            Candle(
                timestamp=row.timestamp,
                ticker=row.ticker,
                open=row.open,
                high=row.high,
                low=row.low,
                close=row.close,
                volume=row.volume,
            )
            for row in reversed(rows)
        ]
        return candles

    async def cleanup_old_data(self) -> dict[str, int]:
        deleted: dict[str, int] = {}
        now = datetime.utcnow()
        for tf, days in RETENTION_DAYS.items():
            tbl = self._get_table(tf)
            cutoff = now - timedelta(days=days)
            async with self.engine.begin() as conn:
                result = await conn.execute(
                    delete(tbl).where(tbl.c.timestamp < cutoff)
                )
                deleted[tf] = result.rowcount
        return deleted
