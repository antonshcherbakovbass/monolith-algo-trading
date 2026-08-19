"""
Setup GUI — PyQt6 configuration window in "Dark Alchemy x Art Deco" style.

Shown on first launch or when running ``python -m hedge_fund.setup_gui``.
All settings are persisted to config/settings.yaml.
"""

from __future__ import annotations

import json
import sys
import urllib.request
from pathlib import Path
from typing import Any

import yaml
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QRect
from PyQt6.QtGui import (
    QColor, QFont, QLinearGradient, QPainter, QPen, QBrush, QPalette, QPixmap,
)
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QTabWidget, QLabel,
    QLineEdit, QTextEdit, QPushButton, QRadioButton, QCheckBox,
    QScrollArea, QFrame, QButtonGroup, QMessageBox, QSizePolicy,
)

from hedge_fund.core.i18n import I18n, t
from hedge_fund.core.themes import ThemeManager
from hedge_fund.core.styled_widgets import (
    DualismSplitBackground, ArtDecoFrameHeader, LightSideButton, DarkSideButton,
    MysticScrollContent, GlowLabel,
)

CONFIG_PATH = Path(__file__).parent / "config" / "settings.yaml"


def _get_colors() -> dict[str, str]:
    base = ThemeManager._themes.get("dark_alchemy")
    base_colors = base.colors if base else {}
    return {**base_colors, **ThemeManager.get_theme().colors}


C = _get_colors()

def _generate_stylesheet() -> str:
    c = _get_colors()
    theme_id = ThemeManager._current_theme

    if theme_id == "divine_dualism":
        return """
QWidget {
    background-color: transparent;
    color: #2A2420;
    font-family: "Cinzel", "Cormorant Garamond", "Georgia", "Segoe UI";
    font-size: 10pt;
}
QTabBar::tab {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #FDFBF7, stop:0.15 #F5F0E6, stop:0.85 #E8E0D0, stop:1 #D8D0C0);
    color: #5A4A28;
    border: 1px solid #C0B490;
    border-top: 2px solid #E6C687;
    border-bottom: none;
    padding: 8px 16px;
    font-family: "Cinzel", "Georgia", "Segoe UI";
    font-size: 9pt;
    letter-spacing: 2px;
    min-width: 55px;
}
QTabBar::tab:selected {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #FFE44D, stop:0.08 #FFD700, stop:0.45 #D4AF37, stop:0.55 #B8960C, stop:0.92 #8B7424, stop:1 #6B5510);
    color: #0A0A0A;
    border: 1px solid #FFE44D;
    border-top: 2px solid #FFFACD;
    border-bottom: none;
    font-weight: bold;
}
QTabBar::tab:hover:!selected {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #FFFDF9, stop:0.5 #F5F0E6, stop:1 #EDE6D6);
    border: 1px solid #D4AF37;
    border-top: 2px solid #E6C687;
    color: #8B7424;
}
QTabWidget::pane {
    border: 2px solid rgba(212,175,55,60);
    border-top: 3px solid rgba(230,198,135,120);
    background: transparent;
}
QFrame {
    background: rgba(253,251,247,180);
    border: 1px solid rgba(192,180,144,100);
    border-top: 2px solid rgba(230,198,135,80);
    border-bottom: 2px solid rgba(0,0,0,40);
    border-radius: 6px;
}
QLabel {
    border: none;
    background: transparent;
    color: #2A2420;
    font-size: 10pt;
}
QLineEdit, QTextEdit {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #FFFDF9, stop:0.1 #FDFBF7, stop:0.9 #F5F0E6, stop:1 #EDE6D6);
    color: #1A1610;
    border: 2px solid #E6C687;
    border-top: 2px solid rgba(0,0,0,30);
    border-bottom: 2px solid rgba(230,198,135,60);
    border-radius: 5px;
    padding: 6px 10px;
    font-family: "Consolas", "Cascadia Mono";
    font-size: 10pt;
    selection-background-color: #D4AF37;
    selection-color: #FFFFFF;
}
QLineEdit:focus, QTextEdit:focus {
    border: 2px solid #D4AF37;
    background: #FFFFFF;
}
QPushButton {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #F5F0E6, stop:0.06 #EDE6D6, stop:0.5 #E0D8C6,
        stop:0.94 #D0C8B6, stop:1 #C0B8A6);
    color: #5A4A28;
    border: 1px solid #C0B490;
    border-top: 2px solid #E6C687;
    border-bottom: 2px solid rgba(0,0,0,60);
    padding: 8px 18px;
    font-family: "Cinzel", "Georgia", "Segoe UI";
    letter-spacing: 1px;
    font-size: 9pt;
    border-radius: 5px;
    font-weight: bold;
}
QPushButton:hover {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #FFE44D, stop:0.06 #FFD700, stop:0.45 #D4AF37,
        stop:0.55 #B8960C, stop:0.94 #8B7424, stop:1 #6B5510);
    color: #0A0A0A;
    border: 1px solid #FFE44D;
    border-top: 2px solid #FFFACD;
    border-bottom: 2px solid #6B5510;
    font-weight: bold;
}
QPushButton:pressed {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #6B5510, stop:0.1 #8B7424, stop:0.9 #D4AF37, stop:1 #FFD700);
    border-top: 3px solid rgba(0,0,0,100);
    border-bottom: 1px solid #FFD700;
}
QPushButton#stop_btn {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #3A0808, stop:0.5 #220404, stop:1 #140000);
    color: #FF8888;
    border: 1px solid #5A000A;
    border-top: 2px solid #7A1010;
    border-bottom: 2px solid rgba(0,0,0,200);
}
QPushButton#stop_btn:hover {
    background: #5A000A; color: #FFCCCC; border-color: #8B0000;
}
QTableWidget {
    background-color: rgba(253,251,247,200);
    alternate-background-color: rgba(237,230,214,200);
    border: 1px solid #C0B490;
    border-top: 2px solid #E6C687;
    gridline-color: rgba(192,180,144,40);
    font-family: "Consolas";
    color: #2A2420;
}
QHeaderView::section {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #FFE44D, stop:0.06 #FFD700, stop:0.4 #D4AF37,
        stop:0.6 #B8960C, stop:0.94 #8B7424, stop:1 #6B5510);
    color: #0A0A0A;
    font-weight: bold;
    font-family: "Cinzel", "Georgia";
    border: none;
    border-bottom: 2px solid #FFE44D;
    padding: 7px 12px;
    letter-spacing: 1.5px;
}
QScrollBar:vertical {
    background: rgba(245,240,230,150);
    width: 10px;
    border: 1px solid rgba(192,180,144,60);
    border-radius: 5px;
    margin: 2px;
}
QScrollBar::handle:vertical {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #C0B490, stop:0.15 #D4AF37, stop:0.5 #E6C687,
        stop:0.85 #D4AF37, stop:1 #C0B490);
    min-height: 40px;
    border-radius: 5px;
    border: 1px solid #C0B490;
}
QScrollBar::handle:vertical:hover {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #D4AF37, stop:0.15 #E6C687, stop:0.5 #FFD700,
        stop:0.85 #E6C687, stop:1 #D4AF37);
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: none; }
QScrollArea { border: none; background: transparent; }
QCheckBox { spacing: 8px; color: #2A2420; font-size: 10pt; }
QCheckBox::indicator {
    width: 18px; height: 18px;
    border: 2px solid #C0B490;
    border-top: 2px solid rgba(0,0,0,30);
    border-radius: 4px;
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #FFFDF9, stop:0.5 #F5F0E6, stop:1 #FFFDF9);
}
QCheckBox::indicator:hover { border-color: #D4AF37; }
QCheckBox::indicator:checked {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #FFD700, stop:0.5 #D4AF37, stop:1 #B8960C);
    border-color: #FFD700;
    image: none;
}
QRadioButton { spacing: 8px; color: #2A2420; font-size: 10pt; }
QRadioButton::indicator {
    width: 18px; height: 18px;
    border: 2px solid #C0B490;
    border-radius: 9px;
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #FFFDF9, stop:0.5 #F5F0E6, stop:1 #FFFDF9);
}
QRadioButton::indicator:hover { border-color: #D4AF37; }
QRadioButton::indicator:checked {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #FFD700, stop:0.5 #D4AF37, stop:1 #B8960C);
    border-color: #FFD700;
}
QComboBox {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #F5F0E6, stop:0.5 #EDE6D6, stop:1 #E0D8C6);
    color: #5A4A28;
    border: 1px solid #C0B490;
    border-top: 2px solid #E6C687;
    border-bottom: 2px solid rgba(0,0,0,40);
    padding: 5px 10px;
    border-radius: 5px;
}
QComboBox:hover { border-color: #D4AF37; }
QComboBox QAbstractItemView {
    background: #FDFBF7;
    color: #2A2420;
    border: 1px solid #C0B490;
    selection-background-color: #D4AF37;
    selection-color: #FFFFFF;
}
QSpinBox {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #FFFDF9, stop:0.5 #F5F0E6, stop:1 #FFFDF9);
    color: #5A4A28;
    border: 1px solid #C0B490;
    border-top: 2px solid rgba(0,0,0,30);
    padding: 4px 8px;
    border-radius: 5px;
}
QSlider::groove:horizontal {
    border: 1px solid #C0B490;
    height: 6px;
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #EDE6D6, stop:1 #F5F0E6);
    border-radius: 3px;
}
QSlider::handle:horizontal {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #FFD700, stop:0.5 #D4AF37, stop:1 #8B7424);
    border: 1px solid #C0B490;
    width: 16px; height: 16px;
    margin: -6px 0;
    border-radius: 8px;
}
"""

    if theme_id == "ny_art_deco":
        return """
QWidget {
    background-color: transparent;
    color: #1A1A2C;
    font-family: "Lato", "Cormorant Garamond", "Segoe UI";
    font-size: 10pt;
}
QTabBar::tab {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #FAF5EB, stop:0.5 #F0E8D8, stop:1 #E0D8C6);
    color: #4A3A20;
    border: 1px solid #B8A070;
    border-top: 2px solid #C9A84C;
    border-bottom: none;
    padding: 8px 16px;
    font-family: "Lato", "Segoe UI";
    font-size: 9pt;
    letter-spacing: 3px;
    min-width: 55px;
}
QTabBar::tab:selected {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #E8C859, stop:0.3 #C9A84C, stop:0.7 #8B7532, stop:1 #6B5510);
    color: #FFFFF0;
    border: 1px solid #E8C859;
    border-top: 2px solid #FFFACD;
    font-weight: bold;
}
QTabBar::tab:hover:!selected {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #FFFFF0, stop:0.5 #FAF5EB, stop:1 #F0E8D8);
    border-top: 2px solid #C9A84C;
    color: #8B7532;
}
QTabWidget::pane {
    border: 2px solid rgba(201,168,76,50);
    border-top: 3px solid rgba(201,168,76,100);
    background: transparent;
}
QFrame {
    background: rgba(250,245,235,180);
    border: 1px solid rgba(184,160,112,80);
    border-radius: 4px;
}
QLabel {
    border: none;
    background: transparent;
    color: #1A1A2C;
    font-size: 10pt;
}
QLineEdit, QTextEdit {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #FFFFF0, stop:0.5 #FAF5EB, stop:1 #F0E8D8);
    color: #1A1A2C;
    border: 2px solid #C9A84C;
    border-radius: 4px;
    padding: 6px 10px;
    font-family: "Consolas", "Cascadia Mono";
    font-size: 10pt;
    selection-background-color: #C9A84C;
    selection-color: #FFFFFF;
}
QLineEdit:focus, QTextEdit:focus {
    border: 2px solid #E8C859;
    background: #FFFFF0;
}
QPushButton {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #F0E8D8, stop:0.5 #E0D8C6, stop:1 #D0C8B6);
    color: #4A3A20;
    border: 1px solid #B8A070;
    border-top: 2px solid #C9A84C;
    border-bottom: 2px solid rgba(0,0,0,50);
    padding: 8px 18px;
    font-family: "Lato", "Segoe UI";
    letter-spacing: 2px;
    font-size: 9pt;
    border-radius: 4px;
    font-weight: bold;
}
QPushButton:hover {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #E8C859, stop:0.3 #C9A84C, stop:0.7 #8B7532, stop:1 #6B5510);
    color: #FFFFF0;
    border: 1px solid #E8C859;
}
QPushButton:pressed {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #6B5510, stop:0.5 #8B7532, stop:1 #C9A84C);
}
QTableWidget {
    background-color: rgba(250,245,235,200);
    alternate-background-color: rgba(240,232,216,200);
    border: 1px solid #B8A070;
    border-top: 2px solid #C9A84C;
    gridline-color: rgba(184,160,112,30);
    font-family: "Consolas";
    color: #1A1A2C;
}
QHeaderView::section {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #E8C859, stop:0.4 #C9A84C, stop:0.6 #8B7532, stop:1 #6B5510);
    color: #FFFFF0;
    font-weight: bold;
    font-family: "Lato", "Segoe UI";
    border: none;
    border-bottom: 2px solid #E8C859;
    padding: 7px 12px;
    letter-spacing: 2px;
}
QScrollBar:vertical {
    background: rgba(240,232,216,150);
    width: 10px;
    border-radius: 5px;
    margin: 2px;
}
QScrollBar::handle:vertical {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #B8A070, stop:0.5 #C9A84C, stop:1 #B8A070);
    min-height: 40px;
    border-radius: 5px;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: none; }
QScrollArea { border: none; background: transparent; }
QCheckBox { spacing: 8px; color: #1A1A2C; font-size: 10pt; }
QCheckBox::indicator {
    width: 18px; height: 18px;
    border: 2px solid #B8A070;
    border-radius: 4px;
    background: #FAF5EB;
}
QCheckBox::indicator:hover { border-color: #C9A84C; }
QCheckBox::indicator:checked {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #E8C859, stop:0.5 #C9A84C, stop:1 #8B7532);
    border-color: #E8C859;
}
QRadioButton { spacing: 8px; color: #1A1A2C; font-size: 10pt; }
QRadioButton::indicator {
    width: 18px; height: 18px;
    border: 2px solid #B8A070;
    border-radius: 9px;
    background: #FAF5EB;
}
QRadioButton::indicator:hover { border-color: #C9A84C; }
QRadioButton::indicator:checked {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #E8C859, stop:0.5 #C9A84C, stop:1 #8B7532);
    border-color: #E8C859;
}
QComboBox {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #FAF5EB, stop:0.5 #F0E8D8, stop:1 #E0D8C6);
    color: #4A3A20;
    border: 1px solid #B8A070;
    border-top: 2px solid #C9A84C;
    padding: 6px 10px;
    border-radius: 4px;
}
QComboBox:hover { border-color: #C9A84C; }
QComboBox QAbstractItemView {
    background: #FAF5EB;
    color: #1A1A2C;
    border: 1px solid #B8A070;
    selection-background-color: #C9A84C;
    selection-color: #FFFFFF;
}
QSpinBox {
    background: #FAF5EB;
    color: #4A3A20;
    border: 1px solid #B8A070;
    border-top: 2px solid rgba(0,0,0,20);
    padding: 4px 8px;
    border-radius: 4px;
}
QSlider::groove:horizontal {
    border: 1px solid #B8A070;
    height: 6px;
    background: #F0E8D8;
    border-radius: 3px;
}
QSlider::handle:horizontal {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #E8C859, stop:0.5 #C9A84C, stop:1 #8B7532);
    border: 1px solid #B8A070;
    width: 16px; height: 16px;
    margin: -6px 0;
    border-radius: 8px;
}
"""

    return f"""
QWidget {{
    background-color: {c['bg_void']};
    color: {c['ivory']};
    font-family: 'Segoe UI', 'Consolas';
    font-size: 10pt;
}}
QTabWidget::pane {{
    border: 1px solid {c['gold_dim']};
    background: {c['bg_dark']};
    border-radius: 4px;
}}
QTabBar::tab {{
    background: {c['obsidian']};
    color: {c['ivory_dim']};
    padding: 8px 18px;
    border: 1px solid {c['gold_dim']};
    border-bottom: none;
    font-weight: bold;
    font-size: 9pt;
}}
QTabBar::tab:selected {{
    background: {c['bg_dark']};
    color: {c['gold']};
    border-bottom: 2px solid {c['gold']};
}}
QTabBar::tab:hover {{
    color: {c['gold_light']};
}}
QLineEdit {{
    background: {c['bg_card']};
    color: {c['ivory']};
    border: 1px solid {c['gold_dim']};
    border-radius: 3px;
    padding: 5px 8px;
    font-family: Consolas;
    font-size: 10pt;
}}
QLineEdit:focus {{
    border: 1px solid {c['gold']};
}}
QTextEdit {{
    background: {c['bg_card']};
    color: {c['ivory']};
    border: 1px solid {c['gold_dim']};
    border-radius: 3px;
    padding: 4px;
    font-family: Consolas;
    font-size: 10pt;
}}
QTextEdit:focus {{
    border: 1px solid {c['gold']};
}}
QScrollArea {{
    border: none;
    background: transparent;
}}
QCheckBox {{
    spacing: 8px;
    color: {c['ivory']};
}}
QCheckBox::indicator {{
    width: 16px; height: 16px;
    border: 1px solid {c['gold_dim']};
    border-radius: 3px;
    background: {c['bg_card']};
}}
QCheckBox::indicator:checked {{
    background: {c['gold']};
    border-color: {c['gold']};
}}
QRadioButton {{
    spacing: 8px;
    color: {c['ivory']};
}}
QRadioButton::indicator {{
    width: 14px; height: 14px;
    border: 1px solid {c['gold_dim']};
    border-radius: 7px;
    background: {c['bg_card']};
}}
QRadioButton::indicator:checked {{
    background: {c['gold']};
    border-color: {c['gold']};
}}
QScrollBar:vertical {{
    background: {c['bg_dark']};
    width: 10px;
    border: none;
}}
QScrollBar::handle:vertical {{
    background: {c['gold_dim']};
    min-height: 30px;
    border-radius: 4px;
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}
"""


