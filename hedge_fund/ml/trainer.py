"""Automated model training — delegates to unified ml.pipeline."""

from __future__ import annotations

import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np

from ..storage.database import Database, MLModelVersion
from ..utils.logger import get_logger
from .pipeline import run_ml_pipeline

log = get_logger("ml.trainer")


class AutoTrainer:
    """Retrains ML models on schedule with walk-forward validation."""

    def __init__(self, config: dict[str, Any], db: Database) -> None:
        self._config = config
        self._db = db
        self._models_dir = Path(config.get("models_dir", "hedge_fund/ml/models"))
        self._models_dir.mkdir(parents=True, exist_ok=True)
        self._min_samples = config.get("min_samples", 1000)
        self._retrain_interval_hours = config.get("retrain_interval_hours", 24)
        self._last_train_time = 0.0

    async def retrain_all(self) -> dict[str, Any]:
        """Retrain all models if enough time has passed."""
        now = time.time()
        if now - self._last_train_time < self._retrain_interval_hours * 3600:
            log.info(
                "Skipping retrain – last trained {:.1f}h ago",
                (now - self._last_train_time) / 3600,
            )
            return {"skipped": True}
        return await self.train_once()

    async def train_once(self) -> dict[str, Any]:
        """Retrain via unified pipeline (DB → MOEX → synthetic)."""
        log.info("Starting full model retrain cycle")
        result = await run_ml_pipeline(
            tickers=self._config.get("tickers"),
            models_dir=str(self._models_dir),
            min_samples=self._min_samples,
            start_date=self._config.get("start_date", "2022-01-01"),
            source="auto",
            db_url=self._config.get("timeseries_db_url"),
            db=self._db,
        )
        if "error" not in result:
            self._last_train_time = time.time()
        log.info("Retrain complete: {}", result)
        return result

    async def track_performance(
        self, model_name: str, predictions: np.ndarray, actuals: np.ndarray
    ) -> dict[str, float]:
        if predictions.ndim > 1:
            pred_classes = predictions.argmax(axis=1)
        else:
            pred_classes = (predictions > 0).astype(int)
        accuracy = float(np.mean(pred_classes == actuals))
        log.info("Live performance for {}: accuracy={:.4f}", model_name, accuracy)
        return {"model": model_name, "accuracy": accuracy, "n_samples": len(actuals)}

    async def save_model_version(
        self, model_name: str, metrics: dict[str, Any], file_path: str
    ) -> None:
        version = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        async with self._db.session() as sess:
            record = MLModelVersion(
                model_name=model_name,
                version=version,
                metrics_json=json.dumps(metrics),
                file_path=str(self._models_dir / file_path),
            )
            sess.add(record)
        log.info("Model version saved: {} v{}", model_name, version)
