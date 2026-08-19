"""Индикатор здоровья портфеля с PyQt6 виджетом."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..utils.logger import get_logger

if TYPE_CHECKING:
    from PyQt6.QtWidgets import QWidget

logger = get_logger(__name__)

COLORS = {
    "bg_void": "#0A0A0F", "bg_dark": "#0D0D14", "bg_card": "#13131F",
    "gold": "#D4AF37", "gold_light": "#F0D060", "gold_dim": "#8B7424",
    "crimson": "#8B0000", "crimson_bright": "#DC143C",
    "ivory": "#FAEBD7", "ivory_dim": "#B8A88A",
    "obsidian": "#1A1A2E", "emerald": "#50C878", "bronze": "#CD7F32",
}


class PortfolioHealth:
    """Оценивает здоровье портфеля и предоставляет виджет для дашборда."""

    def calculate_health(
        self,
        daily_pnl_pct: float,
        drawdown_pct: float,
        diversification_score: float,
        win_rate: float,
        risk_utilization_pct: float,
    ) -> tuple[str, str, str]:
        """
        Рассчитывает здоровье портфеля.

        Returns:
            (color, emoji, explanation_ru)
        """
        if drawdown_pct >= 4 or risk_utilization_pct >= 80 or daily_pnl_pct < -1.5:
            reasons = []
            if drawdown_pct >= 4:
                reasons.append(f"просадка {drawdown_pct:.1f}%")
            if risk_utilization_pct >= 80:
                reasons.append(f"загрузка риска {risk_utilization_pct:.0f}%")
            if daily_pnl_pct < -1.5:
                reasons.append(f"дневной убыток {daily_pnl_pct:.1f}%")
            return ("red", "🔴", f"Высокий риск: {', '.join(reasons)}")

        if drawdown_pct < 2 and risk_utilization_pct < 60 and win_rate > 50:
            return ("green", "🟢", "Всё отлично! Портфель в хорошей форме.")

        reasons = []
        if drawdown_pct >= 2:
            reasons.append(f"просадка {drawdown_pct:.1f}%")
        if risk_utilization_pct >= 60:
            reasons.append(f"загрузка риска {risk_utilization_pct:.0f}%")
        if win_rate <= 50:
            reasons.append(f"процент побед {win_rate:.0f}%")
        return ("yellow", "🟡", f"Внимание: {', '.join(reasons)}" if reasons else "Умеренный риск")

    def get_dashboard_widget(self, parent: "QWidget") -> "QWidget":
        """Возвращает PyQt6 виджет с индикатором здоровья портфеля."""
        from PyQt6.QtCore import Qt
        from PyQt6.QtWidgets import QFrame, QLabel, QVBoxLayout

        frame = QFrame(parent)
        frame.setStyleSheet(f"""
            QFrame {{
                background-color: {COLORS['bg_card']};
                border: 1px solid {COLORS['gold_dim']};
                border-radius: 8px;
                padding: 16px;
            }}
        """)

        layout = QVBoxLayout(frame)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        title = QLabel("ЗДОРОВЬЕ ПОРТФЕЛЯ")
        title.setStyleSheet(f"""
            font-size: 11px;
            font-weight: bold;
            color: {COLORS['gold']};
            letter-spacing: 2px;
        """)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        self._indicator_label = QLabel("🟢")
        self._indicator_label.setStyleSheet("font-size: 48px;")
        self._indicator_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._indicator_label)

        self._explanation_label = QLabel("Загрузка...")
        self._explanation_label.setStyleSheet(f"""
            font-size: 12px;
            color: {COLORS['ivory_dim']};
        """)
        self._explanation_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._explanation_label.setWordWrap(True)
        layout.addWidget(self._explanation_label)

        return frame

    def update_widget(self, color: str, emoji: str, explanation: str) -> None:
        """Обновляет виджет новыми данными."""
        if hasattr(self, "_indicator_label"):
            self._indicator_label.setText(emoji)
            self._explanation_label.setText(explanation)