STYLESHEET = _generate_stylesheet()


def _load_config() -> dict[str, Any]:
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    return {}


def _save_config(cfg: dict[str, Any]) -> None:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        yaml.dump(cfg, f, default_flow_style=False, allow_unicode=True, sort_keys=False)


def _get(cfg: dict, *keys: str, default: Any = "") -> Any:
    obj: Any = cfg
    for k in keys:
        if isinstance(obj, dict):
            obj = obj.get(k, None)
        else:
            return default
        if obj is None:
            return default
    return obj


# ── Worker threads ────────────────────────────────────────────

class _TestTelegramThread(QThread):
    result = pyqtSignal(str)

    def __init__(self, token: str, chat_id: str) -> None:
        super().__init__()
        self.token = token
        self.chat_id = chat_id

    def run(self) -> None:
        try:
            url = f"https://api.telegram.org/bot{self.token}/sendMessage"
            data = json.dumps({"chat_id": self.chat_id, "text": "⟐ LUX NOX Capital · MONOLITH: тестовое сообщение ⟐"}).encode()
            req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                if resp.status == 200:
                    self.result.emit("✓ Telegram подключён! Проверьте бота.")
                else:
                    self.result.emit(f"✗ Ошибка: HTTP {resp.status}")
        except Exception as e:
            self.result.emit(f"✗ Ошибка: {e}")


class _TestOllamaThread(QThread):
    result = pyqtSignal(str)

    def __init__(self, base_url: str) -> None:
        super().__init__()
        self.base_url = base_url

    def run(self) -> None:
        try:
            with urllib.request.urlopen(f"{self.base_url}/api/tags", timeout=5) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read())
                    models = [m.get("name", "?") for m in data.get("models", [])]
                    self.result.emit(f"✓ Ollama OK! Модели: {', '.join(models[:5])}")
                else:
                    self.result.emit(f"✗ Ошибка: HTTP {resp.status}")
        except Exception as e:
            self.result.emit(f"✗ Не доступен: {e}")


# ── Decorative widgets ────────────────────────────────────────

