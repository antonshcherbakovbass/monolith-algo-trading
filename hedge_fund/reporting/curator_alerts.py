"""Уведомления для куратора через отдельный Telegram-бот."""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Optional

from ..utils.logger import get_logger

logger = get_logger(__name__)


class CuratorAlerts:
    """Отправляет алерты куратору (второй Telegram-бот для наблюдателя)."""

    def __init__(self, curator_token: str, curator_chat_id: str):
        self.curator_token = curator_token
        self.curator_chat_id = curator_chat_id
        self._base_url = f"https://api.telegram.org/bot{curator_token}"

    async def _send_message(self, text: str) -> bool:
        """Отправляет сообщение через Telegram API."""
        try:
            import aiohttp

            async with aiohttp.ClientSession() as session:
                url = f"{self._base_url}/sendMessage"
                payload = {
                    "chat_id": self.curator_chat_id,
                    "text": text,
                    "parse_mode": "HTML",
                }
                async with session.post(url, json=payload) as resp:
                    if resp.status == 200:
                        logger.info("Curator alert sent successfully")
                        return True
                    logger.error(f"Curator alert failed: {resp.status}")
                    return False
        except Exception as e:
            logger.error(f"Failed to send curator alert: {e}")
            return False

    def send_alert(self, alert_type: str, details: dict) -> None:
        """Отправляет форматированное уведомление куратору."""
        message = self._format_alert(alert_type, details)
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.ensure_future(self._send_message(message))
            else:
                loop.run_until_complete(self._send_message(message))
        except RuntimeError:
            asyncio.run(self._send_message(message))

    def _format_alert(self, alert_type: str, details: dict) -> str:
        """Форматирует алерт в понятное сообщение для куратора."""
        timestamp = datetime.now().strftime("%d.%m.%Y %H:%M")
        header = f"⏰ {timestamp}\n\n"

        formatters = {
            "daily_loss": self._format_daily_loss,
            "emergency_stop": self._format_emergency_stop,
            "live_mode": self._format_live_mode,
            "system_error": self._format_system_error,
            "large_trade": self._format_large_trade,
        }

        formatter = formatters.get(alert_type, self._format_generic)
        return header + formatter(details)

    def _format_daily_loss(self, details: dict) -> str:
        loss = details.get("loss_amount", 0)
        threshold = details.get("threshold", 0)
        return (
            f"🔴 <b>ПРЕВЫШЕН ЛИМИТ ДНЕВНЫХ ПОТЕРЬ</b>\n\n"
            f"Убыток за день: {loss:,.0f} ₽\n"
            f"Допустимый лимит: {threshold:,.0f} ₽\n\n"
            f"Система может приостановить торговлю автоматически."
        )

    def _format_emergency_stop(self, details: dict) -> str:
        reason = details.get("reason", "не указана")
        return (
            f"🛑 <b>АВАРИЙНАЯ ОСТАНОВКА</b>\n\n"
            f"Торговля полностью остановлена!\n"
            f"Причина: {reason}\n\n"
            f"Все позиции закрываются. Требуется внимание."
        )

    def _format_live_mode(self, details: dict) -> str:
        enabled = details.get("enabled", False)
        if enabled:
            return (
                "⚡ <b>ВКЛЮЧЁН РЕЖИМ РЕАЛЬНОЙ ТОРГОВЛИ</b>\n\n"
                "Система переведена в боевой режим.\n"
                "Все сделки теперь совершаются на реальные деньги."
            )
        return "✅ Система переведена в бумажный (тестовый) режим."

    def _format_system_error(self, details: dict) -> str:
        error = details.get("error", "неизвестная ошибка")
        component = details.get("component", "система")
        return (
            f"⚠️ <b>СИСТЕМНАЯ ОШИБКА</b>\n\n"
            f"Компонент: {component}\n"
            f"Ошибка: {error}\n\n"
            f"Возможно, потребуется перезапуск."
        )

    def _format_large_trade(self, details: dict) -> str:
        ticker = details.get("ticker", "???")
        amount = details.get("amount", 0)
        direction = details.get("direction", "покупка")
        pct = details.get("portfolio_pct", 0)
        return (
            f"💼 <b>КРУПНАЯ СДЕЛКА</b>\n\n"
            f"Инструмент: {ticker}\n"
            f"Направление: {direction}\n"
            f"Сумма: {amount:,.0f} ₽ ({pct:.1f}% портфеля)"
        )

    def _format_generic(self, details: dict) -> str:
        message = details.get("message", str(details))
        return f"ℹ️ <b>Уведомление</b>\n\n{message}"
