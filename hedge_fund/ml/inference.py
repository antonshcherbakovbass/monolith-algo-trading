"""Runtime ML model loading and inference for trading agents."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from ..utils.logger import get_logger
from .features import FeatureGenerator
from .models import ScalpingModel, SwingModel
from .drift_monitor import DriftMonitor, DriftReport

log = get_logger("ml.inference")

_MODEL_SEARCH_DIRS = [
    Path(__file__).resolve().parent / "models",
    Path(__file__).resolve().parent.parent / "models",
]


class ModelRegistry:
    """Loads trained models if available and runs lightweight inference."""

    def __init__(self, models_dir: str | Path | None = None, drift_psi_threshold: float = 0.2) -> None:
        self._models_dir = Path(models_dir) if models_dir else None
        self._scalping: ScalpingModel | None = None
        self._swing: SwingModel | None = None
        self._feature_gen = FeatureGenerator()
        self._drift_monitor: DriftMonitor | None = None
        self._last_drift: DriftReport | None = None
        self._loaded = False
        self._drift_psi_threshold = drift_psi_threshold
        self._load_models()

    @property
    def last_drift_report(self) -> DriftReport | None:
        return self._last_drift

    @property
    def drift_detected(self) -> bool:
        return bool(self._last_drift and self._last_drift.drifted)

    @property
    def has_models(self) -> bool:
        return self._scalping is not None or self._swing is not None

    def _resolve_path(self, filename: str) -> Path | None:
        candidates: list[Path] = []
        if self._models_dir is not None:
            candidates.append(self._models_dir / filename)
        else:
            for base in _MODEL_SEARCH_DIRS:
                candidates.append(base / filename)
        for path in candidates:
            if path.exists():
                return path
        return None

    def _load_models(self) -> None:
        scalping_path = self._resolve_path("scalping_latest.pkl")
        swing_path = self._resolve_path("swing_latest.pkl")

        if scalping_path:
            try:
                model = ScalpingModel()
                model.load(scalping_path)
                self._scalping = model
                log.info("Loaded scalping model from {}", scalping_path)
            except Exception as exc:
                log.warning("Failed to load scalping model: {}", exc)

        if swing_path:
            try:
                model = SwingModel()
                model.load(swing_path)
                self._swing = model
                log.info("Loaded swing model from {}", swing_path)
            except Exception as exc:
                log.warning("Failed to load swing model: {}", exc)

        self._loaded = True
        if self._models_dir:
            self._drift_monitor = DriftMonitor(self._models_dir, psi_threshold=self._drift_psi_threshold)
        elif self._scalping is not None or self._swing is not None:
            for base in _MODEL_SEARCH_DIRS:
                if (base / "baseline_stats.json").exists():
                    self._drift_monitor = DriftMonitor(base, psi_threshold=self._drift_psi_threshold)
                    break

    def reload(self) -> bool:
        """Reload models from disk after retraining."""
        self._scalping = None
        self._swing = None
        self._load_models()
        log.info("ModelRegistry reloaded (has_models={})", self.has_models)
        return self.has_models

    def predict_ticker(self, ticker: str, candles: list[dict[str, Any]]) -> dict[str, Any] | None:
        """Return ML prediction dict or None if models/data unavailable."""
        if not self.has_models or len(candles) < 50:
            return None

        try:
            df = pd.DataFrame([
                {
                    "open": float(c.get("open", c.get("close", 0))),
                    "high": float(c.get("high", c.get("close", 0))),
                    "low": float(c.get("low", c.get("close", 0))),
                    "close": float(c.get("close", 0)),
                    "volume": float(c.get("volume", 0)),
                }
                for c in candles
            ])
            features = self._feature_gen.generate(df).dropna()
            if features.empty:
                return None
            features = self._feature_gen.normalize(features)

            if self._drift_monitor is not None:
                self._last_drift = self._drift_monitor.check(features.tail(50))
                if self._last_drift.drifted:
                    log.warning("Feature drift for {}: {}", ticker, self._last_drift.message)

            X = features.iloc[[-1]].values.astype(np.float64)

            result: dict[str, Any] = {"ticker": ticker, "price": float(df["close"].iloc[-1])}

            if self._scalping is not None:
                proba = self._scalping.predict(X)[0]
                # classes: 0=down, 1=flat, 2=up (typical multi-class)
                down_p, flat_p, up_p = float(proba[0]), float(proba[1]), float(proba[2])
                result.update({
                    "scalping_down": down_p,
                    "scalping_flat": flat_p,
                    "scalping_up": up_p,
                    "direction": "up" if up_p >= max(down_p, flat_p) else ("down" if down_p >= flat_p else "flat"),
                    "confidence": max(down_p, flat_p, up_p),
                })

            if self._swing is not None:
                predicted_return = float(self._swing.predict(X)[0])
                result["swing_return"] = predicted_return

            return result
        except Exception as exc:
            log.debug("ML inference failed for {}: {}", ticker, exc)
            return None

    def signal_from_prediction(self, prediction: dict[str, Any]) -> tuple[str, float, str] | None:
        """Convert prediction to (action, confidence, reasoning) or None."""
        ticker = prediction.get("ticker", "?")
        price = prediction.get("price", 0)

        up_p = prediction.get("scalping_up")
        down_p = prediction.get("scalping_down")
        if up_p is not None and down_p is not None:
            if up_p >= 0.55 and up_p > down_p + 0.1:
                return (
                    "BUY",
                    min(float(up_p), 0.85),
                    f"ML scalping: up={up_p:.0%} down={down_p:.0%} @ {price:.2f}",
                )
            if down_p >= 0.55 and down_p > up_p + 0.1:
                return (
                    "SELL",
                    min(float(down_p), 0.85),
                    f"ML scalping: down={down_p:.0%} up={up_p:.0%} @ {price:.2f}",
                )

        swing_ret = prediction.get("swing_return")
        if swing_ret is not None and abs(float(swing_ret)) >= 0.005:
            action = "BUY" if swing_ret > 0 else "SELL"
            conf = min(abs(float(swing_ret)) * 20, 0.75)
            return (
                action,
                conf,
                f"ML swing: expected return {float(swing_ret):+.2%} for {ticker}",
            )
        return None
