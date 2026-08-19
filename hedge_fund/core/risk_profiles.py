"""Предустановленные профили риска с PyQt6 виджетом выбора."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

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

PROFILES: dict[str, dict[str, Any]] = {
    "conservative": {
        "name_ru": "Консервативный",
        "description_ru": "Минимальный риск. Только голубые фишки, без фьючерсов. Подходит для сохранения капитала.",
        "emoji": "🛡️",
        "params": {
            "max_drawdown_pct": 2.0,
            "max_position_pct": 5.0,
            "max_daily_loss_pct": 1.0,
            "stop_loss_pct": 0.8,
            "max_open_positions": 10,
            "allowed_instruments": ["blue_chips"],
            "allow_futures": False,
        },
    },
    "moderate": {
        "name_ru": "Умеренный",
        "description_ru": "Баланс риска и доходности. Акции и индексные фьючерсы. Для опытных инвесторов.",
        "emoji": "⚖️",
        "params": {
            "max_drawdown_pct": 5.0,
            "max_position_pct": 10.0,
            "max_daily_loss_pct": 2.0,
            "stop_loss_pct": 1.5,
            "max_open_positions": 20,
            "allowed_instruments": ["all_stocks", "index_futures"],
            "allow_futures": True,
        },
    },
    "aggressive": {
        "name_ru": "Агрессивный",
        "description_ru": "Максимальная доходность при высоком риске. Все инструменты. Для профессионалов.",
        "emoji": "🚀",
        "params": {
            "max_drawdown_pct": 10.0,
            "max_position_pct": 15.0,
            "max_daily_loss_pct": 5.0,
            "stop_loss_pct": 3.0,
            "max_open_positions": 30,
            "allowed_instruments": ["all"],
            "allow_futures": True,
        },
    },
}


def apply_profile(profile_name: str, config: dict) -> dict:
    """Применяет профиль риска к конфигурации."""
    profile = PROFILES.get(profile_name)
    if not profile:
        logger.error(f"Unknown profile: {profile_name}")
        return config

    config.setdefault("risk", {})
    config["risk"].update(profile["params"])
    config["risk"]["profile_name"] = profile_name
    logger.info(f"Applied risk profile: {profile['name_ru']}")
    return config


def get_profile_widget(parent: "QWidget") -> "QWidget":
    """Возвращает PyQt6 виджет с 3 карточками профилей для выбора."""
    from PyQt6.QtCore import Qt
    from PyQt6.QtWidgets import QButtonGroup, QFrame, QHBoxLayout, QLabel, QRadioButton, QVBoxLayout

    container = QFrame(parent)
    container.setStyleSheet(f"background: {COLORS['bg_dark']};")
    h_layout = QHBoxLayout(container)
    h_layout.setSpacing(16)

    group = QButtonGroup(container)

    for i, (key, profile) in enumerate(PROFILES.items()):
        card = QFrame()
        card.setStyleSheet(f"""
            QFrame {{
                background-color: {COLORS['bg_card']};
                border: 1px solid {COLORS['gold_dim']};
                border-radius: 8px;
                padding: 16px;
            }}
            QFrame:hover {{
                border-color: {COLORS['gold']};
            }}
        """)
        card_layout = QVBoxLayout(card)
        card_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        emoji_lbl = QLabel(profile["emoji"])
        emoji_lbl.setStyleSheet("font-size: 32px;")
        emoji_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_layout.addWidget(emoji_lbl)

        name_lbl = QLabel(profile["name_ru"])
        name_lbl.setStyleSheet(f"font-size: 14px; font-weight: bold; color: {COLORS['gold']};")
        name_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_layout.addWidget(name_lbl)

        desc_lbl = QLabel(profile["description_ru"])
        desc_lbl.setWordWrap(True)
        desc_lbl.setStyleSheet(f"font-size: 11px; color: {COLORS['ivory_dim']};")
        desc_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_layout.addWidget(desc_lbl)

        params = profile["params"]
        stats = QLabel(
            f"Просадка: {params['max_drawdown_pct']}%\n"
            f"Стоп-лосс: {params['stop_loss_pct']}%\n"
            f"Позиций: до {params['max_open_positions']}"
        )
        stats.setStyleSheet(f"font-size: 10px; color: {COLORS['ivory_dim']}; margin-top: 8px;")
        stats.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_layout.addWidget(stats)

        radio = QRadioButton("Выбрать")
        radio.setStyleSheet(f"color: {COLORS['gold']};")
        if i == 1:
            radio.setChecked(True)
        group.addButton(radio, i)
        card_layout.addWidget(radio, alignment=Qt.AlignmentFlag.AlignCenter)

        h_layout.addWidget(card)

    container._button_group = group
    return container
