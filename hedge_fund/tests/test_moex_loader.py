"""Tests for MOEX ISS data loader (no network)."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pandas as pd
import pytest

from hedge_fund.data.moex_loader import MOEXDataLoader


def _sample_ohlcv(n: int, start: str = "2024-01-01") -> pd.DataFrame:
    dates = pd.date_range(start, periods=n, freq="D")
    close = 100.0 + pd.Series(range(n), dtype=float)
    return pd.DataFrame({
        "datetime": dates,
        "open": close * 0.99,
        "high": close * 1.01,
        "low": close * 0.98,
        "close": close,
        "volume": [1000] * n,
        "value": close * 1000,
    })


def _candles_payload(rows: list[list]) -> dict:
    return {
        "candles": {
            "columns": ["begin", "open", "close", "high", "low", "volume", "value"],
            "data": rows,
        }
    }


class TestMOEXDataLoader:
    def test_extract_candles_dict_format(self):
        data = _candles_payload([["2024-01-02", 250.0, 251.0, 252.0, 249.0, 1000, 250000.0]])
        rows = MOEXDataLoader._extract_candles(data)
        assert len(rows) == 1
        assert rows[0]["begin"] == "2024-01-02"

    def test_extract_candles_empty(self):
        assert MOEXDataLoader._extract_candles({}) == []
        assert MOEXDataLoader._extract_candles({"candles": {"columns": [], "data": []}}) == []

    def test_rows_to_dataframe(self):
        rows = [{"begin": "2024-01-02", "open": 1.0, "high": 2.0, "low": 0.5, "close": 1.5, "volume": 100, "value": 150.0}]
        df = MOEXDataLoader._rows_to_dataframe(rows)
        assert list(df.columns) == ["datetime", "open", "high", "low", "close", "volume", "value"]
        assert len(df) == 1

    def test_cache_roundtrip(self, tmp_path):
        loader = MOEXDataLoader(cache_dir=tmp_path, use_cache=True)
        loader._save_cache("SBER", _sample_ohlcv(60))
        cached = loader._load_cache("SBER", "2024-01-01")
        assert cached is not None
        assert len(cached) == 60

    def test_cache_respects_start_date(self, tmp_path):
        loader = MOEXDataLoader(cache_dir=tmp_path, use_cache=True)
        old = _sample_ohlcv(60, start="2023-01-01")
        recent = _sample_ohlcv(60, start="2024-01-01")
        loader._save_cache("GAZP", pd.concat([old, recent], ignore_index=True))
        cached = loader._load_cache("GAZP", "2024-01-01")
        assert cached is not None
        assert cached["datetime"].min() >= pd.Timestamp("2024-01-01")
        assert len(cached) >= 50

    @pytest.mark.asyncio
    async def test_paginate_stops_on_short_page(self):
        loader = MOEXDataLoader(use_cache=False)
        full_page = [[f"2024-01-{i % 28 + 1:02d}", 1, 2, 3, 0.5, 100, 200] for i in range(500)]
        short_page = [[f"2024-02-{i:02d}", 1, 2, 3, 0.5, 100, 200] for i in range(1, 6)]
        page1 = _candles_payload(full_page)
        page2 = _candles_payload(short_page)

        with patch.object(loader, "_get_json", new_callable=AsyncMock) as get_json:
            get_json.side_effect = [page1, page2]
            df = await loader._paginate_candles(
                "http://example/candles.json",
                interval=24,
                start_date="2024-01-01",
                end_date=None,
                label="TEST",
                max_retries=1,
                total_timeout=5.0,
            )
        assert len(df) == 505
        assert get_json.await_count == 2

    @pytest.mark.asyncio
    async def test_fetch_candles_uses_cache_without_network(self, tmp_path):
        loader = MOEXDataLoader(cache_dir=tmp_path, use_cache=True)
        loader._save_cache("SBER", _sample_ohlcv(60))

        with patch.object(loader, "_paginate_candles", new_callable=AsyncMock) as paginate:
            result = await loader.fetch_candles("SBER", start_date="2024-01-01")
            paginate.assert_not_awaited()
        assert len(result) == 60
