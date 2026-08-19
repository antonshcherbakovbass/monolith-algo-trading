"""Tests for ML retrain scheduler."""
from __future__ import annotations

import time
from unittest.mock import AsyncMock, patch

import pytest

from hedge_fund.ml.retrain_scheduler import MLRetrainScheduler


@pytest.fixture
def config() -> dict:
    return {
        "ml": {
            "auto_retrain_enabled": True,
            "retrain_interval_hours": 24,
            "retrain_on_startup": False,
            "check_interval_sec": 60,
            "models_dir": "hedge_fund/ml/models",
            "min_samples": 100,
        },
        "instruments": {"stocks": ["SBER", "GAZP"]},
        "database": {"url": "sqlite+aiosqlite:///test.db"},
    }


@pytest.fixture
def db():
    from unittest.mock import MagicMock
    return MagicMock()


class TestMLRetrainScheduler:
    def test_disabled_scheduler(self, config, db):
        config["ml"]["auto_retrain_enabled"] = False
        scheduler = MLRetrainScheduler(config, db)
        assert scheduler.enabled is False

    @pytest.mark.asyncio
    async def test_start_stop(self, config, db):
        scheduler = MLRetrainScheduler(config, db)
        with patch.object(scheduler, "_loop", new_callable=AsyncMock):
            await scheduler.start()
            assert scheduler._task is not None
            await scheduler.stop()
            assert scheduler._task is None

    @pytest.mark.asyncio
    async def test_run_retrain_calls_pipeline(self, config, db):
        scheduler = MLRetrainScheduler(config, db)
        with patch("hedge_fund.ml.retrain_scheduler.run_ml_pipeline", new_callable=AsyncMock) as run:
            run.return_value = {"source": "synthetic", "scalping": {"accuracy_mean": 0.6}}
            result = await scheduler.run_retrain()
        assert result["source"] == "synthetic"
        run.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_on_complete_callback(self, config, db):
        callback = AsyncMock()
        scheduler = MLRetrainScheduler(config, db, on_complete=callback)
        with patch.object(scheduler, "run_retrain", new_callable=AsyncMock) as run:
            run.return_value = {"scalping": {}}
            await scheduler._maybe_retrain(force=True)
        callback.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_interval_guard(self, config, db):
        scheduler = MLRetrainScheduler(config, db)
        scheduler._last_run = time.time()
        with patch.object(scheduler, "run_retrain", new_callable=AsyncMock) as run:
            result = await scheduler._maybe_retrain()
        assert result is None
        run.assert_not_awaited()
