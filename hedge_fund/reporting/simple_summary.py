"""Генерация простых ежедневных/еженедельных сводок для Telegram."""

from __future__ import annotations

import random
from typing import Optional

from ..utils.logger import get_logger

logger = get_logger(__name__)

DAILY_TIPS = [
    "Терпение — лучший друг инвестора. Не торопитесь с решениями.",
    "Диверсификация — это ваша страховка. Не кладите все яйца в одну корзину.",
    "Рынок всегда даёт новые возможности. Пропустили сделку — будет следующая.",
    "Фиксируйте прибыль частями — это снижает стресс и защищает капитал.",
    "Убыточная сделка — это урок, а не провал. Главное — сделать выводы.",
    "Не торгуйте на эмоциях. Если злитесь или радуетесь — сделайте паузу.",
    "Лучше маленькая прибыль, чем большой убыток. Защита капитала — приоритет.",
    "Следите за новостями, но не реагируйте на каждый заголовок.",
    "Регулярный доход важнее разовой удачи. Стабильность — ключ к успеху.",
    "Не увеличивайте позицию в убыточной сделке — это частая ошибка.",
    "Отдых — часть стратегии. Уставший трейдер принимает плохие решения.",
    "Ведите дневник сделок — это помогает находить свои слабые места.",
    "Рынок будет и завтра. Не нужно ловить каждое движение.",
    "Маленькие шаги каждый день приводят к большим результатам за год.",
    "Доверяйте системе. Она работает по правилам, а не по эмоциям.",
    "Лучшая сделка — та, которую вы не совершили, когда не были уверены.",
]


class SimpleSummary:
    """Генерирует дружелюбные сводки на простом русском языке."""

    def generate_daily_summary(
        self,
        portfolio_value: float,
        daily_pnl: float,
        trades_count: int,
        wins: int,
        losses: int,
        best_trade: Optional[tuple[str, float]] = None,
        worst_trade: Optional[tuple[str, float]] = None,
        open_positions: int = 0,
    ) -> str:
        """Генерирует ежедневную сводку для Telegram."""
        pnl_sign = "+" if daily_pnl >= 0 else ""
        pnl_emoji = "📈" if daily_pnl >= 0 else "📉"

        lines = [
            "📊 Добрый вечер! Вот как прошёл день:",
            "",
            f"💰 Ваш портфель: {portfolio_value:,.0f} ₽",
            f"{pnl_emoji} Сегодня {'заработали' if daily_pnl >= 0 else 'потеряли'}: {pnl_sign}{daily_pnl:,.0f} ₽",
            "",
            f"🔄 Всего сделок: {trades_count}",
            f"✅ Удачных: {wins}",
            f"❌ Неудачных: {losses}",
        ]

        if best_trade:
            lines.append(f"\n🏆 Лучшая сделка: {best_trade[0]} (+{best_trade[1]:,.0f} ₽)")
        if worst_trade:
            lines.append(f"😔 Худшая: {worst_trade[0]} ({worst_trade[1]:,.0f} ₽)")

        lines.append(f"\n📋 Открыто позиций: {open_positions}")
        lines.append(f"\n💡 Совет дня: {random.choice(DAILY_TIPS)}")

        return "\n".join(lines)

    def generate_weekly_summary(
        self,
        portfolio_value: float,
        weekly_pnl: float,
        total_trades: int,
        wins: int,
        losses: int,
        best_day_pnl: float,
        worst_day_pnl: float,
        open_positions: int = 0,
    ) -> str:
        """Генерирует еженедельную сводку."""
        pnl_sign = "+" if weekly_pnl >= 0 else ""
        pnl_emoji = "📈" if weekly_pnl >= 0 else "📉"
        pnl_pct = (weekly_pnl / (portfolio_value - weekly_pnl)) * 100 if portfolio_value != weekly_pnl else 0

        lines = [
            "📊 Итоги недели:",
            "",
            f"💰 Портфель: {portfolio_value:,.0f} ₽",
            f"{pnl_emoji} За неделю: {pnl_sign}{weekly_pnl:,.0f} ₽ ({pnl_sign}{pnl_pct:.1f}%)",
            "",
            f"🔄 Сделок за неделю: {total_trades}",
            f"✅ Удачных: {wins} | ❌ Неудачных: {losses}",
            f"📊 Процент успешных: {wins / total_trades * 100:.0f}%" if total_trades > 0 else "",
            "",
            f"🏆 Лучший день: +{best_day_pnl:,.0f} ₽",
            f"😔 Худший день: {worst_day_pnl:,.0f} ₽",
            "",
            f"📋 Открыто позиций: {open_positions}",
            "",
            f"💡 {random.choice(DAILY_TIPS)}",
        ]

        return "\n".join(lines)

    def generate_risk_alert_simple(self, alert_type: str, details: dict) -> str:
        """Переводит технические алерты в простой русский."""
        templates = {
            "drawdown": "⚠️ Внимание! Портфель снизился на {pct:.1f}% от максимума. "
                        "Система контролирует риски и следит за ситуацией.",
            "daily_loss": "⚠️ Сегодня убыток составил {amount:,.0f} ₽. "
                          "Система может приостановить торговлю для защиты капитала.",
            "emergency_stop": "🛑 Торговля остановлена! Причина: превышен лимит потерь. "
                              "Все позиции будут закрыты. Не переживайте — это защитный механизм.",
            "connection_lost": "📡 Потеряна связь с биржей. Система пытается переподключиться. "
                               "Открытые позиции защищены стоп-ордерами.",
            "large_trade": "💼 Совершена крупная сделка: {ticker} на {amount:,.0f} ₽. "
                           "Это {pct:.1f}% от портфеля.",
        }

        template = templates.get(alert_type, "ℹ️ Системное уведомление: {message}")
        try:
            return template.format(**details)
        except KeyError:
            return f"ℹ️ Уведомление: {alert_type} — {details}"
