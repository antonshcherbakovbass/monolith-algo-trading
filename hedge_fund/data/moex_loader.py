"""Historical data loader for MOEX ISS API."""

from __future__ import annotations

import asyncio
import json
import ssl
import time
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import aiohttp
import pandas as pd

from ..utils.logger import get_logger

log = get_logger("data.moex_loader")

_DEFAULT_CACHE_DIR = Path(__file__).resolve().parent / "historical"
_CACHE_MAX_AGE_SEC = 7 * 24 * 3600


class MOEXDataLoader:
    """Downloads historical candles from MOEX ISS API."""

    BASE_URL = "https://iss.moex.com/iss"
    _PAGE_SIZE = 500
    _MAX_RPS = 3
    _MAX_RETRIES = 5
    _QUICK_MAX_RETRIES = 2
    _RETRY_BACKOFF = 1.0
    _CONNECT_TIMEOUT = 15
    _SOCK_READ_TIMEOUT = 60
    _TOTAL_TIMEOUT = 90
    _QUICK_TIMEOUT = 12.0
    _URLLIB_TIMEOUT = 60
    _REQUEST_HEADERS = {
        "Connection": "close",
        "User-Agent": "MONOLITH-MOEX/1.0",
    }

    def __init__(
        self,
        cache_dir: str | Path | None = None,
        use_cache: bool = True,
    ) -> None:
        self._cache_dir = Path(cache_dir) if cache_dir else _DEFAULT_CACHE_DIR
        self._use_cache = use_cache
        self._last_request_times: list[float] = []

    def _create_session(self, total_timeout: float | None = None) -> aiohttp.ClientSession:
        total = total_timeout or self._TOTAL_TIMEOUT
        connector = aiohttp.TCPConnector(
            force_close=True,
            enable_cleanup_closed=True,
            limit=4,
        )
        timeout = aiohttp.ClientTimeout(
            total=total,
            connect=self._CONNECT_TIMEOUT,
            sock_read=min(total, self._SOCK_READ_TIMEOUT),
        )
        return aiohttp.ClientSession(connector=connector, timeout=timeout)

    def _cache_path(self, ticker: str) -> Path:
        return self._cache_dir / f"{ticker.upper()}.csv"

    def _load_cache(self, ticker: str, start_date: str, *, allow_stale: bool = False) -> pd.DataFrame | None:
        path = self._cache_path(ticker)
        if not path.exists():
            return None
        age = time.time() - path.stat().st_mtime
        if not allow_stale and age > _CACHE_MAX_AGE_SEC:
            log.debug("Cache stale for {} ({:.0f}h old)", ticker, age / 3600)
            return None
        try:
            df = pd.read_csv(path)
            if "datetime" not in df.columns:
                return None
            df["datetime"] = pd.to_datetime(df["datetime"])
            df = df[df["datetime"] >= pd.Timestamp(start_date)]
            if len(df) >= 50:
                log.info("MOEX cache hit: {} — {} rows ({})", ticker, len(df), path.name)
                return df.reset_index(drop=True)
        except Exception as exc:
            log.warning("Failed to read cache for {}: {}", ticker, exc)
        return None

    def _save_cache(self, ticker: str, df: pd.DataFrame) -> None:
        if df.empty:
            return
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        path = self._cache_path(ticker)
        df.to_csv(path, index=False)
        log.info("MOEX cache saved: {} → {}", ticker, path)

    async def _rate_limit(self) -> None:
        now = time.monotonic()
        self._last_request_times = [t for t in self._last_request_times if now - t < 1.0]
        if len(self._last_request_times) >= self._MAX_RPS:
            sleep_for = 1.0 - (now - self._last_request_times[0])
            if sleep_for > 0:
                await asyncio.sleep(sleep_for)
        self._last_request_times.append(time.monotonic())

    @staticmethod
    def _fetch_json_urllib(url: str, params: dict[str, Any], *, timeout: float | None = None) -> dict[str, Any]:
        query = urlencode({k: str(v) for k, v in params.items()})
        full_url = f"{url}?{query}"
        req = Request(full_url, headers=MOEXDataLoader._REQUEST_HEADERS)
        with urlopen(req, timeout=timeout or MOEXDataLoader._URLLIB_TIMEOUT) as resp:
            raw = resp.read().decode("utf-8")
        return json.loads(raw)

    async def _get_json_aiohttp(
        self,
        url: str,
        params: dict[str, Any],
        *,
        max_retries: int,
        total_timeout: float,
    ) -> dict[str, Any]:
        last_exc: BaseException | None = None
        for attempt in range(1, max_retries + 1):
            try:
                await self._rate_limit()
                async with self._create_session(total_timeout) as session:
                    async with session.get(
                        url, params=params, headers=self._REQUEST_HEADERS
                    ) as resp:
                        resp.raise_for_status()
                        return await resp.json()
            except (aiohttp.ClientError, asyncio.TimeoutError, ssl.SSLError, OSError) as exc:
                last_exc = exc
                if attempt >= max_retries:
                    break
                wait = self._RETRY_BACKOFF * (2 ** (attempt - 1))
                log.warning(
                    "MOEX aiohttp failed ({}/{}): {} — retry {:.1f}s",
                    attempt,
                    max_retries,
                    exc,
                    wait,
                )
                await asyncio.sleep(wait)
        assert last_exc is not None
        raise last_exc

    async def _get_json(
        self,
        url: str,
        params: dict[str, Any],
        *,
        max_retries: int,
        total_timeout: float,
    ) -> dict[str, Any]:
        try:
            return await self._get_json_aiohttp(
                url, params, max_retries=max_retries, total_timeout=total_timeout
            )
        except Exception as exc:
            log.warning("MOEX aiohttp exhausted, trying urllib fallback: {}", exc)
        try:
            return await asyncio.to_thread(
                self._fetch_json_urllib, url, params, timeout=total_timeout,
            )
        except (URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
            raise TimeoutError(f"MOEX unreachable (aiohttp + urllib failed): {exc}") from exc

    async def fetch_candles(
        self,
        ticker: str,
        board: str = "TQBR",
        interval: int = 24,
        start_date: str = "2022-01-01",
        end_date: str | None = None,
        *,
        quick: bool = False,
        use_cache: bool | None = None,
    ) -> pd.DataFrame:
        """Fetch OHLCV candles. Uses cache → network (aiohttp → urllib) → stale cache."""
        use_cache = self._use_cache if use_cache is None else use_cache

        if use_cache:
            cached = self._load_cache(ticker, start_date)
            if cached is not None:
                return cached

        url = (
            f"{self.BASE_URL}/engines/stock/markets/shares"
            f"/boards/{board}/securities/{ticker}/candles.json"
        )
        log.info("MOEX: fetching {} from {} (quick={})", ticker, start_date, quick)
        max_retries = self._QUICK_MAX_RETRIES if quick else self._MAX_RETRIES
        timeout = self._QUICK_TIMEOUT if quick else self._TOTAL_TIMEOUT

        try:
            df = await self._paginate_candles(
                url,
                interval,
                start_date,
                end_date,
                label=ticker,
                max_retries=max_retries,
                total_timeout=timeout,
            )
        except Exception as exc:
            if use_cache:
                stale = self._load_cache(ticker, start_date, allow_stale=True)
                if stale is not None:
                    log.warning("MOEX network failed for {}, using stale cache: {}", ticker, exc)
                    return stale
            raise

        if not df.empty and use_cache:
            self._save_cache(ticker, df)
        return df

    async def fetch_futures_candles(
        self,
        ticker: str,
        interval: int = 24,
        start_date: str = "2022-01-01",
        end_date: str | None = None,
        *,
        quick: bool = False,
    ) -> pd.DataFrame:
        url = (
            f"{self.BASE_URL}/engines/futures/markets/forts"
            f"/boards/RFUD/securities/{ticker}/candles.json"
        )
        max_retries = self._QUICK_MAX_RETRIES if quick else self._MAX_RETRIES
        timeout = self._QUICK_TIMEOUT if quick else self._TOTAL_TIMEOUT
        return await self._paginate_candles(
            url, interval, start_date, end_date, label=ticker,
            max_retries=max_retries, total_timeout=timeout,
        )

    async def _paginate_candles(
        self,
        url: str,
        interval: int,
        start_date: str,
        end_date: str | None,
        label: str = "",
        *,
        max_retries: int = 2,
        total_timeout: float = 25.0,
    ) -> pd.DataFrame:
        all_rows: list[dict[str, Any]] = []
        start = 0
        page = 0
        tag = label or url.rsplit("/", 1)[-1]

        while True:
            page += 1
            params: dict[str, Any] = {
                "from": start_date,
                "interval": interval,
                "start": start,
                "iss.meta": "off",
            }
            if end_date:
                params["till"] = end_date

            log.info("MOEX: {} page {} (offset {})...", tag, page, start)
            data = await self._get_json(
                url, params, max_retries=max_retries, total_timeout=total_timeout
            )

            candles_block = self._extract_candles(data)
            if not candles_block:
                break

            all_rows.extend(candles_block)
            log.info("MOEX: {} page {} — +{} rows (total {})", tag, page, len(candles_block), len(all_rows))
            if len(candles_block) < self._PAGE_SIZE:
                break
            start += len(candles_block)

        if not all_rows:
            log.warning("No candle data returned for {} ({})", tag, url)
            return pd.DataFrame()

        log.info("MOEX: {} done — {} candles", tag, len(all_rows))
        return self._rows_to_dataframe(all_rows)

    @staticmethod
    def _rows_to_dataframe(all_rows: list[dict[str, Any]]) -> pd.DataFrame:
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
        candles_obj: Any = None
        if isinstance(data, list):
            for block in data:
                if isinstance(block, dict) and "candles" in block:
                    candles_obj = block["candles"]
                    break
        elif isinstance(data, dict):
            candles_obj = data.get("candles")

        if candles_obj is None:
            return []

        if isinstance(candles_obj, dict):
            columns = candles_obj.get("columns", [])
            rows = candles_obj.get("data", [])
            if columns and rows:
                return [dict(zip(columns, row)) for row in rows]
            return []

        if isinstance(candles_obj, list):
            return candles_obj
        return []

    async def fetch_orderbook(self, ticker: str, board: str = "TQBR") -> dict[str, Any]:
        url = (
            f"{self.BASE_URL}/engines/stock/markets/shares"
            f"/boards/{board}/securities/{ticker}/orderbook.json"
        )
        return await self._get_json(
            url, {"iss.meta": "off"}, max_retries=self._MAX_RETRIES, total_timeout=self._TOTAL_TIMEOUT
        )

    async def fetch_all_tickers(self, board: str = "TQBR") -> list[dict[str, Any]]:
        url = (
            f"{self.BASE_URL}/engines/stock/markets/shares"
            f"/boards/{board}/securities.json"
        )
        data = await self._get_json(
            url, {"iss.meta": "off"}, max_retries=self._MAX_RETRIES, total_timeout=self._TOTAL_TIMEOUT
        )
        securities = data.get("securities", {})
        columns = securities.get("columns", [])
        rows = securities.get("data", [])
        return [dict(zip(columns, row)) for row in rows]

    async def bulk_download(
        self,
        tickers: list[str],
        start_date: str = "2022-01-01",
        save_dir: str | None = None,
    ) -> dict[str, pd.DataFrame]:
        save_path = Path(save_dir) if save_dir else self._cache_dir
        save_path.mkdir(parents=True, exist_ok=True)
        results: dict[str, pd.DataFrame] = {}

        for ticker in tickers:
            try:
                log.info("Downloading {}", ticker)
                df = await self.fetch_candles(ticker, start_date=start_date)
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
