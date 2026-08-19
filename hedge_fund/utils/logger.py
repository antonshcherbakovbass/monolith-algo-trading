from __future__ import annotations

import sys
from pathlib import Path

from loguru import logger

_LOGS_DIR = Path(__file__).resolve().parent.parent / "logs"
_LOGS_DIR.mkdir(exist_ok=True)

_CONFIGURED = False


def _configure_once() -> None:
    global _CONFIGURED
    if _CONFIGURED:
        return
    _CONFIGURED = True

    logger.remove()

    logger.add(
        sys.stderr,
        level="DEBUG",
        format=(
            "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{extra[module]}</cyan> | "
            "<level>{message}</level>"
        ),
        colorize=True,
    )

    logger.add(
        _LOGS_DIR / "app.log",
        level="DEBUG",
        rotation="10 MB",
        retention=5,
        encoding="utf-8",
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {extra[module]} | {message}",
    )

    logger.add(
        _LOGS_DIR / "trades.log",
        level="INFO",
        rotation="10 MB",
        retention=5,
        encoding="utf-8",
        filter=lambda r: r["extra"].get("module", "").startswith("trade"),
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {extra[module]} | {message}",
    )

    logger.add(
        _LOGS_DIR / "risk.log",
        level="INFO",
        rotation="10 MB",
        retention=5,
        encoding="utf-8",
        filter=lambda r: r["extra"].get("module", "").startswith("risk"),
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {extra[module]} | {message}",
    )

    logger.add(
        _LOGS_DIR / "agents.log",
        level="INFO",
        rotation="10 MB",
        retention=5,
        encoding="utf-8",
        filter=lambda r: r["extra"].get("module", "").startswith("agent"),
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {extra[module]} | {message}",
    )


def get_logger(name: str) -> logger.__class__:
    """Return a logger instance bound to *name*.

    Messages logged through the returned object carry ``extra["module"]``
    equal to *name*, which is used for routing to the correct log file
    (trades, risk, agents) and for console formatting.
    """
    _configure_once()
    return logger.bind(module=name)
