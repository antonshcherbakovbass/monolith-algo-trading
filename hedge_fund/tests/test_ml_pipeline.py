"""Tests for unified ML pipeline."""
from __future__ import annotations

import pytest

from hedge_fund.ml.pipeline import load_frames_synthetic, prepare_features_from_frames, run_ml_pipeline


class TestMLPipeline:
    def test_synthetic_frames_prepare(self):
        frames = load_frames_synthetic(n=2500)
        X, y_cls, y_reg, _, names = prepare_features_from_frames(frames, min_samples=500)
        assert len(X) >= 500
        assert X.shape[1] > 10
        assert len(y_cls) == len(X)

    @pytest.mark.asyncio
    async def test_run_synthetic_pipeline(self, tmp_path):
        result = await run_ml_pipeline(
            source="synthetic",
            min_samples=500,
            models_dir=str(tmp_path),
        )
        assert "error" not in result
        assert (tmp_path / "scalping_latest.pkl").exists()
        assert (tmp_path / "swing_latest.pkl").exists()
        assert (tmp_path / "baseline_stats.json").exists()
        assert (tmp_path / "manifest.json").exists()
