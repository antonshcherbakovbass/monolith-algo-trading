"""Tests for ML inference module."""
from __future__ import annotations

import numpy as np
import pytest

from hedge_fund.ml.inference import ModelRegistry


class TestModelRegistry:
    def test_no_models_graceful(self):
        registry = ModelRegistry(models_dir="/nonexistent/path")
        assert registry.has_models is False
        assert registry.predict_ticker("SBER", [{"close": 250}] * 60) is None

    def test_signal_from_prediction_scalping_up(self):
        registry = ModelRegistry(models_dir="/nonexistent/path")
        pred = {
            "ticker": "SBER",
            "price": 250.0,
            "scalping_up": 0.7,
            "scalping_down": 0.15,
            "scalping_flat": 0.15,
        }
        result = registry.signal_from_prediction(pred)
        assert result is not None
        assert result[0] == "BUY"
        assert result[1] > 0.5

    def test_signal_from_prediction_swing(self):
        registry = ModelRegistry(models_dir="/nonexistent/path")
        pred = {"ticker": "GAZP", "price": 180.0, "swing_return": 0.012}
        result = registry.signal_from_prediction(pred)
        assert result is not None
        assert result[0] == "BUY"

    def test_signal_from_prediction_no_signal(self):
        registry = ModelRegistry(models_dir="/nonexistent/path")
        pred = {"ticker": "SBER", "price": 250.0, "swing_return": 0.001}
        assert registry.signal_from_prediction(pred) is None
