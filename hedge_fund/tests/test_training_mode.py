import json
from datetime import datetime, timezone, timedelta

import pytest

from hedge_fund.core.training_mode import TrainingMode


class TestTrainingMode:
    def test_in_training_period(self):
        tm = TrainingMode(start_date=datetime.now(timezone.utc), training_period_days=14)
        assert tm.is_in_training() is True

    def test_after_training_period(self):
        start = datetime.now(timezone.utc) - timedelta(days=15)
        tm = TrainingMode(start_date=start, training_period_days=14)
        assert tm.is_in_training() is False

    def test_days_remaining_during_training(self):
        start = datetime.now(timezone.utc) - timedelta(days=5)
        tm = TrainingMode(start_date=start, training_period_days=14)
        assert tm.get_days_remaining() == 9

    def test_days_remaining_after_training(self):
        start = datetime.now(timezone.utc) - timedelta(days=20)
        tm = TrainingMode(start_date=start, training_period_days=14)
        assert tm.get_days_remaining() == 0

    def test_accept_risk_disclaimer_persists(self, tmp_path, monkeypatch):
        risk_file = tmp_path / "risk_accepted.json"
        config_dir = tmp_path

        import hedge_fund.core.training_mode as mod
        monkeypatch.setattr(mod, "_CONFIG_DIR", config_dir)
        monkeypatch.setattr(mod, "_RISK_FILE", risk_file)

        tm = TrainingMode()
        tm.accept_risk_disclaimer()
        assert risk_file.exists()
        assert TrainingMode.has_accepted_risk() is True

    def test_has_accepted_risk_false_initially(self, tmp_path, monkeypatch):
        risk_file = tmp_path / "risk_accepted.json"
        import hedge_fund.core.training_mode as mod
        monkeypatch.setattr(mod, "_RISK_FILE", risk_file)
        assert TrainingMode.has_accepted_risk() is False

    def test_boundary_exactly_at_period_end(self):
        start = datetime.now(timezone.utc) - timedelta(days=14)
        tm = TrainingMode(start_date=start, training_period_days=14)
        assert tm.is_in_training() is False
