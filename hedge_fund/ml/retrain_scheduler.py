"""Scheduled ML retraining while the trading system is running."""

from __future__ import annotations

import asyncio
import time
from typing import Any, Awaitable, Callable

from ..storage.database import Database
from ..utils.logger import get_logger
from .pipeline import run_ml_pipeline

log = get_logger("ml.retrain_scheduler")

NotifyCallback = Callable[[str], Awaitable[None]]
ReloadCallback = Callable[[dict[str, Any]], Awaitable[None]]


class MLRetrainScheduler:
    """Runs ML retraining on a fixed interval as a background asyncio task."""

    def __init__(
        self,
        config: dict[str, Any],
        db: Database,
        *,
        on_complete: ReloadCallback | None = None,
        notify: NotifyCallback | None = None,
    ) -> None:
        self._root_config = config
        self._ml_cfg = self._build_ml_config(config)
        self._db = db
        self._on_complete = on_complete
        self._notify = notify
        self._enabled = bool(self._ml_cfg.get("auto_retrain_enabled", True))
        self._interval_hours = float(self._ml_cfg.get("retrain_interval_hours", 24))
        self._check_interval_sec = float(self._ml_cfg.get("check_interval_sec", 3600))
        self._last_run = 0.0
        self._task: asyncio.Task[None] | None = None
        self._running = False

    @staticmethod
    def _build_ml_config(config: dict[str, Any]) -> dict[str, Any]:
        ml_cfg = dict(config.get("ml", {}))
        instruments = config.get("instruments", {})
        if "tickers" not in ml_cfg:
            ml_cfg["tickers"] = instruments.get("stocks", ["SBER", "GAZP", "LKOH"])
        if "models_dir" not in ml_cfg:
            ml_cfg["models_dir"] = "hedge_fund/ml/models"
        ml_cfg["timeseries_db_url"] = config.get("database", {}).get(
            "url", "sqlite+aiosqlite:///hedge_fund.db"
        )
        return ml_cfg

    @property
    def enabled(self) -> bool:
        return self._enabled

    async def start(self) -> None:
        if not self._enabled:
            log.info("ML auto-retrain disabled in config")
            return
        if self._task is not None:
            return
        self._running = True
        self._task = asyncio.create_task(self._loop(), name="ml-retrain-scheduler")
        log.info(
            "ML retrain scheduler started (every {:.0f}h, check every {:.0f}s)",
            self._interval_hours,
            self._check_interval_sec,
        )

    async def stop(self) -> None:
        self._running = False
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

    async def _loop(self) -> None:
        if self._ml_cfg.get("retrain_on_startup", False):
            await self._maybe_retrain(force=True)
        while self._running:
            try:
                await self._maybe_retrain()
            except Exception:
                log.exception("ML retrain scheduler iteration failed")
            await asyncio.sleep(self._check_interval_sec)

    async def _maybe_retrain(self, force: bool = False) -> dict[str, Any] | None:
        now = time.time()
        elapsed_hours = (now - self._last_run) / 3600 if self._last_run else float("inf")
        if not force and elapsed_hours < self._interval_hours:
            return None

        log.info("Starting scheduled ML retrain (elapsed={:.1f}h)", elapsed_hours)
        result = await self.run_retrain()
        self._last_run = time.time()

        if self._on_complete is not None:
            try:
                await self._on_complete(result)
            except Exception:
                log.exception("ML reload callback failed")

        if self._notify is not None:
            await self._send_notification(result)

        return result

    async def run_retrain(self) -> dict[str, Any]:
        """Run unified ML pipeline (DB → MOEX → synthetic)."""
        return await run_ml_pipeline(
            tickers=self._ml_cfg.get("tickers"),
            models_dir=self._ml_cfg.get("models_dir", "hedge_fund/ml/models"),
            min_samples=int(self._ml_cfg.get("min_samples", 1000)),
            start_date=self._ml_cfg.get("start_date", "2022-01-01"),
            source="auto",
            db_url=self._ml_cfg.get("timeseries_db_url"),
            db=self._db,
        )

    async def _send_notification(self, result: dict[str, Any]) -> None:
        if self._notify is None:
            return
        if result.get("skipped"):
            return
        if "error" in result:
            msg = f"⚠️ *ML retrain failed*\n`{result['error']}`"
        else:
            source = result.get("source", "?")
            samples = result.get("samples", "n/a")
            scalping = result.get("scalping", {})
            acc = scalping.get("accuracy_mean", "n/a")
            msg = (
                f"✅ *ML retrain complete*\n"
                f"Source: `{source}`\n"
                f"Samples: `{samples}`\n"
                f"Scalping WF acc: `{acc}`"
            )
        try:
            await self._notify(msg)
        except Exception:
            log.exception("Failed to send ML retrain notification")
