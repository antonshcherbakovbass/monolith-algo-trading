"""Tests for live smoke test script (mocked — no real brokers)."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from hedge_fund.scripts.live_smoke_test import run_smoke_tests, smoke_test_quik, smoke_test_tinkoff


class TestLiveSmoke:
    @pytest.mark.asyncio
    async def test_quik_success(self):
        mock_connector = MagicMock()
        mock_connector.connect = AsyncMock()
        mock_connector.request = AsyncMock(return_value={"version": "1.0"})
        mock_connector.close = AsyncMock()

        with patch("hedge_fund.quik.connector.QuikConnector", return_value=mock_connector):
            result = await smoke_test_quik("127.0.0.1", 34130)
        assert result["ok"] is True

    @pytest.mark.asyncio
    async def test_tinkoff_skipped_without_token(self):
        result = await smoke_test_tinkoff(token="", sandbox=True)
        assert result.get("skipped") is True

    @pytest.mark.asyncio
    async def test_run_smoke_tests_config(self):
        config = {
            "quik": {"host": "127.0.0.1", "port": 34130},
            "broker": {"tinkoff_token": "", "tinkoff_sandbox": True},
        }
        with patch("hedge_fund.scripts.live_smoke_test.smoke_test_quik", new_callable=AsyncMock) as q:
            with patch("hedge_fund.scripts.live_smoke_test.smoke_test_tinkoff", new_callable=AsyncMock) as t:
                q.return_value = {"broker": "quik", "ok": True}
                t.return_value = {"broker": "tinkoff", "skipped": True}
                results = await run_smoke_tests("all", config)
        assert len(results) == 2
