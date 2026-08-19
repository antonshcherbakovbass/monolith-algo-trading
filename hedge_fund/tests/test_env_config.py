"""Tests for env config loader."""
from __future__ import annotations

import os

import pytest

from hedge_fund.core.env_config import apply_env_overrides, load_dotenv


class TestEnvConfig:
    def test_apply_env_overrides(self, monkeypatch):
        monkeypatch.setenv("MONOLITH_MODE", "live")
        monkeypatch.setenv("TINKOFF_TOKEN", "test-token")
        cfg = apply_env_overrides({"system": {}, "broker": {}})
        assert cfg["system"]["mode"] == "live"
        assert cfg["broker"]["tinkoff_token"] == "test-token"

    def test_load_dotenv(self, tmp_path, monkeypatch):
        env_file = tmp_path / ".env"
        env_file.write_text("MONOLITH_MODE=paper\n# comment\nFOO=bar\n", encoding="utf-8")
        monkeypatch.chdir(tmp_path)
        for key in ("MONOLITH_MODE", "FOO"):
            monkeypatch.delenv(key, raising=False)
        load_dotenv(".env")
        assert os.environ.get("MONOLITH_MODE") == "paper"