class _GoldLine(QWidget):
    """Thin horizontal gold gradient line."""

    def __init__(self, height: int = 2, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedHeight(height)

    def paintEvent(self, _: Any) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        grad = QLinearGradient(0, 0, self.width(), 0)
        grad.setColorAt(0.0, QColor(C["bg_void"]))
        grad.setColorAt(0.3, QColor(C["gold"]))
        grad.setColorAt(0.7, QColor(C["gold"]))
        grad.setColorAt(1.0, QColor(C["bg_void"]))
        p.fillRect(self.rect(), grad)
        p.end()


class _HeaderWidget(QWidget):
    """Art-Deco styled header with LUX ☉ NOX branding."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedHeight(110)
        self._build_layout()

    def _build_layout(self) -> None:
        main_lay = QVBoxLayout(self)
        main_lay.setContentsMargins(0, 8, 0, 4)
        main_lay.setSpacing(2)

        title_row = QHBoxLayout()
        title_row.setSpacing(8)
        title_row.addStretch()

        c = _get_colors()

        self._lux_label = QLabel("LUX")
        self._lux_label.setStyleSheet(
            f"color: {c['gold']}; font-size: 20pt; font-weight: bold; "
            f"letter-spacing: 6px; background: transparent;")
        title_row.addWidget(self._lux_label)

        logo_path = Path(__file__).parent / "assets" / "logo_sun.png"
        if logo_path.exists():
            logo_pixmap = QPixmap(str(logo_path)).scaled(
                36, 36, Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation)
            self._logo_label = QLabel()
            self._logo_label.setPixmap(logo_pixmap)
            self._logo_label.setStyleSheet("background: transparent;")
            title_row.addWidget(self._logo_label)
        else:
            self._logo_label = QLabel("☉")
            self._logo_label.setStyleSheet(
                f"color: {c['gold']}; font-size: 22pt; background: transparent;")
            title_row.addWidget(self._logo_label)

        self._nox_label = QLabel("NOX")
        self._nox_label.setStyleSheet(
            f"color: {c['gold']}; font-size: 20pt; font-weight: bold; "
            f"letter-spacing: 6px; background: transparent;")
        title_row.addWidget(self._nox_label)
        title_row.addStretch()

        main_lay.addLayout(title_row)

        self._capital_label = QLabel("CAPITAL")
        self._capital_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._capital_label.setStyleSheet(
            f"color: {c['gold_dim']}; font-size: 11pt; "
            f"letter-spacing: 10px; background: transparent;")
        main_lay.addWidget(self._capital_label)

        self._subtitle_label = QLabel(t("window.subtitle"))
        self._subtitle_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._subtitle_label.setStyleSheet(
            f"color: {c['ivory_dim']}; font-size: 9pt; background: transparent;")
        main_lay.addWidget(self._subtitle_label)

    def refresh_text(self) -> None:
        c = _get_colors()
        self._lux_label.setStyleSheet(
            f"color: {c['gold']}; font-size: 20pt; font-weight: bold; "
            f"letter-spacing: 6px; background: transparent;")
        self._nox_label.setStyleSheet(
            f"color: {c['gold']}; font-size: 20pt; font-weight: bold; "
            f"letter-spacing: 6px; background: transparent;")
        self._capital_label.setStyleSheet(
            f"color: {c['gold_dim']}; font-size: 11pt; "
            f"letter-spacing: 10px; background: transparent;")
        self._subtitle_label.setText(t("window.subtitle"))
        self._subtitle_label.setStyleSheet(
            f"color: {c['ivory_dim']}; font-size: 9pt; background: transparent;")


# ── Main Window ───────────────────────────────────────────────

class SetupWindow(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.config = _load_config()
        self.result: str | None = None
        self.fields: dict[str, QLineEdit] = {}
        self.text_fields: dict[str, QTextEdit] = {}
        self.agent_checks: dict[str, QCheckBox] = {}
        self.instrument_checks: dict[str, QCheckBox] = {}
        self._threads: list[QThread] = []
        self._bg_widget: QWidget | None = None

        self.setWindowTitle("◇ LUX NOX CAPITAL ◇ MONOLITH TERMINAL ◇")
        self.resize(900, 700)
        self._center()
        self.setStyleSheet(STYLESHEET)
        self._build_ui()
        self._apply_bg_widget()

    def _center(self) -> None:
        screen = QApplication.primaryScreen()
        if screen:
            geo = screen.availableGeometry()
            x = (geo.width() - 900) // 2 + geo.x()
            y = (geo.height() - 700) // 2 + geo.y()
            self.move(x, y)

    def _apply_bg_widget(self) -> None:
        """Insert or replace a textured background widget for dualism themes."""
        if self._bg_widget is not None:
            self._bg_widget.setParent(None)
            self._bg_widget.deleteLater()
            self._bg_widget = None

        theme_id = ThemeManager._current_theme
        if theme_id in ("divine_dualism", "ny_art_deco"):
            self._bg_widget = DualismSplitBackground(self)
        else:
            return

        self._bg_widget.setGeometry(0, 0, self.width(), self.height())
        self._bg_widget.lower()
        self._bg_widget.show()

    def resizeEvent(self, event: Any) -> None:
        super().resizeEvent(event)
        if self._bg_widget is not None:
            self._bg_widget.setGeometry(0, 0, self.width(), self.height())

    def _g(self, *keys: str, default: Any = "") -> Any:
        return _get(self.config, *keys, default=default)

    # ── UI building ───────────────────────────────────────────

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        root.addWidget(_GoldLine(2))
        self.header_widget = _HeaderWidget()
        root.addWidget(self.header_widget)
        root.addWidget(_GoldLine(1))

        lang_row = QHBoxLayout()
        lang_row.addStretch()
        self.btn_ru = QPushButton("RUS")
        self.btn_ru.setFixedSize(60, 28)
        self.btn_ru.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_ru.clicked.connect(lambda: self._switch_lang("ru"))
        self.btn_en = QPushButton("ENG")
        self.btn_en.setFixedSize(60, 28)
        self.btn_en.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_en.clicked.connect(lambda: self._switch_lang("en"))
        lang_row.addWidget(self.btn_ru)
        lang_row.addWidget(self.btn_en)

        lang_row.addSpacing(20)
        theme_label = QLabel("Тема / Theme:")
        theme_label.setStyleSheet(f"color: {C['ivory_dim']}; font-size: 8pt;")
        lang_row.addWidget(theme_label)

        _theme_btn_h = 26
        self.btn_theme_dark = QPushButton("  🌑 Dark Alchemy  ")
        self.btn_theme_dark.setFixedHeight(_theme_btn_h)
        self.btn_theme_dark.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        self.btn_theme_dark.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_theme_dark.clicked.connect(lambda: self._switch_theme("dark_alchemy"))

        self.btn_theme_blind = QPushButton("  👁 Clear Vision  ")
        self.btn_theme_blind.setFixedHeight(_theme_btn_h)
        self.btn_theme_blind.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        self.btn_theme_blind.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_theme_blind.clicked.connect(lambda: self._switch_theme("colorblind"))

        self.btn_theme_divine = QPushButton("  ✧ Divine Dualism  ")
        self.btn_theme_divine.setFixedHeight(_theme_btn_h)
        self.btn_theme_divine.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        self.btn_theme_divine.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_theme_divine.clicked.connect(lambda: self._switch_theme("divine_dualism"))

        self.btn_theme_ny = QPushButton("  🏙 NY Art Deco  ")
        self.btn_theme_ny.setFixedHeight(_theme_btn_h)
        self.btn_theme_ny.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        self.btn_theme_ny.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_theme_ny.clicked.connect(lambda: self._switch_theme("ny_art_deco"))

        lang_row.addWidget(self.btn_theme_dark)
        lang_row.addWidget(self.btn_theme_blind)
        lang_row.addWidget(self.btn_theme_divine)
        lang_row.addWidget(self.btn_theme_ny)

        lang_row.setContentsMargins(0, 2, 16, 2)
        root.addLayout(lang_row)
        self._update_lang_buttons()
        self._update_theme_buttons()

        self.tabs = QTabWidget()
        root.addWidget(self.tabs, 1)
        self._rebuild_tabs()

        root.addWidget(_GoldLine(1))
        root.addLayout(self._button_bar())
        root.addWidget(_GoldLine(2))

    def _switch_lang(self, lang: str) -> None:
        I18n.set_lang(lang)
        self._update_lang_buttons()
        self._rebuild_tabs()
        self.header_widget.refresh_text()

    def _update_lang_buttons(self) -> None:
        c = _get_colors()
        active = (
            f"QPushButton {{ background: {c['gold']}; color: {c['bg_void']}; "
            f"border: 1px solid {c['gold']}; border-radius: 3px; font-weight: bold; font-size: 10px; }}"
        )
        inactive = (
            f"QPushButton {{ background: {c['bg_card']}; color: {c['gold_dim']}; "
            f"border: 1px solid {c['gold_dim']}; border-radius: 3px; font-size: 10px; }}"
            f"QPushButton:hover {{ color: {c['gold']}; border-color: {c['gold']}; }}"
        )
        is_ru = I18n.get_lang() == "ru"
        self.btn_ru.setStyleSheet(active if is_ru else inactive)
        self.btn_en.setStyleSheet(inactive if is_ru else active)

    def _switch_theme(self, theme_id: str) -> None:
        ThemeManager.set_theme(theme_id)
        ThemeManager.save_preference()
        self._apply_theme()

    def _apply_theme(self) -> None:
        global C
        C = _get_colors()
        self.setStyleSheet(_generate_stylesheet())
        self._update_lang_buttons()
        self._update_theme_buttons()
        self._rebuild_tabs()
        self.header_widget.refresh_text()
        self._apply_bg_widget()

    def _update_theme_buttons(self) -> None:
        c = _get_colors()
        current = ThemeManager._current_theme
        for btn, tid in [
            (self.btn_theme_dark, "dark_alchemy"),
            (self.btn_theme_blind, "colorblind"),
            (self.btn_theme_divine, "divine_dualism"),
            (self.btn_theme_ny, "ny_art_deco"),
        ]:
            if tid == current:
                btn.setStyleSheet(
                    f"QPushButton {{ background: {c['gold']}; color: {c['bg_void']}; "
                    f"border: 1px solid {c['gold']}; border-radius: 3px; font-weight: bold; font-size: 8pt; }}"
                )
            else:
                btn.setStyleSheet(
                    f"QPushButton {{ background: {c['bg_card']}; color: {c['gold_dim']}; "
                    f"border: 1px solid {c['gold_dim']}; border-radius: 3px; font-size: 8pt; }}"
                    f"QPushButton:hover {{ color: {c['gold']}; border-color: {c['gold']}; }}"
                )

    def _rebuild_tabs(self) -> None:
        current = self.tabs.currentIndex()
        while self.tabs.count() > 0:
            self.tabs.removeTab(0)
        self.tabs.addTab(self._tab_help(), t("tab.help"))
        self.tabs.addTab(self._tab_broker(), t("tab.broker"))
        self.tabs.addTab(self._tab_telegram(), t("tab.telegram"))
        self.tabs.addTab(self._tab_curator(), t("tab.curator"))
        self.tabs.addTab(self._tab_ai(), t("tab.ai"))
        self.tabs.addTab(self._tab_risk(), t("tab.risk"))
        self.tabs.addTab(self._tab_safety(), t("tab.safety"))
        self.tabs.addTab(self._tab_instruments(), t("tab.instruments"))
        self.tabs.addTab(self._tab_mode(), t("tab.mode"))
        self.tabs.setCurrentIndex(min(current, self.tabs.count() - 1))

    def _make_scroll_tab(self) -> tuple[QScrollArea, QVBoxLayout]:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        theme_id = ThemeManager._current_theme
        if theme_id in ("divine_dualism", "ny_art_deco"):
            inner = MysticScrollContent("divine")
        else:
            inner = QWidget()
            inner.setStyleSheet(f"background: {C['bg_dark']};")
        lay = QVBoxLayout(inner)
        lay.setContentsMargins(24, 16, 24, 16)
        lay.setSpacing(6)
        scroll.setWidget(inner)
        return scroll, lay

    def _add_section(self, lay: QVBoxLayout, text: str) -> None:
        spacer = QLabel("◆")
        spacer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        spacer.setStyleSheet(f"color: {C['gold_dim']}; font-size: 8pt; margin-top: 8px;")
        lay.addWidget(spacer)

        theme_id = ThemeManager._current_theme
        if theme_id in ("divine_dualism", "ny_art_deco"):
            lbl = GlowLabel(text, "#D4AF37", "#5A4A28", 2, False)
            lbl.setFont(QFont("Cinzel", 11, QFont.Weight.Bold))
        else:
            lbl = QLabel(text)
            lbl.setStyleSheet(f"color: {C['gold']}; font-size: 11pt; font-weight: bold;")
        lay.addWidget(lbl)

        line = _GoldLine(1)
        lay.addWidget(line)

    def _add_field(self, lay: QVBoxLayout, label: str, key: str,
                   default: str = "", placeholder: str = "") -> QLineEdit:
        row = QHBoxLayout()
        lbl = QLabel(label)
        lbl.setFixedWidth(260)
        lbl.setStyleSheet(f"color: {C['ivory_dim']};")
        row.addWidget(lbl)

        edit = QLineEdit(str(default))
        if placeholder:
            edit.setPlaceholderText(placeholder)
        row.addWidget(edit, 1)
        lay.addLayout(row)
        self.fields[key] = edit
        return edit

    def _add_hint(self, lay: QVBoxLayout, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setWordWrap(True)
        lbl.setStyleSheet(f"color: {C['gold_dim']}; font-size: 9pt; padding: 4px 0;")
        lay.addWidget(lbl)
        return lbl

    # ── Tabs ──────────────────────────────────────────────────

    def _tab_help(self) -> QWidget:
        scroll, lay = self._make_scroll_tab()

        theme_id = ThemeManager._current_theme
        if theme_id in ("divine_dualism", "ny_art_deco"):
            welcome = GlowLabel(t("help.welcome"), "#D4AF37", "#5A4A28", 2, False)
            welcome.setFont(QFont("Cinzel", 14, QFont.Weight.Bold))
            welcome.setAlignment(Qt.AlignmentFlag.AlignCenter)
            welcome.setFixedHeight(50)
        else:
            welcome = QLabel(t("help.welcome"))
            welcome.setStyleSheet(
                f"color: {C['gold']}; font-size: 14pt; font-weight: bold; "
                f"letter-spacing: 2px; padding: 8px 0;")
            welcome.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(welcome)

        intro = QLabel(t("help.intro"))
        intro.setWordWrap(True)
        intro.setStyleSheet(f"color: {C['ivory']}; font-size: 10pt; padding: 4px 0 12px 0;")
        lay.addWidget(intro)

        tabs_info = [
            ("help.broker.title", "help.broker.subtitle", "help.broker.description"),
            ("help.telegram.title", "help.telegram.subtitle", "help.telegram.description"),
            ("help.curator.title", "help.curator.subtitle", "help.curator.description"),
            ("help.ai.title", "help.ai.subtitle", "help.ai.description"),
            ("help.risk.title", "help.risk.subtitle", "help.risk.description"),
            ("help.safety.title", "help.safety.subtitle", "help.safety.description"),
            ("help.instruments.title", "help.instruments.subtitle", "help.instruments.description"),
            ("help.mode.title", "help.mode.subtitle", "help.mode.description"),
        ]

        for title_key, subtitle_key, desc_key in tabs_info:
            hdr = QLabel(t(title_key))
            hdr.setStyleSheet(
                f"color: {C['gold']}; font-size: 11pt; font-weight: bold; "
                f"padding: 10px 0 0 0;")
            lay.addWidget(hdr)

            sub = QLabel(t(subtitle_key))
            sub.setStyleSheet(f"color: {C['gold_light']}; font-size: 9pt; font-style: italic; padding: 0 0 2px 0;")
            lay.addWidget(sub)

            desc_frame = QFrame()
            desc_frame.setStyleSheet(
                f"QFrame {{ background: {C['bg_card']}; border: 1px solid {C['gold_dim']}; "
                f"border-radius: 3px; padding: 8px; }}")
            desc_lay = QVBoxLayout(desc_frame)
            desc_lay.setContentsMargins(10, 8, 10, 8)
            desc_lbl = QLabel(t(desc_key))
            desc_lbl.setWordWrap(True)
            desc_lbl.setStyleSheet(f"color: {C['ivory']}; font-size: 9pt; line-height: 1.5; border: none;")
            desc_lay.addWidget(desc_lbl)
            lay.addWidget(desc_frame)

        lay.addSpacing(16)
        tip = QLabel(t("help.tip"))
        tip.setWordWrap(True)
        tip.setStyleSheet(
            f"color: {C['emerald']}; font-size: 10pt; font-weight: bold; "
            f"padding: 8px; background: {C['bg_card']}; "
            f"border: 1px solid {C['emerald']}; border-radius: 3px;")
        lay.addWidget(tip)

        lay.addStretch()
        return scroll

    def _tab_broker(self) -> QWidget:
        scroll, lay = self._make_scroll_tab()

        self._add_section(lay, t("broker.select"))

        self.broker_group = QButtonGroup(self)
        self.broker_radios: dict[str, QRadioButton] = {}
        self._broker_field_containers: dict[str, QWidget] = {}

        current_broker = self._g("broker", "name", default="sber")

        BROKER_DEFS = [
            ("sber", t("broker.sber"), t("broker.sber.desc")),
            ("tinkoff", t("broker.tinkoff"), t("broker.tinkoff.desc")),
            ("alor", t("broker.alor"), "Alor OpenAPI"),
            ("finam", t("broker.finam"), "Finam Trade API"),
        ]

        for broker_id, label, desc in BROKER_DEFS:
            rb = QRadioButton(f"{label}\n     {desc}")
            rb.setChecked(broker_id == current_broker)
            rb.setStyleSheet(
                f"QRadioButton {{ color: {C['ivory']}; spacing: 6px; padding: 4px 0; }}"
                f"QRadioButton::indicator {{ width: 14px; height: 14px; "
                f"border: 1px solid {C['gold_dim']}; border-radius: 7px; "
                f"background: {C['bg_card']}; }}"
                f"QRadioButton::indicator:checked {{ background: {C['gold']}; "
                f"border-color: {C['gold']}; }}")
            self.broker_group.addButton(rb)
            self.broker_radios[broker_id] = rb
            lay.addWidget(rb)

            container = QWidget()
            container.setStyleSheet(f"background: {C['bg_dark']};")
            cl = QVBoxLayout(container)
            cl.setContentsMargins(28, 4, 0, 8)
            cl.setSpacing(4)
            self._broker_field_containers[broker_id] = container

            if broker_id == "sber":
                self._add_field(cl, t("broker.quik_host"), "quik_host",
                                self._g("quik", "host", default="127.0.0.1"))
                self._add_field(cl, t("broker.quik_port"), "quik_port",
                                str(self._g("quik", "port", default=34130)))
                self._add_field(cl, t("broker.quik_batch"), "quik_batch",
                                str(self._g("quik", "batch_window_ms", default=100)))
                self._add_field(cl, t("broker.quik_rps"), "quik_rps",
                                str(self._g("quik", "max_requests_per_second", default=50)))
                self._add_field(cl, t("broker.quik_reconnect"), "quik_reconnect",
                                str(self._g("quik", "reconnect_interval_sec", default=5)))

                btn_row = QHBoxLayout()
                btn_auto = QPushButton(t("broker.auto_setup"))
                btn_auto.setStyleSheet(self._gold_button_style())
                btn_auto.clicked.connect(self._quik_auto_setup)
                btn_diag = QPushButton(t("broker.diagnostics"))
                btn_diag.setStyleSheet(self._gold_button_style())
                btn_diag.clicked.connect(self._quik_diagnostics)
                btn_row.addWidget(btn_auto)
                btn_row.addWidget(btn_diag)
                btn_row.addStretch()
                cl.addLayout(btn_row)

            elif broker_id == "tinkoff":
                self._add_field(cl, t("broker.api_token"), "tinkoff_token",
                                self._g("broker", "tinkoff_token", default=""),
                                placeholder="t.XXXXXXXXXXXXXXXXXXXXX")
                self.tinkoff_sandbox = QCheckBox(t("broker.tinkoff_sandbox"))
                self.tinkoff_sandbox.setChecked(
                    self._g("broker", "tinkoff_sandbox", default=False))
                cl.addWidget(self.tinkoff_sandbox)
                hint = QLabel(t("broker.tinkoff_hint"))
                hint.setWordWrap(True)
                hint.setStyleSheet(
                    f"color: {C['gold_dim']}; font-size: 9pt; padding: 2px 0;")
                cl.addWidget(hint)

            elif broker_id == "alor":
                self._add_field(cl, t("broker.api_token"), "alor_token",
                                self._g("broker", "alor_token", default=""))
                self._add_field(cl, "Refresh Token:", "alor_refresh",
                                self._g("broker", "alor_refresh_token", default=""))
                hint = QLabel(t("broker.alor_hint"))
                hint.setWordWrap(True)
                hint.setStyleSheet(
                    f"color: {C['gold_dim']}; font-size: 9pt; padding: 2px 0;")
                cl.addWidget(hint)

            elif broker_id == "finam":
                self._add_field(cl, t("broker.api_token"), "finam_token",
                                self._g("broker", "finam_token", default=""))
                self._add_field(cl, "Client ID:", "finam_client_id",
                                self._g("broker", "finam_client_id", default=""))
                hint = QLabel(t("broker.finam_hint"))
                hint.setWordWrap(True)
                hint.setStyleSheet(
                    f"color: {C['gold_dim']}; font-size: 9pt; padding: 2px 0;")
                cl.addWidget(hint)

            lay.addWidget(container)

        self.broker_group.buttonClicked.connect(lambda _: self._update_broker_fields())
        self._update_broker_fields()

        self._add_section(lay, t("broker.account_commissions"))
        self._add_field(lay, t("broker.account"), "broker_account",
                        self._g("broker", "account_id", default=""))
        self._add_field(lay, t("broker.client_code"), "broker_client",
                        self._g("broker", "client_code", default=""))

        self._add_section(lay, t("broker.comm_stocks"))
        self._add_field(lay, t("broker.exchange_fee"), "comm_stock_exchange",
                        str(self._g("commissions", "stocks", "exchange_fee_pct", default=0.01)))
        self._add_field(lay, t("broker.broker_fee"), "comm_stock_broker",
                        str(self._g("commissions", "stocks", "broker_fee_pct", default=0.06)))
        self._add_field(lay, t("broker.clearing_fee"), "comm_stock_clearing",
                        str(self._g("commissions", "stocks", "clearing_fee_pct", default=0.01)))

        self._add_section(lay, t("broker.comm_futures"))
        self._add_field(lay, t("broker.fut_exchange_fee"), "comm_fut_exchange",
                        str(self._g("commissions", "futures", "exchange_fee_per_contract", default=1.0)))
        self._add_field(lay, t("broker.fut_broker_fee"), "comm_fut_broker",
                        str(self._g("commissions", "futures", "broker_fee_per_contract", default=0.5)))
        self._add_field(lay, t("broker.fut_clearing_fee"), "comm_fut_clearing",
                        str(self._g("commissions", "futures", "clearing_fee_per_contract", default=0.5)))
        lay.addStretch()
        return scroll

    def _get_selected_broker(self) -> str:
        for bid, rb in self.broker_radios.items():
            if rb.isChecked():
                return bid
        return "sber"

    def _update_broker_fields(self) -> None:
        """Show/hide broker-specific fields and pre-fill commissions."""
        selected = self._get_selected_broker()
        for bid, container in self._broker_field_containers.items():
            container.setVisible(bid == selected)

        COMMISSION_DEFAULTS = {
            "sber":    {"stock_broker": 0.06, "fut_broker": 0.5},
            "tinkoff": {"stock_broker": 0.05, "fut_broker": 0.5},
            "alor":    {"stock_broker": 0.05, "fut_broker": 0.5},
            "finam":   {"stock_broker": 0.05, "fut_broker": 0.5},
        }
        defaults = COMMISSION_DEFAULTS.get(selected, {})
        if "comm_stock_broker" in self.fields and defaults:
            self.fields["comm_stock_broker"].setText(str(defaults.get("stock_broker", 0.06)))

    def _quik_auto_setup(self) -> None:
        try:
            from hedge_fund.quik.auto_setup import QuikAutoSetup
            QuikAutoSetup.show_setup_wizard(self)
        except Exception as e:
            QMessageBox.warning(self, t("msg.error"), t("msg.quik_wizard_fail").format(e))

    def _quik_diagnostics(self) -> None:
        try:
            from hedge_fund.quik.auto_setup import QuikAutoSetup
            setup = QuikAutoSetup()
            diag = setup.run_diagnostics()
            lines = []
            for key, label in [
                ("quik_found", t("diag.quik_found")),
                ("quik_path", t("diag.path")),
                ("quik_running", t("diag.quik_running")),
                ("quik_version", t("diag.version")),
                ("lua_script_installed", t("diag.script_installed")),
                ("tcp_port_open", t("diag.tcp_port")),
                ("connection_test", t("diag.connection")),
            ]:
                val = diag.get(key, "")
                if isinstance(val, bool):
                    lines.append(f"{'✓' if val else '✗'} {label}")
                elif val:
                    lines.append(f"  {label}: {val}")
            if diag.get("issues"):
                lines.append("")
                for issue in diag["issues"]:
                    lines.append(f"⚠ {issue}")
            if diag.get("fixes"):
                for fix in diag["fixes"]:
                    lines.append(f"💡 {fix}")
            QMessageBox.information(self, t("msg.quik_diag_title"), "\n".join(lines))
        except Exception as e:
            QMessageBox.warning(self, t("msg.error"), t("msg.quik_diag_fail").format(e))

    def _tab_telegram(self) -> QWidget:
        scroll, lay = self._make_scroll_tab()
        self._add_section(lay, t("telegram.section"))
        self._add_field(lay, t("telegram.token"), "tg_token",
                        self._g("telegram", "token", default=""))
        self._add_field(lay, t("telegram.chat_id"), "tg_chat_id",
                        self._g("telegram", "chat_id", default=""))
        self._add_field(lay, t("telegram.interval"), "tg_interval",
                        str(self._g("telegram", "report_interval_minutes", default=60)))

        btn = QPushButton(t("telegram.test"))
        btn.setStyleSheet(self._gold_button_style())
        btn.clicked.connect(self._test_telegram)
        lay.addWidget(btn)

        self.tg_status = QLabel("")
        self.tg_status.setStyleSheet(f"color: {C['emerald']}; font-size: 9pt;")
        lay.addWidget(self.tg_status)

        self._add_hint(lay, t("telegram.hint"))
        lay.addStretch()
        return scroll

    def _tab_ai(self) -> QWidget:
        scroll, lay = self._make_scroll_tab()
        self._add_section(lay, t("ai.section_llm"))
        self._add_field(lay, t("ai.url"), "ai_url",
                        self._g("ai", "base_url", default="http://localhost:11434"))
        self._add_field(lay, t("ai.model"), "ai_model",
                        self._g("ai", "model", default="llama3.1"))
        self._add_field(lay, t("ai.temp"), "ai_temp",
                        str(self._g("ai", "temperature", default=0.3)))

        btn = QPushButton(t("ai.check"))
        btn.setStyleSheet(self._gold_button_style())
        btn.clicked.connect(self._test_ollama)
        lay.addWidget(btn)

        self.ollama_status = QLabel("")
        self.ollama_status.setStyleSheet(f"color: {C['emerald']}; font-size: 9pt;")
        lay.addWidget(self.ollama_status)

        self._add_section(lay, t("ai.section_ml"))
        self._add_field(lay, t("ai.retrain"), "ml_retrain",
                        str(self._g("ml", "retrain_interval_hours", default=24)))
        self._add_field(lay, t("ai.min_samples"), "ml_samples",
                        str(self._g("ml", "min_samples", default=1000)))
        self._add_field(lay, t("ai.features_window"), "ml_window",
                        str(self._g("ml", "features_window", default=100)))
        lay.addStretch()
        return scroll

    def _tab_curator(self) -> QWidget:
        scroll, lay = self._make_scroll_tab()
        self._add_section(lay, t("curator.title"))
        self._add_hint(lay, t("curator.hint"))

        self.curator_enabled = QCheckBox(t("curator.enable"))
        self.curator_enabled.setChecked(self._g("curator", "enabled", default=False))
        self.curator_enabled.setStyleSheet(
            f"QCheckBox {{ color: {C['gold_light']}; spacing: 6px; font-size: 10pt; }}"
            f"QCheckBox::indicator {{ width: 16px; height: 16px; border: 1px solid {C['gold_dim']}; "
            f"border-radius: 2px; background: {C['bg_card']}; }}"
            f"QCheckBox::indicator:checked {{ background: {C['gold']}; }}")
        lay.addWidget(self.curator_enabled)

        self.curator_token = self._add_field(lay, t("curator.token"),
            self._g("curator", "token", default=""))
        self.curator_chat_id = self._add_field(lay, t("curator.chat_id"),
            self._g("curator", "chat_id", default=""))

        self._add_hint(lay, t("curator.tip"))

        lay.addStretch()
        return scroll

    def _tab_safety(self) -> QWidget:
        scroll, lay = self._make_scroll_tab()
        self._add_section(lay, t("safety.training"))
        self._add_hint(lay, t("safety.training_hint"))

        self.training_days = self._add_field(lay, t("safety.training_days"),
            str(self._g("safety", "training_period_days", default=14)))

        self._add_section(lay, t("safety.loss_section"))
        self.daily_lock = QCheckBox(t("safety.loss_lock"))
        self.daily_lock.setChecked(self._g("safety", "daily_loss_lock_enabled", default=True))
        self.daily_lock.setStyleSheet(
            f"QCheckBox {{ color: {C['ivory']}; spacing: 6px; }}"
            f"QCheckBox::indicator {{ width: 14px; height: 14px; border: 1px solid {C['gold_dim']}; "
            f"border-radius: 2px; background: {C['bg_card']}; }}"
            f"QCheckBox::indicator:checked {{ background: {C['emerald']}; }}")
        lay.addWidget(self.daily_lock)

        self.trade_threshold = self._add_field(lay, t("safety.trade_threshold"),
            str(self._g("safety", "large_trade_threshold_rub", default=50000)))

        self._add_section(lay, t("safety.pin_section"))
        self.pin_required = QCheckBox(t("safety.pin_required"))
        self.pin_required.setChecked(self._g("safety", "pin_required_for_live", default=True))
        self.pin_required.setStyleSheet(
            f"QCheckBox {{ color: {C['ivory']}; spacing: 6px; }}"
            f"QCheckBox::indicator {{ width: 14px; height: 14px; border: 1px solid {C['gold_dim']}; "
            f"border-radius: 2px; background: {C['bg_card']}; }}"
            f"QCheckBox::indicator:checked {{ background: {C['emerald']}; }}")
        lay.addWidget(self.pin_required)

        pin_btn = QPushButton(t("safety.pin_setup"))
        pin_btn.setStyleSheet(
            f"QPushButton {{ background: {C['bg_card']}; color: {C['gold']}; "
            f"border: 1px solid {C['gold_dim']}; border-radius: 3px; padding: 6px 16px; }}"
            f"QPushButton:hover {{ background: {C['obsidian']}; border-color: {C['gold']}; }}")
        pin_btn.clicked.connect(self._setup_pin)
        lay.addWidget(pin_btn)

        self._add_section(lay, t("safety.backup_section"))
        self.auto_backup = QCheckBox(t("safety.backup_auto"))
        self.auto_backup.setChecked(self._g("safety", "auto_backup_enabled", default=True))
        self.auto_backup.setStyleSheet(
            f"QCheckBox {{ color: {C['ivory']}; spacing: 6px; }}"
            f"QCheckBox::indicator {{ width: 14px; height: 14px; border: 1px solid {C['gold_dim']}; "
            f"border-radius: 2px; background: {C['bg_card']}; }}"
            f"QCheckBox::indicator:checked {{ background: {C['emerald']}; }}")
        lay.addWidget(self.auto_backup)

        backup_btn = QPushButton(t("safety.backup_manage"))
        backup_btn.setStyleSheet(
            f"QPushButton {{ background: {C['bg_card']}; color: {C['gold']}; "
            f"border: 1px solid {C['gold_dim']}; border-radius: 3px; padding: 6px 16px; }}"
            f"QPushButton:hover {{ background: {C['obsidian']}; border-color: {C['gold']}; }}")
        backup_btn.clicked.connect(self._show_backup_manager)
        lay.addWidget(backup_btn)

        self._add_section(lay, t("safety.profile"))
        self._add_hint(lay, t("safety.profile_hint"))

        self.risk_profile_group = QButtonGroup(self)
        profiles = [
            ("conservative", t("safety.conservative"), t("safety.conservative.desc")),
            ("moderate", t("safety.moderate"), t("safety.moderate.desc")),
            ("aggressive", t("safety.aggressive"), t("safety.aggressive.desc")),
        ]
        current_profile = self._g("safety", "risk_profile", default="moderate")
        self.risk_profile_buttons: dict[str, QRadioButton] = {}
        for key, label, desc in profiles:
            rb = QRadioButton(f"{label}\n     {desc}")
            rb.setChecked(key == current_profile)
            rb.setStyleSheet(
                f"QRadioButton {{ color: {C['ivory']}; spacing: 6px; padding: 4px 0; }}"
                f"QRadioButton::indicator {{ width: 14px; height: 14px; border: 1px solid {C['gold_dim']}; "
                f"border-radius: 7px; background: {C['bg_card']}; }}"
                f"QRadioButton::indicator:checked {{ background: {C['gold']}; border-color: {C['gold']}; }}")
            self.risk_profile_group.addButton(rb)
            self.risk_profile_buttons[key] = rb
            lay.addWidget(rb)

        lay.addStretch()
        return scroll

    def _setup_pin(self) -> None:
        try:
            from hedge_fund.core.pin_protection import PinProtection
            PinProtection.show_pin_setup_dialog(self)
        except Exception as e:
            QMessageBox.warning(self, t("msg.error"), t("msg.pin_fail").format(e))

    def _show_backup_manager(self) -> None:
        try:
            from hedge_fund.core.config_backup import ConfigBackup
            ConfigBackup.show_backup_manager_dialog(self)
        except Exception as e:
            QMessageBox.warning(self, t("msg.error"), t("msg.backup_fail").format(e))

    def _tab_risk(self) -> QWidget:
        scroll, lay = self._make_scroll_tab()
        self._add_section(lay, t("risk.section"))
        self._add_field(lay, t("risk.max_drawdown"), "risk_drawdown",
                        str(self._g("risk", "max_drawdown_pct", default=5.0)))
        self._add_field(lay, t("risk.max_position"), "risk_position",
                        str(self._g("risk", "max_position_pct", default=10.0)))
        self._add_field(lay, t("risk.daily_loss"), "risk_daily_loss",
                        str(self._g("risk", "max_daily_loss_pct", default=2.0)))
        self._add_field(lay, t("risk.correlation"), "risk_correlation",
                        str(self._g("risk", "max_correlation", default=0.7)))
        self._add_field(lay, t("risk.max_positions"), "risk_max_pos",
                        str(self._g("risk", "max_open_positions", default=20)))
        self._add_field(lay, t("risk.stop_loss"), "risk_sl",
                        str(self._g("risk", "stop_loss_default_pct", default=1.5)))
        lay.addStretch()
        return scroll

    def _tab_instruments(self) -> QWidget:
        scroll, lay = self._make_scroll_tab()

        # Currently enabled instruments from config
        enabled_stocks = set(self._g("instruments", "stocks", default=[]) or [])
        enabled_futures = set(self._g("instruments", "futures", default=[]) or [])
        enabled_all = enabled_stocks | enabled_futures

        self.instrument_checks: dict[str, QCheckBox] = {}

        btn_row = QHBoxLayout()
        btn_select_all = QPushButton(t("instruments.select_all"))
        btn_select_all.setFixedHeight(28)
        btn_select_all.setStyleSheet(
            f"QPushButton {{ background: {C['bg_card']}; color: {C['gold']}; border: 1px solid {C['gold_dim']}; "
            f"border-radius: 3px; padding: 2px 12px; font-size: 9pt; }}"
            f"QPushButton:hover {{ border-color: {C['gold']}; }}")
        btn_select_all.clicked.connect(lambda: self._toggle_all_instruments(True))
        btn_deselect = QPushButton(t("instruments.deselect_all"))
        btn_deselect.setFixedHeight(28)
        btn_deselect.setStyleSheet(btn_select_all.styleSheet())
        btn_deselect.clicked.connect(lambda: self._toggle_all_instruments(False))
        btn_row.addWidget(btn_select_all)
        btn_row.addWidget(btn_deselect)
        btn_row.addStretch()
        lay.addLayout(btn_row)

        # ticker -> (name, risk%, profit%, volatility_note)
        # Risk = avg annual drawdown estimate; Profit = avg annual upside estimate
        MOEX_INSTRUMENTS: dict[str, list[tuple[str, str, int, int, str]]] = {
            "🛢 НЕФТЬ И ГАЗ": [
                ("GAZP", "Газпром", 35, 40, "высокая волатильность, зависит от газа/геополитики"),
                ("LKOH", "Лукойл", 25, 35, "стабильные дивиденды, умеренный риск"),
                ("ROSN", "Роснефть", 30, 35, "госкомпания, привязка к нефти"),
                ("NVTK", "Новатэк", 30, 45, "рост СПГ, высокий потенциал"),
                ("SNGS", "Сургутнефтегаз", 20, 25, "валютная подушка, низкий риск"),
                ("SNGSP", "Сургутнефтегаз-п", 25, 40, "высокие дивиденды при слабом рубле"),
                ("TATN", "Татнефть", 25, 30, "стабильный дивидендный поток"),
                ("TATNP", "Татнефть-п", 20, 35, "дивидендная привилегированная"),
                ("BANEP", "Башнефть-п", 25, 30, "дивиденды, умеренный рост"),
                ("SIBN", "Газпром нефть", 25, 30, "дочка Газпрома, стабильнее"),
            ],
            "🏦 БАНКИ И ФИНАНСЫ": [
                ("SBER", "Сбербанк", 30, 40, "голубая фишка №1, высокая ликвидность"),
                ("SBERP", "Сбербанк-п", 28, 45, "привилегированная, выше дивиденды"),
                ("VTBR", "ВТБ", 45, 50, "высокий риск, возможны допэмиссии"),
                ("TCSG", "TCS Group (Тинькофф)", 40, 55, "быстрый рост, высокая волатильность"),
                ("MOEX", "Московская биржа", 20, 30, "монополия, стабильный доход"),
                ("CBOM", "МКБ", 40, 35, "средний банк, повышенный риск"),
                ("BSPB", "Банк СПБ", 35, 35, "региональный банк"),
                ("SFIN", "SFI", 45, 40, "высокая волатильность"),
            ],
            "⛏ МЕТАЛЛУРГИЯ И ДОБЫЧА": [
                ("GMKN", "Норникель", 30, 35, "мировой лидер, никель/палладий"),
                ("NLMK", "НЛМК", 30, 35, "экспортёр стали, валютная выручка"),
                ("CHMF", "Северсталь", 28, 35, "дивидендный чемпион металлургии"),
                ("MAGN", "ММК", 30, 30, "внутренний рынок стали"),
                ("ALRS", "АЛРОСА", 35, 30, "монополия на алмазы, цикличность"),
                ("RUAL", "Русал", 45, 50, "алюминий, высокая цикличность"),
                ("PLZL", "Полюс Золото", 25, 45, "защитный актив, золото"),
                ("POLY", "Polymetal", 35, 40, "золото/серебро, реструктуризация"),
                ("MTLR", "Мечел", 55, 60, "высокий долг = высокий риск/профит"),
                ("MTLRP", "Мечел-п", 50, 65, "спекулятивная, высокие дивиденды"),
                ("VSMO", "ВСМПО-АВИСМА", 25, 25, "титан, стабильная ниша"),
            ],
            "⚡ ЭНЕРГЕТИКА": [
                ("IRAO", "Интер РАО", 20, 25, "стабильная, низкая волатильность"),
                ("HYDR", "РусГидро", 25, 25, "госкомпания, предсказуемая"),
                ("FEES", "ФСК ЕЭС", 30, 25, "регулируемые тарифы"),
                ("MSNG", "Мосэнерго", 25, 20, "региональная энергетика"),
                ("OGKB", "ОГК-2", 30, 25, "дочка Газпром энергохолдинга"),
                ("TGKA", "ТГК-1", 30, 25, "генерация, Северо-Запад"),
                ("UPRO", "Юнипро", 20, 20, "стабильные дивиденды, низкий рост"),
                ("LSNG", "Ленэнерго", 25, 20, "сетевая компания"),
                ("LSNGP", "Ленэнерго-п", 20, 30, "высокие дивиденды по уставу"),
            ],
            "📡 ТЕЛЕКОМ И IT": [
                ("YNDX", "Яндекс", 40, 60, "технологический лидер, высокий рост"),
                ("MTSS", "МТС", 20, 25, "дивидендная корова, стабильно"),
                ("RTKM", "Ростелеком", 20, 20, "госоператор, медленный рост"),
                ("RTKMP", "Ростелеком-п", 18, 25, "дивидендная привилегированная"),
                ("OZON", "Ozon", 50, 65, "e-commerce рост, пока без прибыли"),
                ("VKCO", "VK", 45, 50, "соцсети, реструктуризация"),
                ("HHRU", "HeadHunter", 35, 50, "монополия HR, рост"),
                ("CIAN", "Циан", 40, 45, "недвижимость онлайн"),
                ("POSI", "Positive Technologies", 35, 55, "кибербезопасность, быстрый рост"),
            ],
            "🏬 РИТЕЙЛ И ПОТРЕБ.": [
                ("MGNT", "Магнит", 25, 30, "второй ритейлер, дивиденды"),
                ("FIVE", "X5 Group", 25, 35, "лидер ритейла, стабильный рост"),
                ("FIXP", "Fix Price", 30, 35, "дискаунтер, экспансия"),
                ("LENT", "Лента", 30, 25, "гипермаркеты, трансформация"),
                ("DSKY", "Детский мир", 25, 25, "детские товары, стабильно"),
                ("MVID", "М.Видео", 45, 35, "электроника, высокий долг"),
            ],
            "🚛 ТРАНСПОРТ": [
                ("AFLT", "Аэрофлот", 50, 45, "авиа, высокая цикличность"),
                ("NMTP", "НМТП", 25, 25, "порт, стабильный грузооборот"),
                ("GLTR", "Globaltrans", 30, 30, "ж/д перевозки, дивиденды"),
                ("FLOT", "Совкомфлот", 30, 30, "танкерный флот"),
                ("FESH", "ДВМП", 40, 40, "контейнерные перевозки"),
            ],
            "🏗 СТРОИТЕЛЬСТВО И НЕДВИЖ.": [
                ("PIKK", "ПИК", 35, 35, "лидер жилого строительства"),
                ("SMLT", "Самолёт", 40, 50, "быстрый рост, высокий долг"),
                ("LSRG", "ЛСР", 30, 30, "диверсифицированный застройщик"),
                ("ETLN", "Эталон", 35, 30, "реструктуризация"),
            ],
            "🧪 ХИМИЯ И УДОБРЕНИЯ": [
                ("PHOR", "ФосАгро", 25, 35, "удобрения, мировой спрос"),
                ("AKRN", "Акрон", 25, 30, "удобрения, экспорт"),
                ("KAZT", "КуйбышевАзот", 30, 25, "химия, внутренний рынок"),
                ("NKNC", "Нижнекамскнефтехим", 30, 25, "нефтехимия"),
            ],
            "📦 ПРОЧИЕ АКЦИИ": [
                ("AGRO", "РусАгро", 30, 35, "агросектор, экспорт"),
                ("RNFT", "РуссНефть", 40, 30, "малая нефтянка"),
                ("SGZH", "Сегежа", 55, 40, "лесопром, высокий долг"),
                ("TRNFP", "Транснефть-п", 20, 25, "монополия трубопроводов, стабильно"),
                ("RGSS", "Россети", 30, 25, "электросети"),
                ("IRKT", "Иркут/ОАК", 50, 55, "авиастроение, гособоронзаказ"),
                ("AQUA", "ИНАРКТИКА", 30, 35, "аквакультура, рост рынка"),
            ],
        }

        FUTURES: dict[str, list[tuple[str, str, int, int, str]]] = {
            "📈 ИНДЕКСНЫЕ ФЬЮЧЕРСЫ": [
                ("RIZ4", "RTS Index", 40, 50, "основной индексный фьючерс, высокое плечо"),
                ("MXZ4", "MOEX Index", 35, 45, "рублёвый индекс"),
                ("MMZ4", "MiniMOEX", 35, 45, "мини-контракт, для малых депозитов"),
            ],
            "💱 ВАЛЮТНЫЕ ФЬЮЧЕРСЫ": [
                ("SiZ4", "USD/RUB", 30, 40, "самый ликвидный фьючерс MOEX"),
                ("EuZ4", "EUR/RUB", 30, 35, "валютный хедж, средняя ликвидность"),
                ("CNZ4", "CNY/RUB", 25, 30, "юань, растущая ликвидность"),
                ("GUZ4", "GBP/USD", 25, 30, "кросс-курс"),
                ("EDZ4", "EUR/USD", 20, 25, "кросс-курс, низкий спред"),
            ],
            "🛢 ТОВАРНЫЕ ФЬЮЧЕРСЫ": [
                ("BRF5", "Brent Oil", 40, 50, "нефть Brent, высокая волатильность"),
                ("CLF5", "WTI Oil", 40, 50, "нефть WTI"),
                ("NGF5", "Natural Gas", 55, 65, "газ, экстремальная волатильность"),
                ("GDF5", "Gasoil", 35, 40, "дизельное топливо"),
            ],
            "🥇 ДРАГ. МЕТАЛЛЫ (ФЬЮЧЕРСЫ)": [
                ("GDZ4", "Золото", 20, 30, "защитный актив, тренд вверх"),
                ("SVZ4", "Серебро", 30, 40, "промышленный + защитный металл"),
                ("PTZ4", "Платина", 35, 40, "редкий, промышленный спрос"),
                ("PDZ4", "Палладий", 40, 50, "автопром, высокая волатильность"),
            ],
            "🏦 ФЬЮЧЕРСЫ НА АКЦИИ": [
                ("SRZ4", "Сбербанк", 35, 45, "самый ликвидный фьючерс на акцию"),
                ("GZZ4", "Газпром", 40, 45, "высокая волатильность"),
                ("LKZ4", "Лукойл", 30, 40, "нефтяной сектор"),
                ("RNZ4", "Роснефть", 35, 40, "госнефтянка"),
                ("VBZ4", "ВТБ", 50, 55, "высокий риск, спекулятивный"),
                ("TRZ4", "Татнефть", 30, 35, "средняя волатильность"),
                ("NKZ4", "Норникель", 35, 40, "металлургия"),
                ("YNZ4", "Яндекс", 45, 60, "IT-сектор, высокая бета"),
                ("MGZ4", "Магнит", 30, 35, "ритейл"),
                ("ALZ4", "АЛРОСА", 35, 35, "алмазы"),
            ],
        }

        CB_STYLE_STOCK = (
            f"QCheckBox {{ color: {C['ivory']}; spacing: 6px; padding: 1px 0; }}"
            f"QCheckBox::indicator {{ width: 14px; height: 14px; border: 1px solid {C['gold_dim']}; "
            f"border-radius: 2px; background: {C['bg_card']}; }}"
            f"QCheckBox::indicator:checked {{ background: {C['gold']}; border-color: {C['gold']}; }}"
            f"QCheckBox::indicator:hover {{ border-color: {C['gold_light']}; }}"
        )
        CB_STYLE_FUT = (
            f"QCheckBox {{ color: {C['ivory']}; spacing: 6px; padding: 1px 0; }}"
            f"QCheckBox::indicator {{ width: 14px; height: 14px; border: 1px solid {C['bronze']}; "
            f"border-radius: 2px; background: {C['bg_card']}; }}"
            f"QCheckBox::indicator:checked {{ background: {C['bronze']}; border-color: {C['gold']}; }}"
            f"QCheckBox::indicator:hover {{ border-color: {C['gold_light']}; }}"
        )

        def _risk_color(pct: int) -> str:
            if pct <= 25:
                return C["emerald"]
            elif pct <= 35:
                return C["gold"]
            elif pct <= 45:
                return C["bronze"]
            else:
                return C["crimson_bright"]

        def _profit_color(pct: int) -> str:
            if pct >= 50:
                return C["emerald"]
            elif pct >= 35:
                return C["gold_light"]
            else:
                return C["ivory_dim"]

        def _add_instrument_row(parent_lay: QVBoxLayout, ticker: str, name: str,
                                risk: int, profit: int, note_key: str,
                                is_future: bool) -> None:
            row = QHBoxLayout()
            row.setSpacing(6)
            cb = QCheckBox(f"{ticker}")
            cb.setFixedWidth(70)
            cb.setChecked(ticker in enabled_all)
            cb.setStyleSheet(CB_STYLE_FUT if is_future else CB_STYLE_STOCK)
            self.instrument_checks[ticker] = cb
            row.addWidget(cb)

            name_lbl = QLabel(name)
            name_lbl.setFixedWidth(180)
            name_lbl.setStyleSheet(f"color: {C['ivory']}; font-size: 9pt;")
            row.addWidget(name_lbl)

            i18n_key = f"instr.{ticker}.note"
            translated = t(i18n_key)
            note_text = translated if translated != i18n_key else note_key
            risk_lbl = QLabel(f"⚠ {risk}%")
            risk_lbl.setFixedWidth(50)
            risk_lbl.setToolTip(t("instruments.risk_tooltip").format(risk, note_text))
            risk_lbl.setStyleSheet(f"color: {_risk_color(risk)}; font-size: 8pt; font-weight: bold;")
            row.addWidget(risk_lbl)

            profit_lbl = QLabel(f"▲ {profit}%")
            profit_lbl.setFixedWidth(50)
            profit_lbl.setToolTip(t("instruments.profit_tooltip").format(profit, note_text))
            profit_lbl.setStyleSheet(f"color: {_profit_color(profit)}; font-size: 8pt; font-weight: bold;")
            row.addWidget(profit_lbl)

            note_lbl = QLabel(note_text)
            note_lbl.setStyleSheet(f"color: {C['ivory_dim']}; font-size: 8pt; font-style: italic;")
            row.addWidget(note_lbl, 1)

            parent_lay.addLayout(row)

        # Column headers
        hdr = QHBoxLayout()
        hdr.setSpacing(6)
        for text, w in [("", 70), (t("instruments.header_instrument"), 180), (t("instruments.risk"), 50), (t("instruments.profit"), 50), (t("instruments.note"), 300)]:
            lbl = QLabel(text)
            if w < 300:
                lbl.setFixedWidth(w)
            else:
                lbl.setMinimumWidth(100)
            lbl.setStyleSheet(f"color: {C['gold_dim']}; font-size: 8pt; font-weight: bold;")
            hdr.addWidget(lbl, 1 if w >= 300 else 0)
        lay.addLayout(hdr)

        SECTION_I18N = {
            "🛢 НЕФТЬ И ГАЗ": "instr.section.oil_gas",
            "🏦 БАНКИ И ФИНАНСЫ": "instr.section.banks",
            "⛏ МЕТАЛЛУРГИЯ И ДОБЫЧА": "instr.section.metals",
            "⚡ ЭНЕРГЕТИКА": "instr.section.energy",
            "📡 ТЕЛЕКОМ И IT": "instr.section.telecom",
            "🏬 РИТЕЙЛ И ПОТРЕБ.": "instr.section.retail",
            "🚛 ТРАНСПОРТ": "instr.section.transport",
            "🏗 СТРОИТЕЛЬСТВО И НЕДВИЖ.": "instr.section.construction",
            "🧪 ХИМИЯ И УДОБРЕНИЯ": "instr.section.chemistry",
            "📦 ПРОЧИЕ АКЦИИ": "instr.section.other",
            "📈 ИНДЕКСНЫЕ ФЬЮЧЕРСЫ": "instr.section.index_futures",
            "💱 ВАЛЮТНЫЕ ФЬЮЧЕРСЫ": "instr.section.fx_futures",
            "🛢 ТОВАРНЫЕ ФЬЮЧЕРСЫ": "instr.section.commodity_futures",
            "🥇 ДРАГ. МЕТАЛЛЫ (ФЬЮЧЕРСЫ)": "instr.section.metal_futures",
            "🏦 ФЬЮЧЕРСЫ НА АКЦИИ": "instr.section.stock_futures",
        }

        for section_name, tickers in MOEX_INSTRUMENTS.items():
            self._add_section(lay, t(SECTION_I18N.get(section_name, section_name)))
            for ticker, name, risk, profit, note in tickers:
                _add_instrument_row(lay, ticker, name, risk, profit, note, False)

        for section_name, tickers in FUTURES.items():
            self._add_section(lay, t(SECTION_I18N.get(section_name, section_name)))
            for ticker, name, risk, profit, note in tickers:
                _add_instrument_row(lay, ticker, name, risk, profit, note, True)

        self._add_section(lay, t("instruments.manual"))
        self._add_hint(lay, t("instruments.manual_hint"))
        self.manual_tickers_edit = QTextEdit()
        self.manual_tickers_edit.setFixedHeight(60)
        self.manual_tickers_edit.setPlaceholderText("Например: NKHP, KZOS, AMEZ, ELFV, NGH5, ...")
        self.manual_tickers_edit.setStyleSheet(
            f"QTextEdit {{ background: {C['bg_card']}; color: {C['ivory']}; "
            f"border: 1px solid {C['gold_dim']}; border-radius: 3px; "
            f"font: 10pt 'Consolas'; padding: 4px; }}"
            f"QTextEdit:focus {{ border-color: {C['gold']}; }}")
        lay.addWidget(self.manual_tickers_edit)

        lay.addStretch()
        return scroll

    def _toggle_all_instruments(self, state: bool) -> None:
        for cb in self.instrument_checks.values():
            cb.setChecked(state)

    def _tab_mode(self) -> QWidget:
        scroll, lay = self._make_scroll_tab()
        self._add_section(lay, t("mode.trading"))

        self.mode_paper = QRadioButton(t("mode.paper"))
        self.mode_live = QRadioButton(t("mode.live"))
        mode_group = QButtonGroup(self)
        mode_group.addButton(self.mode_paper)
        mode_group.addButton(self.mode_live)
        current_mode = self._g("system", "mode", default="paper")
        if current_mode == "live":
            self.mode_live.setChecked(True)
        else:
            self.mode_paper.setChecked(True)
        lay.addWidget(self.mode_paper)
        lay.addWidget(self.mode_live)

        warn = QLabel(t("mode.warning"))
        warn.setWordWrap(True)
        warn.setStyleSheet(f"color: {C['crimson_bright']}; font-size: 9pt; padding: 6px 0;")
        lay.addWidget(warn)

        self._add_section(lay, t("mode.agents"))
        agents_def = [
            ("orchestrator", "⚜ Orchestrator (координатор)"),
            ("scalping", "⚡ Scalping Agent (скальпинг)"),
            ("day_trading", "☀ Day Trading Agent (дейтрейдинг)"),
            ("long_term", "Ω Long Term Agent (долгосрочный)"),
            ("news", "☿ News Agent (новости)"),
            ("risk", "⚖ Risk Agent (безопасность)"),
            ("quant", "◎ Quant Agent (математика)"),
            ("hedging", "☊ Hedging Agent (страхование)"),
            ("sre", "⚙ SRE Agent (мониторинг)"),
        ]
        existing_agents = self._g("agents", default=[])
        agent_enabled_map: dict[str, bool] = {}
        for a in (existing_agents if isinstance(existing_agents, list) else []):
            if isinstance(a, dict):
                agent_enabled_map[a.get("name", "")] = a.get("enabled", True)

        for agent_id, label in agents_def:
            cb = QCheckBox(label)
            cb.setChecked(agent_enabled_map.get(agent_id, True))
            lay.addWidget(cb)
            self.agent_checks[agent_id] = cb

        self._add_section(lay, t("mode.extra"))
        self.dashboard_check = QCheckBox(t("mode.dashboard"))
        self.dashboard_check.setChecked(True)
        lay.addWidget(self.dashboard_check)

        self.voice_check = QCheckBox(t("mode.voice"))
        self.voice_check.setChecked(False)
        lay.addWidget(self.voice_check)

        lay.addStretch()
        return scroll

    # ── Button bar ────────────────────────────────────────────

    def _gold_button_style(self) -> str:
        return (
            f"QPushButton {{ background: {C['bg_card']}; color: {C['gold']}; "
            f"border: 1px solid {C['gold_dim']}; border-radius: 4px; "
            f"padding: 7px 20px; font-weight: bold; font-size: 10pt; }}"
            f"QPushButton:hover {{ border-color: {C['gold']}; color: {C['gold_light']}; }}"
            f"QPushButton:pressed {{ background: {C['obsidian']}; }}"
        )

    def _button_bar(self) -> QHBoxLayout:
        bar = QHBoxLayout()
        bar.setContentsMargins(24, 10, 24, 10)

        btn_save = QPushButton(t("btn.save"))
        btn_save.setStyleSheet(self._gold_button_style())
        btn_save.clicked.connect(self._on_save)

        btn_launch = QPushButton(t("btn.launch"))
        btn_launch.setStyleSheet(
            f"QPushButton {{ background: {C['gold']}; color: {C['bg_void']}; "
            f"border: 2px solid {C['gold_light']}; border-radius: 4px; "
            f"padding: 8px 28px; font-weight: bold; font-size: 11pt; }}"
            f"QPushButton:hover {{ background: {C['gold_light']}; }}"
            f"QPushButton:pressed {{ background: {C['bronze']}; }}"
        )
        theme_id = ThemeManager._current_theme
        if theme_id in ("divine_dualism", "ny_art_deco"):
            btn_launch.setStyleSheet(
                "QPushButton { "
                "  background: qlineargradient(x1:0, y1:0, x2:1, y2:0,"
                "    stop:0 #FFD700, stop:0.44 #E6C687,"
                "    stop:0.48 #5A000A, stop:0.52 #5A000A,"
                "    stop:0.56 #0A0A0C, stop:1 #121216);"
                "  color: #FFFACD;"
                "  border: 2px solid #D4AF37;"
                "  border-top: 3px solid #FFE44D;"
                "  border-bottom: 3px solid rgba(0,0,0,180);"
                "  border-radius: 6px;"
                "  padding: 10px 36px;"
                "  font-family: 'Cinzel', 'Georgia';"
                "  font-weight: bold; font-size: 11pt;"
                "  letter-spacing: 3px;"
                "}"
                "QPushButton:hover {"
                "  background: qlineargradient(x1:0, y1:0, x2:1, y2:0,"
                "    stop:0 #FFE44D, stop:0.44 #FFD700,"
                "    stop:0.48 #8B0015, stop:0.52 #8B0015,"
                "    stop:0.56 #1A1A20, stop:1 #2A2A30);"
                "  border-color: #FFE44D;"
                "  color: #FFFFFF;"
                "}"
                "QPushButton:pressed {"
                "  background: qlineargradient(x1:0, y1:0, x2:1, y2:0,"
                "    stop:0 #B8960C, stop:0.44 #8B7424,"
                "    stop:0.48 #3A0005, stop:0.52 #3A0005,"
                "    stop:0.56 #060608, stop:1 #0A0A0C);"
                "  border-top: 3px solid rgba(0,0,0,200);"
                "  border-bottom: 2px solid #D4AF37;"
                "}"
            )
        btn_launch.clicked.connect(self._on_run)

        btn_cancel = QPushButton(t("btn.cancel"))
        btn_cancel.setStyleSheet(
            f"QPushButton {{ background: {C['bg_card']}; color: {C['crimson_bright']}; "
            f"border: 1px solid {C['crimson']}; border-radius: 4px; "
            f"padding: 7px 20px; font-weight: bold; }}"
            f"QPushButton:hover {{ border-color: {C['crimson_bright']}; }}"
        )
        btn_cancel.clicked.connect(self._on_cancel)

        bar.addWidget(btn_save)
        bar.addStretch()
        bar.addWidget(btn_launch)
        bar.addStretch()
        bar.addWidget(btn_cancel)
        return bar

    # ── Actions ───────────────────────────────────────────────

    def _v(self, key: str) -> str:
        if key in self.fields:
            return self.fields[key].text().strip()
        if key in self.text_fields:
            return self.text_fields[key].toPlainText().strip()
        return ""

    def _f(self, key: str) -> float:
        try:
            return float(self._v(key))
        except ValueError:
            return 0.0

    def _i(self, key: str) -> int:
        try:
            return int(float(self._v(key)))
        except ValueError:
            return 0

    def _collect_config(self) -> dict[str, Any]:
        # Collect from instrument checkboxes
        FUTURES_PREFIXES = {"RI", "MX", "MM", "Si", "Eu", "CN", "GU", "ED", "BR", "CL", "NG", "GD",
                            "SV", "PT", "PD", "SR", "GZ", "LK", "RN", "VB", "TR", "NK", "YN", "MG", "AL"}
        stocks_list = []
        futures_list = []
        for ticker, cb in self.instrument_checks.items():
            if cb.isChecked():
                prefix = ticker[:2]
                if prefix in FUTURES_PREFIXES or any(c.isdigit() for c in ticker[-2:]):
                    futures_list.append(ticker)
                else:
                    stocks_list.append(ticker)
        # Add manually entered tickers
        manual_text = self.manual_tickers_edit.toPlainText().strip() if hasattr(self, "manual_tickers_edit") else ""
        for tk in manual_text.replace(";", ",").split(","):
            tk = tk.strip().upper()
            if not tk:
                continue
            prefix = tk[:2]
            if prefix in FUTURES_PREFIXES or any(c.isdigit() for c in tk[-2:]):
                if tk not in futures_list:
                    futures_list.append(tk)
            else:
                if tk not in stocks_list:
                    stocks_list.append(tk)

        existing_agents = self._g("agents", default=[])
        agent_params_map: dict[str, dict] = {}
        for a in (existing_agents if isinstance(existing_agents, list) else []):
            if isinstance(a, dict):
                agent_params_map[a.get("name", "")] = a.get("params", {})

        agents_list = []
        for agent_id, cb in self.agent_checks.items():
            agents_list.append({
                "name": agent_id,
                "enabled": cb.isChecked(),
                "params": agent_params_map.get(agent_id, {}),
            })

        return {
            "system": {
                "mode": "live" if self.mode_live.isChecked() else "paper",
                "log_level": "INFO",
                "timezone": "Europe/Moscow",
                "web_dashboard": self.dashboard_check.isChecked(),
                "voice_alerts": self.voice_check.isChecked(),
            },
            "quik": {
                "host": self._v("quik_host") or "127.0.0.1",
                "port": self._i("quik_port") or 34130,
                "reconnect_interval_sec": self._i("quik_reconnect") or 5,
                "batch_window_ms": self._i("quik_batch") or 100,
                "max_requests_per_second": self._i("quik_rps") or 50,
            },
            "broker": {
                "name": self._get_selected_broker(),
                "account_id": self._v("broker_account"),
                "client_code": self._v("broker_client"),
                "tinkoff_token": self._v("tinkoff_token"),
                "tinkoff_sandbox": (hasattr(self, "tinkoff_sandbox")
                                    and self.tinkoff_sandbox.isChecked()),
                "alor_token": self._v("alor_token"),
                "alor_refresh_token": self._v("alor_refresh"),
                "finam_token": self._v("finam_token"),
                "finam_client_id": self._v("finam_client_id"),
            },
            "commissions": {
                "stocks": {
                    "exchange_fee_pct": self._f("comm_stock_exchange"),
                    "broker_fee_pct": self._f("comm_stock_broker"),
                    "clearing_fee_pct": self._f("comm_stock_clearing"),
                },
                "futures": {
                    "exchange_fee_per_contract": self._f("comm_fut_exchange"),
                    "broker_fee_per_contract": self._f("comm_fut_broker"),
                    "clearing_fee_per_contract": self._f("comm_fut_clearing"),
                },
                "bonds": {
                    "exchange_fee_pct": 0.01,
                    "broker_fee_pct": 0.06,
                },
            },
            "risk": {
                "max_drawdown_pct": self._f("risk_drawdown"),
                "max_position_pct": self._f("risk_position"),
                "max_daily_loss_pct": self._f("risk_daily_loss"),
                "max_correlation": self._f("risk_correlation"),
                "max_open_positions": self._i("risk_max_pos"),
                "stop_loss_default_pct": self._f("risk_sl"),
            },
            "agents": agents_list,
            "telegram": {
                "token": self._v("tg_token"),
                "chat_id": self._v("tg_chat_id"),
                "report_interval_minutes": self._i("tg_interval"),
            },
            "ai": {
                "provider": "ollama",
                "model": self._v("ai_model"),
                "base_url": self._v("ai_url"),
                "temperature": self._f("ai_temp"),
            },
            "ml": {
                "retrain_interval_hours": self._i("ml_retrain"),
                "min_samples": self._i("ml_samples"),
                "features_window": self._i("ml_window"),
            },
            "database": {
                "url": "sqlite+aiosqlite:///hedge_fund.db",
            },
            "safety": {
                "training_period_days": int(self.training_days.text() or 14),
                "daily_loss_lock_enabled": self.daily_lock.isChecked(),
                "large_trade_threshold_rub": int(self.trade_threshold.text() or 50000),
                "pin_required_for_live": self.pin_required.isChecked(),
                "auto_backup_enabled": self.auto_backup.isChecked(),
                "risk_profile": next(
                    (k for k, rb in self.risk_profile_buttons.items() if rb.isChecked()),
                    "moderate",
                ),
            },
            "curator": {
                "enabled": self.curator_enabled.isChecked(),
                "token": self.curator_token.text().strip(),
                "chat_id": self.curator_chat_id.text().strip(),
            },
            "instruments": {
                "stocks": stocks_list,
                "futures": futures_list,
            },
        }

    def _on_save(self) -> None:
        cfg = self._collect_config()
        _save_config(cfg)
        self.config = cfg
        QMessageBox.information(self, t("msg.saved_title"), t("msg.saved"))

    def _on_run(self) -> None:
        cfg = self._collect_config()
        token = cfg["telegram"]["token"]
        if not token or token == "YOUR_TOKEN":
            reply = QMessageBox.question(
                self, "Telegram",
                t("msg.no_telegram"),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.No:
                return

        account = cfg["broker"]["account_id"]
        if cfg["system"]["mode"] == "live" and (not account or account == "YOUR_ACCOUNT_ID"):
            QMessageBox.critical(self, t("msg.error"), t("msg.no_account"))
            return

        if cfg["system"]["mode"] == "live":
            # PIN check
            if cfg.get("safety", {}).get("pin_required_for_live", True):
                try:
                    from hedge_fund.core.pin_protection import PinProtection
                    pp = PinProtection()
                    if pp.has_pin() and not PinProtection.show_pin_verify_dialog(self):
                        return
                except Exception:
                    pass
            # Risk disclaimer
            try:
                from hedge_fund.core.training_mode import TrainingMode
                if not TrainingMode.show_risk_disclaimer_dialog(self):
                    return
            except Exception:
                pass

        _save_config(cfg)
        self.config = cfg
        self.result = "run"
        self.close()

    def _on_cancel(self) -> None:
        self.result = None
        self.close()

    def _test_telegram(self) -> None:
        token = self._v("tg_token")
        chat_id = self._v("tg_chat_id")
        if not token or not chat_id:
            self.tg_status.setText(t("telegram.fill_fields"))
            self.tg_status.setStyleSheet(f"color: {C['crimson_bright']}; font-size: 9pt;")
            return
        self.tg_status.setText(t("telegram.checking"))
        self.tg_status.setStyleSheet(f"color: {C['ivory_dim']}; font-size: 9pt;")
        t = _TestTelegramThread(token, chat_id)
        t.result.connect(self._on_tg_result)
        self._threads.append(t)
        t.start()

    def _on_tg_result(self, msg: str) -> None:
        color = C['emerald'] if msg.startswith("✓") else C['crimson_bright']
        self.tg_status.setText(msg)
        self.tg_status.setStyleSheet(f"color: {color}; font-size: 9pt;")

    def _test_ollama(self) -> None:
        url = self._v("ai_url")
        self.ollama_status.setText(t("ai.checking"))
        self.ollama_status.setStyleSheet(f"color: {C['ivory_dim']}; font-size: 9pt;")
        t = _TestOllamaThread(url)
        t.result.connect(self._on_ollama_result)
        self._threads.append(t)
        t.start()

    def _on_ollama_result(self, msg: str) -> None:
        color = C['emerald'] if msg.startswith("✓") else C['crimson_bright']
        self.ollama_status.setText(msg)
        self.ollama_status.setStyleSheet(f"color: {color}; font-size: 9pt;")


# ── Public API ────────────────────────────────────────────────

def launch_setup() -> tuple[dict[str, Any] | None, str | None]:
    """Show the setup GUI. Returns (config, action) where action is 'run' or None."""
    app = QApplication.instance() or QApplication(sys.argv)
    win = SetupWindow()
    win.show()
    app.exec()
    if win.result == "run":
        return win.config, "run"
    return None, None


if __name__ == "__main__":
    config, action = launch_setup()
    if action == "run":
        print("Config saved, launching system...")
        from hedge_fund.main import main as run_main
        sys.argv = ["hedge_fund", "--mode", config["system"]["mode"]]
        run_main()
    else:
        print("Setup cancelled.")
