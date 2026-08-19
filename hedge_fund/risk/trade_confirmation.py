"""
Large Trade Confirmation — requires explicit user approval for trades above a threshold.

Shows a styled PyQt6 dialog with trade details, estimated commission, and risk assessment.
"""
from __future__ import annotations

from typing import Optional

from PyQt6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QWidget
from PyQt6.QtCore import Qt

from ..utils.logger import get_logger

logger = get_logger("risk.trade_confirmation")

COLORS = {
    "bg_void": "#0A0A0F", "bg_dark": "#0D0D14", "bg_card": "#13131F",
    "gold": "#D4AF37", "gold_light": "#F0D060", "gold_dim": "#8B7424",
    "crimson": "#8B0000", "crimson_bright": "#DC143C",
    "ivory": "#FAEBD7", "ivory_dim": "#B8A88A",
    "obsidian": "#1A1A2E", "emerald": "#50C878", "bronze": "#CD7F32",
}


class TradeConfirmation:
    """Gate-keeps large trades that exceed *threshold_rub*."""

    def __init__(self, threshold_rub: float = 50_000) -> None:
        self.threshold_rub: float = threshold_rub

    def needs_confirmation(self, trade_value: float) -> bool:
        """Return *True* when the trade value warrants user confirmation."""
        return abs(trade_value) >= self.threshold_rub

    @staticmethod
    def show_confirmation_dialog(
        parent: Optional[QWidget],
        ticker: str,
        side: str,
        qty: int,
        price: float,
        total: float,
        risk_pct: float,
    ) -> bool:
        """Show an Art-Deco-styled confirmation dialog in Russian.

        Returns *True* if the user confirms the trade.
        """
        commission_est = total * 0.0005  # ~0.05% MOEX typical

        risk_color = COLORS["emerald"] if risk_pct < 3.0 else (
            COLORS["gold"] if risk_pct < 7.0 else COLORS["crimson_bright"]
        )

        dlg = QDialog(parent)
        dlg.setWindowTitle("Подтверждение сделки")
        dlg.setMinimumWidth(420)
        dlg.setStyleSheet(
            f"QDialog {{ background-color: {COLORS['bg_dark']}; "
            f"border: 2px solid {COLORS['gold_dim']}; }}"
            f"QLabel {{ color: {COLORS['ivory']}; font-family: 'Segoe UI'; }}"
        )

        layout = QVBoxLayout(dlg)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(10)

        title = QLabel(f"⚜ Крупная сделка — {ticker}")
        title.setStyleSheet(
            f"font-size: 16px; font-weight: bold; color: {COLORS['gold']};"
        )
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        sep = QLabel("─" * 50)
        sep.setStyleSheet(f"color: {COLORS['gold_dim']}; font-size: 10px;")
        sep.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(sep)

        rows = [
            ("Тикер:", ticker),
            ("Направление:", "ПОКУПКА" if side.upper() in ("BUY", "LONG") else "ПРОДАЖА"),
            ("Количество:", f"{qty:,} шт."),
            ("Цена:", f"{price:,.2f} ₽"),
            ("Сумма:", f"{total:,.2f} ₽"),
            ("Комиссия (≈):", f"{commission_est:,.2f} ₽"),
        ]
        for label_text, value_text in rows:
            row = QHBoxLayout()
            lbl = QLabel(label_text)
            lbl.setStyleSheet(f"color: {COLORS['ivory_dim']}; font-size: 13px;")
            val = QLabel(str(value_text))
            val.setStyleSheet(f"color: {COLORS['ivory']}; font-size: 13px; font-weight: bold;")
            val.setAlignment(Qt.AlignmentFlag.AlignRight)
            row.addWidget(lbl)
            row.addWidget(val)
            layout.addLayout(row)

        risk_lbl = QLabel(f"Риск на портфель: {risk_pct:.1f}%")
        risk_lbl.setStyleSheet(
            f"color: {risk_color}; font-size: 14px; font-weight: bold; margin-top: 6px;"
        )
        risk_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(risk_lbl)

        btn_style = (
            f"QPushButton {{ background-color: {COLORS['bg_card']}; color: {COLORS['gold']}; "
            f"border: 1px solid {COLORS['gold_dim']}; padding: 8px 24px; "
            f"font-weight: bold; font-size: 13px; }}"
            f"QPushButton:hover {{ background-color: {COLORS['obsidian']}; }}"
        )
        cancel_style = (
            f"QPushButton {{ background-color: {COLORS['bg_card']}; color: {COLORS['crimson_bright']}; "
            f"border: 1px solid {COLORS['crimson']}; padding: 8px 24px; "
            f"font-weight: bold; font-size: 13px; }}"
            f"QPushButton:hover {{ background-color: {COLORS['crimson']}; color: {COLORS['ivory']}; }}"
        )

        btn_row = QHBoxLayout()
        confirm_btn = QPushButton("Подтвердить")
        confirm_btn.setStyleSheet(btn_style)
        confirm_btn.clicked.connect(dlg.accept)
        cancel_btn = QPushButton("Отменить")
        cancel_btn.setStyleSheet(cancel_style)
        cancel_btn.clicked.connect(dlg.reject)
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(confirm_btn)
        layout.addLayout(btn_row)

        logger.info(
            "Trade confirmation dialog shown — {} {} x{} @ {:.2f} = {:.2f}",
            side, ticker, qty, price, total,
        )
        return dlg.exec() == QDialog.DialogCode.Accepted
