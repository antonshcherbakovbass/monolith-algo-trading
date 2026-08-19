"""Пошаговый мастер первого запуска с Art Deco стилизацией."""

from __future__ import annotations

from typing import Optional

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from ..utils.logger import get_logger

logger = get_logger(__name__)

COLORS = {
    "bg_void": "#0A0A0F", "bg_dark": "#0D0D14", "bg_card": "#13131F",
    "gold": "#D4AF37", "gold_light": "#F0D060", "gold_dim": "#8B7424",
    "crimson": "#8B0000", "crimson_bright": "#DC143C",
    "ivory": "#FAEBD7", "ivory_dim": "#B8A88A",
    "obsidian": "#1A1A2E", "emerald": "#50C878", "bronze": "#CD7F32",
}

STYLESHEET = f"""
    QWidget {{
        background-color: {COLORS['bg_void']};
        color: {COLORS['ivory']};
        font-family: 'Segoe UI', sans-serif;
    }}
    QLabel {{
        background: transparent;
    }}
    QLineEdit {{
        background-color: {COLORS['bg_card']};
        border: 1px solid {COLORS['gold_dim']};
        border-radius: 4px;
        padding: 8px;
        color: {COLORS['ivory']};
        font-size: 13px;
    }}
    QLineEdit:focus {{
        border-color: {COLORS['gold']};
    }}
    QPushButton {{
        background-color: {COLORS['bg_card']};
        border: 1px solid {COLORS['gold_dim']};
        border-radius: 4px;
        padding: 10px 24px;
        color: {COLORS['gold']};
        font-size: 13px;
        font-weight: bold;
    }}
    QPushButton:hover {{
        background-color: {COLORS['obsidian']};
        border-color: {COLORS['gold']};
    }}
    QPushButton#primary {{
        background-color: {COLORS['gold_dim']};
        color: {COLORS['bg_void']};
        border: none;
    }}
    QPushButton#primary:hover {{
        background-color: {COLORS['gold']};
    }}
    QComboBox {{
        background-color: {COLORS['bg_card']};
        border: 1px solid {COLORS['gold_dim']};
        border-radius: 4px;
        padding: 8px;
        color: {COLORS['ivory']};
    }}
"""


