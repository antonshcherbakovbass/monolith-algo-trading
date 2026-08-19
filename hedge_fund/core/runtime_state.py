"""Runtime state bridge between main trading loop and desktop dashboard."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..utils.logger import get_logger

log = get_logger("core.runtime_state")

_LOGS_DIR = Path(__file__).resolve().parent.parent / "logs"
STATE_PATH = _LOGS_DIR / "runtime_state.json"
CONTROL_PATH = _LOGS_DIR / "runtime_control.json"


class RuntimeState:
    """Shared JSON state file for live dashboard updates."""

    @staticmethod
    def write(data: dict[str, Any]) -> None:
        _LOGS_DIR.mkdir(parents=True, exist_ok=True)
        payload = {
            **data,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        tmp = STATE_PATH.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(STATE_PATH)

    @staticmethod
    def read(max_age_sec: float = 30.0) -> dict[str, Any] | None:
        if not STATE_PATH.exists():
            return None
        try:
            data = json.loads(STATE_PATH.read_text(encoding="utf-8"))
            updated = data.get("updated_at")
            if updated:
                ts = datetime.fromisoformat(updated.replace("Z", "+00:00"))
                age = (datetime.now(timezone.utc) - ts).total_seconds()
                if age > max_age_sec:
                    return None
            return data
        except (json.JSONDecodeError, OSError, ValueError) as exc:
            log.debug("runtime state read failed: {}", exc)
            return None

    @staticmethod
    def request_emergency_stop() -> None:
        _LOGS_DIR.mkdir(parents=True, exist_ok=True)
        CONTROL_PATH.write_text(
            json.dumps({
                "action": "emergency_stop",
                "requested_at": datetime.now(timezone.utc).isoformat(),
            }),
            encoding="utf-8",
        )
        log.warning("Emergency stop requested via runtime control file")

    @staticmethod
    def read_control() -> dict[str, Any] | None:
        if not CONTROL_PATH.exists():
            return None
        try:
            return json.loads(CONTROL_PATH.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None

    @staticmethod
    def clear_control() -> None:
        if CONTROL_PATH.exists():
            CONTROL_PATH.unlink(missing_ok=True)
