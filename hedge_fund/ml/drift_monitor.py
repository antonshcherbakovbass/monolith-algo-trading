"""Feature drift monitoring for deployed ML models."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from ..utils.logger import get_logger

log = get_logger("ml.drift_monitor")

BASELINE_FILENAME = "baseline_stats.json"
DEFAULT_PSI_THRESHOLD = 0.2
DEFAULT_Z_THRESHOLD = 3.0


@dataclass
class DriftReport:
    drifted: bool
    max_psi: float
    max_z_score: float
    drifted_features: list[str] = field(default_factory=list)
    n_features: int = 0
    message: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "drifted": self.drifted,
            "max_psi": round(self.max_psi, 4),
            "max_z_score": round(self.max_z_score, 4),
            "drifted_features": self.drifted_features,
            "n_features": self.n_features,
            "message": self.message,
        }


class DriftMonitor:
    """Compares live feature distributions against training baseline."""

    def __init__(
        self,
        models_dir: str | Path,
        psi_threshold: float = DEFAULT_PSI_THRESHOLD,
        z_threshold: float = DEFAULT_Z_THRESHOLD,
    ) -> None:
        self._models_dir = Path(models_dir)
        self._psi_threshold = psi_threshold
        self._z_threshold = z_threshold
        self._baseline: dict[str, Any] | None = None

    @property
    def baseline_path(self) -> Path:
        return self._models_dir / BASELINE_FILENAME

    def load_baseline(self) -> dict[str, Any] | None:
        if self._baseline is not None:
            return self._baseline
        if not self.baseline_path.exists():
            return None
        self._baseline = json.loads(self.baseline_path.read_text(encoding="utf-8"))
        return self._baseline

    def save_baseline(self, features: pd.DataFrame) -> None:
        """Persist per-feature mean/std/histogram from training data."""
        self._models_dir.mkdir(parents=True, exist_ok=True)
        stats: dict[str, Any] = {"features": {}, "n_samples": len(features)}
        for col in features.columns:
            series = features[col].dropna()
            if series.empty:
                continue
            hist, bin_edges = np.histogram(series.values, bins=10)
            hist = hist.astype(float)
            hist = hist / max(hist.sum(), 1.0)
            stats["features"][col] = {
                "mean": float(series.mean()),
                "std": float(series.std()) if series.std() > 0 else 1e-6,
                "hist": hist.tolist(),
                "bin_edges": bin_edges.tolist(),
            }
        self.baseline_path.write_text(json.dumps(stats, indent=2), encoding="utf-8")
        self._baseline = stats
        log.info("Drift baseline saved: {} features", len(stats["features"]))

    @staticmethod
    def _psi(expected: np.ndarray, observed: np.ndarray) -> float:
        """Population Stability Index between two histograms."""
        eps = 1e-6
        expected = np.clip(expected, eps, None)
        observed = np.clip(observed, eps, None)
        expected = expected / expected.sum()
        observed = observed / observed.sum()
        return float(np.sum((observed - expected) * np.log(observed / expected)))

    def check(self, features: pd.DataFrame) -> DriftReport:
        baseline = self.load_baseline()
        if baseline is None or not baseline.get("features"):
            return DriftReport(
                drifted=False,
                max_psi=0.0,
                max_z_score=0.0,
                message="no baseline — drift check skipped",
            )

        max_psi = 0.0
        max_z = 0.0
        drifted_features: list[str] = []

        for col, ref in baseline["features"].items():
            if col not in features.columns:
                continue
            series = features[col].dropna()
            if len(series) < 5:
                continue

            # Z-score drift on mean
            ref_std = max(float(ref["std"]), 1e-6)
            z = abs(float(series.mean()) - float(ref["mean"])) / ref_std
            max_z = max(max_z, z)

            # PSI on histogram
            ref_hist = np.array(ref["hist"], dtype=float)
            bin_edges = np.array(ref["bin_edges"], dtype=float)
            obs_hist, _ = np.histogram(series.values, bins=bin_edges)
            obs_hist = obs_hist.astype(float)
            obs_hist = obs_hist / max(obs_hist.sum(), 1.0)
            psi = self._psi(ref_hist, obs_hist)
            max_psi = max(max_psi, psi)

            if psi >= self._psi_threshold or z >= self._z_threshold:
                drifted_features.append(col)

        drifted = len(drifted_features) > 0
        msg = (
            f"drift detected in {len(drifted_features)} features"
            if drifted
            else "features within baseline"
        )
        if drifted:
            log.warning(
                "Feature drift: max_psi={:.3f} max_z={:.2f} features={}",
                max_psi, max_z, drifted_features[:5],
            )

        return DriftReport(
            drifted=drifted,
            max_psi=max_psi,
            max_z_score=max_z,
            drifted_features=drifted_features,
            n_features=len(baseline["features"]),
            message=msg,
        )
