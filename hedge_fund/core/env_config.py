"""Load config from YAML with .env overrides for secrets."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

from ..utils.logger import get_logger

log = get_logger("core.env_config")

# Map env var → config path (dot-separated)
_ENV_MAP: dict[str, str] = {
    "MONOLITH_MODE": "system.mode",
    "MONOLITH_LOG_LEVEL": "system.log_level",
    "QUIK_HOST": "quik.host",
    "QUIK_PORT": "quik.port",
    "BROKER_NAME": "broker.name",
    "BROKER_ACCOUNT_ID": "broker.account_id",
    "BROKER_CLIENT_CODE": "broker.client_code",
    "TINKOFF_TOKEN": "broker.tinkoff_token",
    "TINKOFF_SANDBOX": "broker.tinkoff_sandbox",
    "ALOR_TOKEN": "broker.alor_token",
    "FINAM_TOKEN": "broker.finam_token",
    "TELEGRAM_TOKEN": "telegram.token",
    "TELEGRAM_CHAT_ID": "telegram.chat_id",
    "OLLAMA_BASE_URL": "ai.base_url",
    "DATABASE_URL": "database.url",
    "ML_MODELS_DIR": "ml.models_dir",
    "ML_AUTO_RETRAIN": "ml.auto_retrain_enabled",
    "ML_DRIFT_PSI_THRESHOLD": "ml.drift_psi_threshold",
}


def _set_nested(cfg: dict[str, Any], path: str, value: Any) -> None:
    keys = path.split(".")
    node = cfg
    for key in keys[:-1]:
        node = node.setdefault(key, {})
    node[keys[-1]] = value


def _coerce_value(key: str, raw: str) -> Any:
    if key in ("QUIK_PORT",):
        return int(raw)
    if key in ("TINKOFF_SANDBOX", "ML_AUTO_RETRAIN"):
        return raw.lower() in ("1", "true", "yes", "on")
    if key in ("ML_DRIFT_PSI_THRESHOLD",):
        return float(raw)
    return raw


def load_dotenv(path: str | Path = ".env") -> None:
    """Minimal .env loader (no external dependency)."""
    env_path = Path(path)
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def apply_env_overrides(config: dict[str, Any]) -> dict[str, Any]:
    """Overlay environment variables onto config dict."""
    for env_key, cfg_path in _ENV_MAP.items():
        raw = os.environ.get(env_key)
        if raw is not None and raw != "":
            _set_nested(config, cfg_path, _coerce_value(env_key, raw))
            log.debug("Config override from env: {}", cfg_path)
    return config


def load_config(config_path: str | Path = "hedge_fund/config/settings.yaml") -> dict[str, Any]:
    """Load YAML config + .env overrides."""
    load_dotenv()
    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(f"Config not found: {path}")
    with open(path, encoding="utf-8") as f:
        config = yaml.safe_load(f) or {}
    return apply_env_overrides(config)
