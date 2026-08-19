"""
Training Mode — enforces a paper-trading cool-down period before live trading.

New users are encouraged to stay in paper mode for at least 14 days.
Switching to live requires explicit risk-disclaimer acceptance.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from PyQt6.QtWidgets import QMessageBox, QWidget

from ..utils.logger import get_logger

logger = get_logger("core.training_mode")

_CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"
_RISK_FILE = _CONFIG_DIR / "risk_accepted.json"

COLORS = {
    "bg_void": "#0A0A0F", "bg_dark": "#0D0D14", "bg_card": "#13131F",
    "gold": "#D4AF37", "gold_light": "#F0D060", "gold_dim": "#8B7424",
    "crimson": "#8B0000", "crimson_bright": "#DC143C",
    "ivory": "#FAEBD7", "ivory_dim": "#B8A88A",
    "obsidian": "#1A1A2E", "emerald": "#50C878", "bronze": "#CD7F32",
}


class TrainingMode:
    """Tracks paper-trading training period and risk-disclaimer acceptance."""

    def __init__(
        self,
        start_date: Optional[datetime] = None,
        training_period_days: int = 14,
    ) -> None:
        self.start_date: datetime = start_date or datetime.now(timezone.utc)
        self.training_period_days: int = training_period_days
        self.is_training_complete: bool = False
        logger.info(
            "TrainingMode initialised — start={}, period={}d",
            self.start_date.isoformat(),
            self.training_period_days,
        )

    # ------------------------------------------------------------------
    def is_in_training(self) -> bool:
        """Return *True* while inside the training window."""
        elapsed = (datetime.now(timezone.utc) - self.start_date).days
        in_training = elapsed < self.training_period_days
        if not in_training:
            self.is_training_complete = True
        return in_training

    def can_switch_to_live(self) -> bool:
        """Users can always switch — but a warning is shown."""
        return True

    def get_days_remaining(self) -> int:
        """Days left in the training window (≥ 0)."""
        remaining = self.training_period_days - (datetime.now(timezone.utc) - self.start_date).days
        return max(remaining, 0)

    # ------------------------------------------------------------------
    def accept_risk_disclaimer(self) -> None:
        """Persist risk-disclaimer acceptance with a UTC timestamp."""
        _CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        payload = {
            "accepted": True,
            "accepted_at": datetime.now(timezone.utc).isoformat(),
        }
        _RISK_FILE.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        logger.info("Risk disclaimer accepted and saved to {}", _RISK_FILE)

    @staticmethod
    def has_accepted_risk() -> bool:
        """Check whether the user previously accepted the disclaimer."""
        if not _RISK_FILE.exists():
            return False
        try:
            data = json.loads(_RISK_FILE.read_text(encoding="utf-8"))
            return bool(data.get("accepted"))
        except (json.JSONDecodeError, OSError):
            return False

    # ------------------------------------------------------------------
    @staticmethod
    def show_risk_disclaimer_dialog(parent: Optional[QWidget] = None) -> bool:
        """Show a serious Russian-language risk-disclaimer dialog.

        Returns *True* if the user accepts all risks.
        """
        text = (
            "<div style='font-family: Segoe UI; color: {ivory};'>"
            "<h2 style='color: {crimson_bright}; text-align: center;'>"
            "⚠ ПРЕДУПРЕЖДЕНИЕ О РИСКАХ ⚠</h2>"
            "<p>Торговля на финансовых рынках сопряжена с <b>существенными рисками</b> "
            "потери капитала. Прошлые результаты <b>не гарантируют</b> будущих доходов.</p>"
            "<p>В соответствии с Федеральным законом № 39-ФЗ «О рынке ценных бумаг» "
            "и нормативными актами Банка России, Вы подтверждаете, что:</p>"
            "<ul>"
            "<li>Осознаёте все риски, связанные с торговлей ценными бумагами и "
            "производными финансовыми инструментами;</li>"
            "<li>Принимаете на себя <b>полную ответственность</b> за все торговые "
            "решения и возможные убытки;</li>"
            "<li>Используете данное программное обеспечение <b>на свой страх и риск</b>;</li>"
            "<li>Разработчики программы <b>не несут ответственности</b> за финансовые "
            "потери любого размера.</li>"
            "</ul>"
            "<p style='color: {gold};'><b>Рекомендуется начать с режима бумажной торговли "
            "(Paper Trading) минимум на 14 дней.</b></p>"
            "</div>"
        ).format(**COLORS)

        box = QMessageBox(parent)
        box.setWindowTitle("Принятие рисков")
        box.setIcon(QMessageBox.Icon.Warning)
        box.setTextFormat(box.textFormat().RichText if hasattr(box.textFormat(), "RichText") else 1)
        box.setText(text)
        box.setStyleSheet(
            f"QMessageBox {{ background-color: {COLORS['bg_dark']}; }}"
            f"QLabel {{ color: {COLORS['ivory']}; }}"
            f"QPushButton {{ background-color: {COLORS['bg_card']}; color: {COLORS['gold']}; "
            f"border: 1px solid {COLORS['gold_dim']}; padding: 6px 20px; font-weight: bold; }}"
            f"QPushButton:hover {{ background-color: {COLORS['obsidian']}; }}"
        )
        accept_btn = box.addButton("Принять риски", QMessageBox.ButtonRole.AcceptRole)
        box.addButton("Отмена", QMessageBox.ButtonRole.RejectRole)
        box.exec()
        return box.clickedButton() == accept_btn

    @staticmethod
    def show_training_recommendation_dialog(
        parent: Optional[QWidget] = None,
        days_remaining: int = 0,
    ) -> bool:
        """Recommend staying in paper mode; allow override.

        Returns *True* if the user chooses to proceed to live anyway.
        """
        text = (
            f"<div style='font-family: Segoe UI; color: {COLORS['ivory']};'>"
            f"<h3 style='color: {COLORS['gold']};'>⏳ Рекомендация: режим Paper Trading</h3>"
            f"<p>До завершения тренировочного периода осталось "
            f"<b style='color: {COLORS['gold_light']};'>{days_remaining}</b> дн.</p>"
            f"<p>Настоятельно рекомендуем дождаться окончания тренировочного периода "
            f"перед переходом на реальную торговлю.</p>"
            f"<p style='color: {COLORS['ivory_dim']};'>Вы можете перейти сейчас, "
            f"но это увеличивает риск.</p></div>"
        )
        box = QMessageBox(parent)
        box.setWindowTitle("Тренировочный период")
        box.setIcon(QMessageBox.Icon.Information)
        box.setText(text)
        box.setStyleSheet(
            f"QMessageBox {{ background-color: {COLORS['bg_dark']}; }}"
            f"QLabel {{ color: {COLORS['ivory']}; }}"
            f"QPushButton {{ background-color: {COLORS['bg_card']}; color: {COLORS['gold']}; "
            f"border: 1px solid {COLORS['gold_dim']}; padding: 6px 20px; font-weight: bold; }}"
            f"QPushButton:hover {{ background-color: {COLORS['obsidian']}; }}"
        )
        proceed_btn = box.addButton("Перейти на Live", QMessageBox.ButtonRole.AcceptRole)
        box.addButton("Остаться в Paper", QMessageBox.ButtonRole.RejectRole)
        box.exec()
        return box.clickedButton() == proceed_btn
