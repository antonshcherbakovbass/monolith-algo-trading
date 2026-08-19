"""Historical data loader for MOEX ISS API."""

from __future__ import annotations

import asyncio
import time
from pathlib import Path
from typing import Any

import aiohttp
import pandas as pd

from ..utils.logger import get_logger

log = get_logger("data.moex_loader")


class MOEXDataLoader:
    """Downloads historical candles from MOEX ISS API."""

    BASE_URL = "https://iss.moex.com/iss"
    _PAGE_SIZE = 500
    _MAX_RPS = 5

    def __init__(self) -> None:
        self._last_request_times: list[float] = []

    async def _rate_limit(self) -> None:
        now = time.monotonic()
        self._last_request_times = [
            t for t in self._last_request_times if now - t < 1.0
        ]
        if len(self._last_request_times) >= self._MAX_RPS:
            sleep_for = 1.0 - (now - self._last_request_times[0])
            if sleep_for > 0:
                await asyncio.sleep(sleep_for)
        self._last_request_times.append(time.monotonic())

    async def _get_json(
        self, session: aiohttp.ClientSession, url: str, params: dict[str, Any]
    ) -> dict[str, Any]:
        await self._rate_limit()
        async with session.get(url, params=params) as resp:
            resp.raise_for_status()
            return await resp.json()

    async def fetch_candles(
        self,
        ticker: str,
        board: str = "TQBR",
        interval: int = 24,
        start_date: str = "2022-01-01",
        end_date: str | None = None,
    ) -> pd.DataFrame:
        """Fetch OHLCV candles for a stock ticker.

        Returns DataFrame with columns:
        open, high, low, close, volume, value, datetime.
        """
        url = (
            f"{self.BASE_URL}/engines/stock/markets/shares"
            f"/boards/{board}/securities/{ticker}/candles.json"
        )
        return await self._paginate_candles(url, interval, start_date, end_date)

    async def fetch_futures_candles(
        self,
        ticker: str,
        interval: int = 24,
        start_date: str = "2022-01-01",
        end_date: str | None = None,
    ) -> pd.DataFrame:
        """Fetch OHLCV candles for a futures ticker on RFUD board."""
        url = (
            f"{self.BASE_URL}/engines/futures/markets/forts"
            f"/boards/RFUD/securities/{ticker}/candles.json"
        )
        return await self._paginate_candles(url, interval, start_date, end_date)

    async def _paginate_candles(
        self,
        url: str,
        interval: int,
        start_date: str,
        end_date: str | None,
    ) -> pd.DataFrame:
        all_rows: list[dict[str, Any]] = []
        start = 0
        async with aiohttp.ClientSession() as session:
            while True:
                params: dict[str, Any] = {
                    "from": start_date,
                    "interval": interval,
                    "start": start,
                    "iss.meta": "off",
                    "iss.json": "extended",
                }
                if end_date:
                    params["till"] = end_date

                data = await self._get_json(session, url, params)

                candles_block = self._extract_candles(data)
                if not candles_block:
                    break

                all_rows.extend(candles_block)
                if len(candles_block) < self._PAGE_SIZE:
                    break
                start += self._PAGE_SIZE

        if not all_rows:
            log.warning("No candle data returned for {}", url)
            return pd.DataFrame()

        df = pd.DataFrame(all_rows)
        col_map = {
            "begin": "datetime",
            "open": "open",
            "close": "close",
            "high": "high",
            "low": "low",
            "volume": "volume",
            "value": "value",
        }
        present = {k: v for k, v in col_map.items() if k in df.columns}
        df = df.rename(columns=present)
        for col in col_map.values():
            if col not in df.columns:
                df[col] = None

        df["datetime"] = pd.to_datetime(df["datetime"])
        df = df.sort_values("datetime").reset_index(drop=True)
        return df[["datetime", "open", "high", "low", "close", "volume", "value"]]

    @staticmethod
    def _extract_candles(data: Any) -> list[dict[str, Any]]:
        """Pull candle rows from ISS extended JSON response."""
        if isinstance(data, list):
            for block in data:
                if isinstance(block, dict) and "candles" in block:
                    return block["candles"]
        if isinstance(data, dict):
            candles = data.get("candles", {})
            columns = candles.get("columns", [])
            rows = candles.get("data", [])
            return [dict(zip(columns, row)) for row in rows]
        return []

    async def fetch_orderbook(
        self, ticker: str, board: str = "TQBR"
    ) -> dict[str, Any]:
        """Fetch the current order book snapshot."""
        url = (
            f"{self.BASE_URL}/engines/stock/markets/shares"
            f"/boards/{board}/securities/{ticker}/orderbook.json"
        )
        async with aiohttp.ClientSession() as session:
            data = await self._get_json(session, url, {"iss.meta": "off"})
        return data

    async def fetch_all_tickers(self, board: str = "TQBR") -> list[dict[str, Any]]:
        """Return a list of all securities on *board*."""
        url = (
            f"{self.BASE_URL}/engines/stock/markets/shares"
            f"/boards/{board}/securities.json"
        )
        async with aiohttp.ClientSession() as session:
            data = await self._get_json(session, url, {"iss.meta": "off"})
        securities = data.get("securities", {})
        columns = securities.get("columns", [])
        rows = securities.get("data", [])
        return [dict(zip(columns, row)) for row in rows]

    async def bulk_download(
        self,
        tickers: list[str],
        start_date: str = "2022-01-01",
        save_dir: str = "hedge_fund/data/historical",
    ) -> dict[str, pd.DataFrame]:
        """Download historical data for multiple tickers, save to CSV."""
        save_path = Path(save_dir)
        save_path.mkdir(parents=True, exist_ok=True)
        results: dict[str, pd.DataFrame] = {}

        for ticker in tickers:
            try:
                log.info("Downloading {}", ticker)
                df = await self.fetch_candles(
                    ticker, start_date=start_date
                )
                if df.empty:
                    log.warning("No data for {}", ticker)
                    continue
                csv_file = save_path / f"{ticker}.csv"
                df.to_csv(csv_file, index=False)
                results[ticker] = df
                log.info("Saved {} rows for {} → {}", len(df), ticker, csv_file)
            except Exception:
                log.exception("Failed to download {}", ticker)

        return results
