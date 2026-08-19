"""
PIN Protection — guards live-mode access and emergency-stop reset with a hashed PIN.

PINs are 4-6 digits, hashed with SHA-256, and stored in ``config/pin.json``.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Optional

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QLineEdit, QPushButton, QWidget, QMessageBox,
)
from PyQt6.QtCore import Qt

from ..utils.logger import get_logger

logger = get_logger("core.pin_protection")

_CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"
_PIN_FILE = _CONFIG_DIR / "pin.json"

COLORS = {
    "bg_void": "#0A0A0F", "bg_dark": "#0D0D14", "bg_card": "#13131F",
    "gold": "#D4AF37", "gold_light": "#F0D060", "gold_dim": "#8B7424",
    "crimson": "#8B0000", "crimson_bright": "#DC143C",
    "ivory": "#FAEBD7", "ivory_dim": "#B8A88A",
    "obsidian": "#1A1A2E", "emerald": "#50C878", "bronze": "#CD7F32",
}

_DIALOG_STYLE = (
    f"QDialog {{ background-color: {COLORS['bg_dark']}; "
    f"border: 2px solid {COLORS['gold_dim']}; }}"
    f"QLabel {{ color: {COLORS['ivory']}; font-family: 'Segoe UI'; border: none; }}"
    f"QLineEdit {{ background-color: {COLORS['bg_card']}; color: {COLORS['gold_light']}; "
    f"border: 1px solid {COLORS['gold_dim']}; padding: 8px; font-size: 20px; "
    f"font-family: Consolas; letter-spacing: 8px; }}"
)

_BTN_STYLE = (
    f"QPushButton {{ background-color: {COLORS['bg_card']}; color: {COLORS['gold']}; "
    f"border: 1px solid {COLORS['gold_dim']}; padding: 8px 24px; "
    f"font-weight: bold; font-size: 13px; }}"
    f"QPushButton:hover {{ background-color: {COLORS['obsidian']}; }}"
    f"QPushButton:disabled {{ color: {COLORS['ivory_dim']}; }}"
)


def _hash_pin(pin: str) -> str:
    return hashlib.sha256(pin.encode("utf-8")).hexdigest()


class PinProtection:
    """Manage a hashed PIN for authorising sensitive operations."""

    def set_pin(self, pin: str) -> None:
        """Hash and persist a new PIN (4-6 digits)."""
        if not (pin.isdigit() and 4 <= len(pin) <= 6):
            raise ValueError("PIN must be 4-6 digits")
        _CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        payload = {"pin_hash": _hash_pin(pin)}
        _PIN_FILE.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        logger.info("PIN set and saved to {}", _PIN_FILE)

    def verify_pin(self, pin: str) -> bool:
        """Return *True* if *pin* matches the stored hash."""
        if not _PIN_FILE.exists():
            return False
        try:
            data = json.loads(_PIN_FILE.read_text(encoding="utf-8"))
            return data.get("pin_hash") == _hash_pin(pin)
        except (json.JSONDecodeError, OSError):
            return False

    def has_pin(self) -> bool:
        """Return *True* if a PIN has been configured."""
        return _PIN_FILE.exists()

    # ------------------------------------------------------------------
    @staticmethod
    def show_pin_setup_dialog(parent: Optional[QWidget] = None) -> Optional[str]:
        """Show a dialog to create a new 4-6 digit PIN.

        Returns the chosen PIN string, or *None* if cancelled.
        """
        dlg = QDialog(parent)
        dlg.setWindowTitle("Установка PIN-кода")
        dlg.setMinimumWidth(360)
        dlg.setStyleSheet(_DIALOG_STYLE)

        layout = QVBoxLayout(dlg)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(12)

        title = QLabel("⚜ Установите PIN-код (4–6 цифр)")
        title.setStyleSheet(f"font-size: 15px; font-weight: bold; color: {COLORS['gold']};")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        pin_input = QLineEdit()
        pin_input.setMaxLength(6)
        pin_input.setEchoMode(QLineEdit.EchoMode.Password)
        pin_input.setAlignment(Qt.AlignmentFlag.AlignCenter)
        pin_input.setPlaceholderText("●●●●")
        layout.addWidget(pin_input)

        confirm_input = QLineEdit()
        confirm_input.setMaxLength(6)
        confirm_input.setEchoMode(QLineEdit.EchoMode.Password)
        confirm_input.setAlignment(Qt.AlignmentFlag.AlignCenter)
        confirm_input.setPlaceholderText("Повторите PIN")
        layout.addWidget(confirm_input)

        ok_btn = QPushButton("Сохранить")
        ok_btn.setStyleSheet(_BTN_STYLE)
        ok_btn.setEnabled(False)
        layout.addWidget(ok_btn)

        _result: list[Optional[str]] = [None]

        def _validate() -> None:
            p, c = pin_input.text(), confirm_input.text()
            ok_btn.setEnabled(p.isdigit() and 4 <= len(p) <= 6 and p == c)

        pin_input.textChanged.connect(lambda: _validate())
        confirm_input.textChanged.connect(lambda: _validate())

        def _accept() -> None:
            _result[0] = pin_input.text()
            dlg.accept()

        ok_btn.clicked.connect(_accept)
        dlg.exec()
        return _result[0]

    @staticmethod
    def show_pin_verify_dialog(parent: Optional[QWidget] = None) -> bool:
        """Show a dialog to enter and verify the PIN.

        Returns *True* if the entered PIN is correct.
        """
        dlg = QDialog(parent)
        dlg.setWindowTitle("Проверка PIN-кода")
        dlg.setMinimumWidth(340)
        dlg.setStyleSheet(_DIALOG_STYLE)

        layout = QVBoxLayout(dlg)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(12)

        title = QLabel("⚜ Введите PIN-код")
        title.setStyleSheet(f"font-size: 15px; font-weight: bold; color: {COLORS['gold']};")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        pin_input = QLineEdit()
        pin_input.setMaxLength(6)
        pin_input.setEchoMode(QLineEdit.EchoMode.Password)
        pin_input.setAlignment(Qt.AlignmentFlag.AlignCenter)
        pin_input.setPlaceholderText("●●●●")
        layout.addWidget(pin_input)

        status_lbl = QLabel("")
        status_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        status_lbl.setStyleSheet(f"color: {COLORS['crimson_bright']}; font-size: 12px;")
        layout.addWidget(status_lbl)

        ok_btn = QPushButton("Подтвердить")
        ok_btn.setStyleSheet(_BTN_STYLE)
        layout.addWidget(ok_btn)

        prot = PinProtection()
        _success = [False]

        def _check() -> None:
            if prot.verify_pin(pin_input.text()):
                _success[0] = True
                dlg.accept()
            else:
                status_lbl.setText("Неверный PIN-код")
                pin_input.clear()

        ok_btn.clicked.connect(_check)
        pin_input.returnPressed.connect(_check)
        dlg.exec()
        return _success[0]
