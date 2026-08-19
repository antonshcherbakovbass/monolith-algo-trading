"""
Emergency Stop — kills all live trading and closes positions immediately.

Activation requires typing "СТОП" in a confirmation dialog.
Reset requires a valid PIN (see pin_protection module).
"""
from __future__ import annotations

import asyncio
from typing import Callable, Optional

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QLineEdit, QPushButton, QWidget,
)
from PyQt6.QtCore import Qt

from ..utils.logger import get_logger

logger = get_logger("core.emergency_stop")

COLORS = {
    "bg_void": "#0A0A0F", "bg_dark": "#0D0D14", "bg_card": "#13131F",
    "gold": "#D4AF37", "gold_light": "#F0D060", "gold_dim": "#8B7424",
    "crimson": "#8B0000", "crimson_bright": "#DC143C",
    "ivory": "#FAEBD7", "ivory_dim": "#B8A88A",
    "obsidian": "#1A1A2E", "emerald": "#50C878", "bronze": "#CD7F32",
}


class EmergencyStop:
    """Global kill-switch that closes all positions via a callback."""

    def __init__(self, close_all_callback: Callable[[], None]) -> None:
        self._close_all = close_all_callback
        self._active: bool = False

    def activate(self) -> None:
        """Activate emergency stop — calls the close-all-positions callback."""
        if self._active:
            logger.warning("Emergency stop already active")
            return
        self._active = True
        logger.critical("🚨 EMERGENCY STOP ACTIVATED — closing all positions")
        result = self._close_all()
        if asyncio.iscoroutine(result):
            asyncio.create_task(result)

    def is_active(self) -> bool:
        return self._active

    def reset(self, pin: str, verify_fn: Callable[[str], bool]) -> bool:
        """Reset the emergency stop. Requires valid PIN verification.

        *verify_fn* should be ``PinProtection.verify_pin``.
        Returns *True* if reset was successful.
        """
        if verify_fn(pin):
            self._active = False
            logger.info("Emergency stop reset by authorised PIN")
            return True
        logger.warning("Emergency stop reset DENIED — invalid PIN")
        return False

    @staticmethod
    def show_emergency_dialog(parent: Optional[QWidget] = None) -> bool:
        """Show a large red confirmation dialog requiring the user to type СТОП.

        Returns *True* if the user confirmed the emergency stop.
        """
        dlg = QDialog(parent)
        dlg.setWindowTitle("АВАРИЙНАЯ ОСТАНОВКА")
        dlg.setMinimumSize(480, 340)
        dlg.setStyleSheet(
            f"QDialog {{ background-color: {COLORS['bg_void']}; "
            f"border: 3px solid {COLORS['crimson_bright']}; }}"
        )

        layout = QVBoxLayout(dlg)
        layout.setContentsMargins(30, 24, 30, 24)
        layout.setSpacing(16)

        icon_lbl = QLabel("🚨")
        icon_lbl.setStyleSheet("font-size: 48px; border: none;")
        icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(icon_lbl)

        title = QLabel("АВАРИЙНАЯ ОСТАНОВКА ТОРГОВЛИ")
        title.setStyleSheet(
            f"font-size: 20px; font-weight: bold; color: {COLORS['crimson_bright']}; "
            "border: none;"
        )
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        warn = QLabel(
            "Все открытые позиции будут НЕМЕДЛЕННО закрыты по рыночной цене.\n"
            "Это действие необратимо.\n\n"
            "Для подтверждения введите: СТОП"
        )
        warn.setStyleSheet(
            f"color: {COLORS['ivory']}; font-size: 14px; border: none;"
        )
        warn.setAlignment(Qt.AlignmentFlag.AlignCenter)
        warn.setWordWrap(True)
        layout.addWidget(warn)

        line_edit = QLineEdit()
        line_edit.setPlaceholderText("Введите СТОП")
        line_edit.setAlignment(Qt.AlignmentFlag.AlignCenter)
        line_edit.setStyleSheet(
            f"background-color: {COLORS['bg_card']}; color: {COLORS['crimson_bright']}; "
            f"border: 2px solid {COLORS['crimson']}; font-size: 18px; "
            f"font-weight: bold; padding: 8px; font-family: Consolas;"
        )
        layout.addWidget(line_edit)

        btn = QPushButton("АКТИВИРОВАТЬ АВАРИЙНУЮ ОСТАНОВКУ")
        btn.setEnabled(False)
        btn.setStyleSheet(
            f"QPushButton {{ background-color: {COLORS['crimson']}; color: {COLORS['ivory']}; "
            f"border: 2px solid {COLORS['crimson_bright']}; padding: 12px; "
            f"font-size: 14px; font-weight: bold; }}"
            f"QPushButton:hover {{ background-color: {COLORS['crimson_bright']}; }}"
            f"QPushButton:disabled {{ background-color: {COLORS['bg_card']}; "
            f"color: {COLORS['ivory_dim']}; border-color: {COLORS['gold_dim']}; }}"
        )
        btn.clicked.connect(dlg.accept)
        layout.addWidget(btn)

        line_edit.textChanged.connect(
            lambda t: btn.setEnabled(t.strip() == "СТОП")
        )

        cancel_btn = QPushButton("Отмена")
        cancel_btn.setStyleSheet(
            f"QPushButton {{ background-color: {COLORS['bg_card']}; color: {COLORS['gold']}; "
            f"border: 1px solid {COLORS['gold_dim']}; padding: 8px 20px; }}"
            f"QPushButton:hover {{ background-color: {COLORS['obsidian']}; }}"
        )
        cancel_btn.clicked.connect(dlg.reject)
        layout.addWidget(cancel_btn)

        result = dlg.exec() == QDialog.DialogCode.Accepted
        if result:
            logger.critical("Emergency stop CONFIRMED via dialog")
        return result
