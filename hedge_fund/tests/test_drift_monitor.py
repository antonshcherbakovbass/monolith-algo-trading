"""Tests for ML drift monitor."""
from __future__ import annotations

import json

import numpy as np
import pandas as pd
import pytest

from hedge_fund.ml.drift_monitor import DriftMonitor


class TestDriftMonitor:
    def test_no_baseline_skips(self, tmp_path):
        monitor = DriftMonitor(tmp_path)
        df = pd.DataFrame({"a": [1.0, 2.0, 3.0]})
        report = monitor.check(df)
        assert report.drifted is False
        assert "no baseline" in report.message

    def test_detects_drift(self, tmp_path):
        monitor = DriftMonitor(tmp_path, psi_threshold=0.1, z_threshold=2.0)
        baseline = pd.DataFrame({"feat": np.random.normal(0, 1, 500)})
        monitor.save_baseline(baseline)

        shifted = pd.DataFrame({"feat": np.random.normal(5, 1, 100)})
        report = monitor.check(shifted)
        assert report.drifted is True
        assert report.max_psi > 0

    def test_stable_features_no_drift(self, tmp_path):
        monitor = DriftMonitor(tmp_path)
        rng = np.random.default_rng(42)
        baseline = pd.DataFrame({"feat": rng.normal(0, 1, 500)})
        monitor.save_baseline(baseline)
        similar = pd.DataFrame({"feat": rng.normal(0, 1, 100)})
        report = monitor.check(similar)
        assert report.drifted is False

    def test_baseline_persisted(self, tmp_path):
        monitor = DriftMonitor(tmp_path)
        monitor.save_baseline(pd.DataFrame({"x": [1.0, 2.0, 3.0]}))
        assert (tmp_path / "baseline_stats.json").exists()
        data = json.loads((tmp_path / "baseline_stats.json").read_text())
        assert "features" in data