class FirstRunWizard(QWidget):
    """Мастер первого запуска — 5 шагов настройки системы."""

    finished = pyqtSignal(dict)

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle("Первый запуск")
        self.setMinimumSize(700, 500)
        self.setStyleSheet(STYLESHEET)

        self._config: dict = {}
        self._current_step = 0
        self._total_steps = 5

        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 30, 40, 30)

        # Progress
        self._progress_layout = QHBoxLayout()
        self._progress_dots: list[QLabel] = []
        for i in range(self._total_steps):
            dot = QLabel("●")
            dot.setAlignment(Qt.AlignmentFlag.AlignCenter)
            dot.setStyleSheet(f"font-size: 14px; color: {COLORS['gold_dim']};")
            self._progress_dots.append(dot)
            self._progress_layout.addWidget(dot)
        layout.addLayout(self._progress_layout)

        # Stacked pages
        self._stack = QStackedWidget()
        self._stack.addWidget(self._create_welcome_page())
        self._stack.addWidget(self._create_risk_page())
        self._stack.addWidget(self._create_quik_page())
        self._stack.addWidget(self._create_telegram_page())
        self._stack.addWidget(self._create_finish_page())
        layout.addWidget(self._stack)

        # Navigation
        nav = QHBoxLayout()
        self._btn_back = QPushButton("← Назад")
        self._btn_back.clicked.connect(self._go_back)
        self._btn_next = QPushButton("Далее →")
        self._btn_next.setObjectName("primary")
        self._btn_next.clicked.connect(self._go_next)
        nav.addWidget(self._btn_back)
        nav.addStretch()
        nav.addWidget(self._btn_next)
        layout.addLayout(nav)

        self._update_navigation()

    def _create_welcome_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        title = QLabel("✦ Добро пожаловать! ✦")
        title.setStyleSheet(f"font-size: 24px; font-weight: bold; color: {COLORS['gold']};")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        desc = QLabel(
            "Это система автоматической торговли на Московской бирже.\n\n"
            "Она анализирует рынок, совершает сделки по заданным правилам\n"
            "и защищает ваш капитал с помощью управления рисками.\n\n"
            "Сейчас мы настроим основные параметры за несколько простых шагов."
        )
        desc.setStyleSheet(f"font-size: 14px; color: {COLORS['ivory_dim']}; line-height: 1.6;")
        desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(desc)

        return page

    def _create_risk_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)

        title = QLabel("Выберите профиль риска")
        title.setStyleSheet(f"font-size: 18px; font-weight: bold; color: {COLORS['gold']};")
        layout.addWidget(title)

        self._risk_combo = QComboBox()
        self._risk_combo.addItems([
            "🛡️ Консервативный — минимальный риск, стабильный доход",
            "⚖️ Умеренный — баланс между риском и доходностью",
            "🚀 Агрессивный — максимальная доходность, высокий риск",
        ])
        layout.addWidget(self._risk_combo)

        desc = QLabel(
            "Консервативный: только голубые фишки, макс. просадка 2%\n"
            "Умеренный: акции + фьючерсы, макс. просадка 5%\n"
            "Агрессивный: все инструменты, макс. просадка 10%"
        )
        desc.setStyleSheet(f"font-size: 12px; color: {COLORS['ivory_dim']};")
        layout.addWidget(desc)
        layout.addStretch()

        return page

    def _create_quik_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)

        title = QLabel("Подключение к QUIK")
        title.setStyleSheet(f"font-size: 18px; font-weight: bold; color: {COLORS['gold']};")
        layout.addWidget(title)

        desc = QLabel("Укажите адрес и порт терминала QUIK для подключения.")
        desc.setStyleSheet(f"color: {COLORS['ivory_dim']};")
        layout.addWidget(desc)

        layout.addWidget(QLabel("IP-адрес:"))
        self._quik_ip = QLineEdit("127.0.0.1")
        layout.addWidget(self._quik_ip)

        layout.addWidget(QLabel("Порт:"))
        self._quik_port = QLineEdit("34130")
        layout.addWidget(self._quik_port)

        layout.addStretch()
        return page

    def _create_telegram_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)

        title = QLabel("Telegram уведомления")
        title.setStyleSheet(f"font-size: 18px; font-weight: bold; color: {COLORS['gold']};")
        layout.addWidget(title)

        desc = QLabel(
            "1. Откройте @BotFather в Telegram\n"
            "2. Отправьте /newbot и следуйте инструкциям\n"
            "3. Скопируйте токен бота сюда"
        )
        desc.setStyleSheet(f"color: {COLORS['ivory_dim']}; font-size: 12px;")
        layout.addWidget(desc)

        layout.addWidget(QLabel("Токен бота:"))
        self._tg_token = QLineEdit()
        self._tg_token.setPlaceholderText("123456:ABC-DEF...")
        layout.addWidget(self._tg_token)

        layout.addWidget(QLabel("Chat ID:"))
        self._tg_chat_id = QLineEdit()
        self._tg_chat_id.setPlaceholderText("Ваш числовой ID")
        layout.addWidget(self._tg_chat_id)

        sep = QLabel("— Куратор (необязательно) —")
        sep.setStyleSheet(f"color: {COLORS['gold_dim']}; margin-top: 10px;")
        layout.addWidget(sep)

        layout.addWidget(QLabel("Токен бота куратора:"))
        self._curator_token = QLineEdit()
        layout.addWidget(self._curator_token)

        layout.addWidget(QLabel("Chat ID куратора:"))
        self._curator_chat_id = QLineEdit()
        layout.addWidget(self._curator_chat_id)

        layout.addStretch()
        return page

    def _create_finish_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        title = QLabel("✦ Готово! ✦")
        title.setStyleSheet(f"font-size: 24px; font-weight: bold; color: {COLORS['gold']};")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        self._summary_label = QLabel("")
        self._summary_label.setStyleSheet(f"font-size: 13px; color: {COLORS['ivory_dim']};")
        self._summary_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._summary_label)

        note = QLabel("Система запустится в бумажном (тестовом) режиме.\nРеальная торговля включается отдельно.")
        note.setStyleSheet(f"font-size: 12px; color: {COLORS['emerald']};")
        note.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(note)

        return page

    def _update_navigation(self) -> None:
        self._btn_back.setVisible(self._current_step > 0)
        is_last = self._current_step == self._total_steps - 1
        self._btn_next.setText("Готово ✓" if is_last else "Далее →")

        for i, dot in enumerate(self._progress_dots):
            if i == self._current_step:
                dot.setStyleSheet(f"font-size: 14px; color: {COLORS['gold']};")
            elif i < self._current_step:
                dot.setStyleSheet(f"font-size: 14px; color: {COLORS['emerald']};")
            else:
                dot.setStyleSheet(f"font-size: 14px; color: {COLORS['gold_dim']};")

    def _go_back(self) -> None:
        if self._current_step > 0:
            self._current_step -= 1
            self._stack.setCurrentIndex(self._current_step)
            self._update_navigation()

    def _go_next(self) -> None:
        if self._current_step == self._total_steps - 1:
            self._collect_config()
            self.finished.emit(self._config)
            self.close()
            return

        self._current_step += 1
        if self._current_step == self._total_steps - 1:
            self._collect_config()
            self._summary_label.setText(
                f"Профиль: {self._config.get('risk_profile', '?')}\n"
                f"QUIK: {self._config.get('quik_ip', '?')}:{self._config.get('quik_port', '?')}\n"
                f"Telegram: {'настроен' if self._config.get('telegram_token') else 'не настроен'}\n"
                f"Режим: Бумажная торговля"
            )
        self._stack.setCurrentIndex(self._current_step)
        self._update_navigation()

    def _collect_config(self) -> None:
        profiles = ["conservative", "moderate", "aggressive"]
        self._config = {
            "risk_profile": profiles[self._risk_combo.currentIndex()],
            "quik_ip": self._quik_ip.text(),
            "quik_port": self._quik_port.text(),
            "telegram_token": self._tg_token.text(),
            "telegram_chat_id": self._tg_chat_id.text(),
            "curator_token": self._curator_token.text(),
            "curator_chat_id": self._curator_chat_id.text(),
            "trading_mode": "paper",
        }

    def get_config(self) -> dict:
        """Возвращает собранную конфигурацию."""
        return self._config
