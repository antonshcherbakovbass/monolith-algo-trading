"""Helpers for normalizing settings.yaml into runtime-friendly structures."""
from __future__ import annotations

from typing import Any

BROKER_ALIASES: dict[str, str] = {
    "sber": "sber_quik",
    "vtb": "sber_quik",
    "quik": "sber_quik",
}


def normalize_broker_name(name: str) -> str:
    return BROKER_ALIASES.get(name.lower(), name.lower())


def agents_as_dict(config: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Convert agents list from YAML into {name: entry} dict."""
    agents = config.get("agents", {})
    if isinstance(agents, list):
        return {entry["name"]: entry for entry in agents if isinstance(entry, dict) and "name" in entry}
    if isinstance(agents, dict):
        return agents
    return {}


def get_agent_entry(config: dict[str, Any], name: str) -> dict[str, Any]:
    return agents_as_dict(config).get(name, {})


def get_agent_params(config: dict[str, Any], name: str) -> dict[str, Any]:
    entry = get_agent_entry(config, name)
    params = entry.get("params", {})
    return params if isinstance(params, dict) else {}


def is_agent_enabled(config: dict[str, Any], name: str) -> bool:
    entry = get_agent_entry(config, name)
    return entry.get("enabled", True)


def class_code_for_ticker(ticker: str, config: dict[str, Any]) -> str:
    instruments = config.get("instruments", {})
    if ticker in instruments.get("futures", []):
        return "RFUD"
    return "TQBR"
