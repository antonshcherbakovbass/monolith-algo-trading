"""Tests for runtime state bridge."""
from __future__ import annotations

import json

from hedge_fund.core.runtime_state import RuntimeState


class TestRuntimeState:
    def test_write_and_read(self, tmp_path, monkeypatch):
        state_file = tmp_path / "runtime_state.json"
        control_file = tmp_path / "runtime_control.json"
        monkeypatch.setattr("hedge_fund.core.runtime_state.STATE_PATH", state_file)
        monkeypatch.setattr("hedge_fund.core.runtime_state.CONTROL_PATH", control_file)
        monkeypatch.setattr("hedge_fund.core.runtime_state._LOGS_DIR", tmp_path)

        RuntimeState.write({"mode": "PAPER", "portfolio_value": 1_000_000})
        data = RuntimeState.read(max_age_sec=60)
        assert data is not None
        assert data["mode"] == "PAPER"
        assert data["portfolio_value"] == 1_000_000

    def test_emergency_stop_control(self, tmp_path, monkeypatch):
        state_file = tmp_path / "runtime_state.json"
        control_file = tmp_path / "runtime_control.json"
        monkeypatch.setattr("hedge_fund.core.runtime_state.STATE_PATH", state_file)
        monkeypatch.setattr("hedge_fund.core.runtime_state.CONTROL_PATH", control_file)
        monkeypatch.setattr("hedge_fund.core.runtime_state._LOGS_DIR", tmp_path)

        RuntimeState.request_emergency_stop()
        cmd = RuntimeState.read_control()
        assert cmd is not None
        assert cmd["action"] == "emergency_stop"
        RuntimeState.clear_control()
        assert RuntimeState.read_control() is None

    def test_stale_state_returns_none(self, tmp_path, monkeypatch):
        state_file = tmp_path / "runtime_state.json"
        monkeypatch.setattr("hedge_fund.core.runtime_state.STATE_PATH", state_file)
        monkeypatch.setattr("hedge_fund.core.runtime_state._LOGS_DIR", tmp_path)

        state_file.write_text(json.dumps({
            "mode": "PAPER",
            "updated_at": "2020-01-01T00:00:00+00:00",
        }), encoding="utf-8")
        assert RuntimeState.read(max_age_sec=10) is None
