"""Broker factory — creates the appropriate connector based on configuration."""
from __future__ import annotations

from typing import Any

from ..core.config_loader import normalize_broker_name
from ..utils.logger import get_logger
from .base import BaseBroker

logger = get_logger("brokers.factory")


class BrokerFactory:
    """Creates the appropriate broker connector based on config."""

    @staticmethod
    def create(broker_name: str, config: dict[str, Any]) -> BaseBroker:
        broker_name = normalize_broker_name(broker_name)
        brokers = BrokerFactory._broker_map()
        if broker_name not in brokers:
            available = ", ".join(brokers.keys())
            raise ValueError(f"Unknown broker '{broker_name}'. Available: {available}")

        cls = brokers[broker_name]
        kwargs = BrokerFactory._build_kwargs(broker_name, config)
        logger.info("creating broker: {} ({})", broker_name, cls.__name__)
        return cls(**kwargs)

    @staticmethod
    def _build_kwargs(broker_name: str, config: dict[str, Any]) -> dict[str, Any]:
        broker_cfg = config.get("broker", {})
        quik_cfg = config.get("quik", {})
        paper = config.get("system", {}).get("mode", "paper") == "paper"

        if broker_name == "sber_quik":
            return {
                "host": quik_cfg.get("host", "127.0.0.1"),
                "port": quik_cfg.get("port", 34130),
                "account": broker_cfg.get("account_id", ""),
                "client_code": broker_cfg.get("client_code", ""),
                "paper_trading": paper,
            }
        if broker_name == "tinkoff":
            return {
                "token": broker_cfg.get("tinkoff_token", ""),
                "account_id": broker_cfg.get("account_id", ""),
                "sandbox": broker_cfg.get("tinkoff_sandbox", paper),
            }
        if broker_name == "alor":
            return {
                "refresh_token": broker_cfg.get("alor_refresh_token", "") or broker_cfg.get("alor_token", ""),
                "portfolio": broker_cfg.get("account_id", ""),
            }
        if broker_name == "finam":
            return {
                "token": broker_cfg.get("finam_token", ""),
                "client_id": broker_cfg.get("finam_client_id", ""),
            }
        return {}

    @staticmethod
    def available_brokers() -> list[dict[str, Any]]:
        """Returns list of supported brokers with metadata."""
        return [
            {
                "id": "sber_quik",
                "name_ru": "Сбер / ВТБ через QUIK",
                "description_ru": "Подключение через терминал QUIK (LUA bridge). "
                                  "Требуется запущенный QUIK с LUA-скриптом.",
                "needs_quik": True,
                "has_api": False,
            },
            {
                "id": "tinkoff",
                "name_ru": "Т-Инвестиции (Тинькофф)",
                "description_ru": "Прямое API-подключение через gRPC. "
                                  "Поддержка sandbox для тестирования.",
                "needs_quik": False,
                "has_api": True,
            },
            {
                "id": "alor",
                "name_ru": "Алор Брокер",
                "description_ru": "REST + WebSocket API. OAuth2 авторизация. "
                                  "Реальное время через WebSocket.",
                "needs_quik": False,
                "has_api": True,
            },
            {
                "id": "finam",
                "name_ru": "Финам",
                "description_ru": "gRPC API для торговли и получения данных. "
                                  "Токен из личного кабинета.",
                "needs_quik": False,
                "has_api": True,
            },
        ]

    @staticmethod
    def _broker_map() -> dict[str, type[BaseBroker]]:
        from .quik_broker import QuikBroker
        from .tinkoff_broker import TinkoffBroker
        from .alor_broker import AlorBroker
        from .finam_broker import FinamBroker

        return {
            "sber_quik": QuikBroker,
            "tinkoff": TinkoffBroker,
            "alor": AlorBroker,
            "finam": FinamBroker,
        }

    @staticmethod
    def is_api_broker(broker_name: str) -> bool:
        return normalize_broker_name(broker_name) in ("tinkoff", "alor", "finam")
