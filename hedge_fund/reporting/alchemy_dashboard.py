"""
Alchemy Dashboard — Dark Art Deco Trading Monitor.
Run: python -m hedge_fund.reporting.alchemy_dashboard
"""
import sys
import random
from datetime import datetime, timezone, timedelta

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout,
    QHBoxLayout, QLabel, QTableWidget, QTableWidgetItem, QFrame,
    QScrollArea, QHeaderView, QAbstractItemView, QTextEdit,
    QSizePolicy, QPushButton, QMessageBox,
)
from PyQt6.QtCore import Qt, QTimer, QRectF
from PyQt6.QtGui import QPainter, QPen, QColor, QFont, QBrush, QLinearGradient, QPixmap

from hedge_fund.core.themes import ThemeManager
from hedge_fund.core.runtime_state import RuntimeState
from hedge_fund.core.styled_widgets import (
    GoldBorderFrame, TexturedCard, AgentCard,
    SacredSeparator, DualismHeader, IconLabel,
    NYArtDecoBackground,
)

COLORS = {
    "bg_void": "#0A0A0F",
    "bg_dark": "#0D0D14",
    "bg_card": "#13131F",
    "bg_card_hover": "#1A1A2A",
    "gold": "#D4AF37",
    "gold_light": "#F0D060",
    "gold_dim": "#8B7424",
    "crimson": "#8B0000",
    "crimson_bright": "#DC143C",
    "crimson_dim": "#4A0010",
    "ivory": "#FAEBD7",
    "ivory_dim": "#B8A88A",
    "obsidian": "#1A1A2E",
    "emerald": "#2D6B4F",
    "emerald_bright": "#50C878",
    "silver": "#C0C0C0",
    "bronze": "#CD7F32",
}

TICKERS = ["SBER", "GAZP", "LKOH", "YNDX", "GMKN", "NVTK", "ROSN", "MGNT", "VTBR", "POLY", "ALRS", "TATN"]

AGENTS = [
    ("⚜", "ORCHESTRATOR", "The Sovereign"),
    ("⚡", "SCALPING", "The Lightning"),
    ("☀", "DAY TRADING", "The Sun Chariot"),
    ("Ω", "LONG TERM", "The Eternal Temple"),
    ("☿", "NEWS", "The Mercury Herald"),
    ("⚖", "RISK SHIELD", "Scales of Judgement"),
    ("◎", "QUANT", "The All-Seeing Eye"),
    ("☊", "HEDGING", "The Celestial Shield"),
    ("⚙", "SRE", "The Clockwork Guardian"),
]

MOSCOW_TZ = timezone(timedelta(hours=3))

def _build_stylesheet() -> str:
    if ThemeManager._current_theme == "divine_dualism":
        return f"""
QMainWindow {{
    background-color: #0A0A0F;
}}
QWidget {{
    color: {COLORS['ivory']};
    font-family: "Cinzel", "Marcellus", "Georgia", "Segoe UI";
    font-size: 12px;
}}
QFrame {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #14141E, stop:0.02 #10101A, stop:0.98 #0C0C14, stop:1 #080810);
    border: 1px solid {COLORS['gold_dim']};
    border-radius: 2px;
}}
QLabel {{
    border: none;
    background: transparent;
}}
QTableWidget {{
    background-color: #0C0C14;
    alternate-background-color: #10101A;
    border: 1px solid {COLORS['gold_dim']};
    gridline-color: #1A1A2A;
    font-family: "Consolas";
    font-size: 11px;
    selection-background-color: {COLORS['obsidian']};
}}
QTableWidget::item {{
    padding: 4px 8px;
    border: none;
}}
QHeaderView::section {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #D4AF37, stop:0.4 #B8960C, stop:0.41 #8B7424, stop:1 #5A4A1E);
    color: #0D0D0D;
    font-weight: bold;
    font-family: "Cinzel", "Georgia", "Segoe UI";
    font-size: 11px;
    padding: 6px 8px;
    border: none;
    border-bottom: 2px solid #FFD700;
    letter-spacing: 1px;
}}
QTextEdit {{
    background-color: #0A0A0F;
    border: 1px solid {COLORS['gold_dim']};
    border-radius: 2px;
    font-family: "Consolas";
    font-size: 11px;
    color: {COLORS['ivory_dim']};
}}
QPushButton {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #1E1E2A, stop:0.3 #16161E, stop:0.31 #0E0E14, stop:1 #0A0A0F);
    color: #D4AF37;
    border: 1px solid #8B7424;
    padding: 8px 18px;
    font-family: "Cinzel", "Georgia", "Segoe UI";
    letter-spacing: 1px;
}}
QPushButton:hover {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #D4AF37, stop:0.3 #FFD700, stop:0.31 #D4AF37, stop:1 #B8960C);
    color: #0D0D0D;
    border: 1px solid #FFD700;
}}
QScrollBar:vertical {{
    background: #0A0A0F;
    width: 10px;
    border: none;
}}
QScrollBar::handle:vertical {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #5A4A1E, stop:0.5 #D4AF37, stop:1 #5A4A1E);
    min-height: 30px;
    border-radius: 0px;
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}
QScrollBar:horizontal {{
    background: #0A0A0F;
    height: 10px;
}}
QScrollBar::handle:horizontal {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #5A4A1E, stop:0.5 #D4AF37, stop:1 #5A4A1E);
    min-width: 30px;
    border-radius: 0px;
}}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
    width: 0;
}}
"""
    return f"""
QMainWindow {{
    background-color: {COLORS['bg_void']};
}}
QWidget {{
    color: {COLORS['ivory']};
    font-family: "Segoe UI";
    font-size: 12px;
}}
QFrame {{
    background-color: {COLORS['bg_card']};
    border: 1px solid {COLORS['gold_dim']};
    border-radius: 2px;
}}
QLabel {{
    border: none;
    background: transparent;
}}
QTableWidget {{
    background-color: {COLORS['bg_card']};
    alternate-background-color: {COLORS['bg_dark']};
    border: 1px solid {COLORS['gold_dim']};
    gridline-color: transparent;
    font-family: "Consolas";
    font-size: 11px;
    selection-background-color: {COLORS['obsidian']};
}}
QTableWidget::item {{
    padding: 4px 8px;
    border: none;
}}
QHeaderView::section {{
    background-color: {COLORS['gold_dim']};
    color: {COLORS['bg_void']};
    font-weight: bold;
    font-family: "Segoe UI";
    font-size: 11px;
    padding: 5px 8px;
    border: none;
    border-bottom: 2px solid {COLORS['gold']};
}}
QTextEdit {{
    background-color: {COLORS['bg_dark']};
    border: 1px solid {COLORS['gold_dim']};
    border-radius: 2px;
    font-family: "Consolas";
    font-size: 11px;
    color: {COLORS['ivory_dim']};
}}
QScrollBar:vertical {{
    background: {COLORS['bg_dark']};
    width: 8px;
    margin: 0;
}}
QScrollBar::handle:vertical {{
    background: {COLORS['gold_dim']};
    min-height: 20px;
    border-radius: 4px;
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}
QScrollBar:horizontal {{
    background: {COLORS['bg_dark']};
    height: 8px;
}}
QScrollBar::handle:horizontal {{
    background: {COLORS['gold_dim']};
    min-width: 20px;
    border-radius: 4px;
}}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
    width: 0;
}}
"""

STYLESHEET = _build_stylesheet()


class DecorativeFrame(QFrame):
    """A frame that draws Art Deco corner ornaments and chevron borders."""

    def __init__(self, draw_corners=True, draw_top_chevron=False, parent=None):
        super().__init__(parent)
        self._draw_corners = draw_corners
        self._draw_top_chevron = draw_top_chevron

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        gold = QColor(COLORS["gold"])
        gold_dim = QColor(COLORS["gold_dim"])
        pen = QPen(gold_dim, 1.0)
        painter.setPen(pen)

        w, h = self.width(), self.height()

        if self._draw_corners:
            size = 12
            for cx, cy, sx, sy in [(0, 0, 1, 1), (w, 0, -1, 1), (0, h, 1, -1), (w, h, -1, -1)]:
                painter.setPen(QPen(gold, 1.0))
                painter.drawLine(int(cx), int(cy + 4 * sy), int(cx + size * sx), int(cy + 4 * sy))
                painter.drawLine(int(cx + 4 * sx), int(cy), int(cx + 4 * sx), int(cy + size * sy))
                painter.setPen(QPen(gold_dim, 1.0))
                painter.drawLine(int(cx + 2 * sx), int(cy + 2 * sy), int(cx + 8 * sx), int(cy + 2 * sy))
                painter.drawLine(int(cx + 2 * sx), int(cy + 2 * sy), int(cx + 2 * sx), int(cy + 8 * sy))

        if self._draw_top_chevron:
            painter.setPen(QPen(gold, 1.0))
            mid = w // 2
            y = 2
            for i in range(3):
                offset = i * 20
                painter.drawLine(mid - 6 - offset, y + 3, mid - offset, y)
                painter.drawLine(mid - offset, y, mid + 6 + offset, y + 3) if offset == 0 else None
                painter.drawLine(mid + offset, y, mid + 6 + offset, y + 3)

        painter.end()


class SeparatorLine(QWidget):
    """Draws a horizontal separator with a diamond in the center."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(16)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        gold = QColor(COLORS["gold_dim"])
        painter.setPen(QPen(gold, 1.0))
        w = self.width()
        mid_y = self.height() // 2
        mid_x = w // 2
        painter.drawLine(20, mid_y, mid_x - 8, mid_y)
        painter.drawLine(mid_x + 8, mid_y, w - 20, mid_y)
        painter.setBrush(QBrush(QColor(COLORS["gold"])))
        painter.setPen(Qt.PenStyle.NoPen)
        diamond = [
            (mid_x, mid_y - 4),
            (mid_x + 4, mid_y),
            (mid_x, mid_y + 4),
            (mid_x - 4, mid_y),
        ]
        from PyQt6.QtGui import QPolygon
        from PyQt6.QtCore import QPoint
        painter.drawPolygon(QPolygon([QPoint(x, y) for x, y in diamond]))
        painter.end()


class AlchemyDashboard(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("LUX NOX Capital \u00b7 MONOLITH Terminal")
        self.setMinimumSize(1200, 800)
        self.resize(1280, 850)

        self._init_data()

        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(4)

        main_layout.addWidget(self._build_title_bar())
        main_layout.addWidget(self._build_status_bar())

        body = QHBoxLayout()
        body.setSpacing(6)
        body.addWidget(self._build_left_panel(), stretch=60)
        body.addWidget(self._build_right_panel(), stretch=40)
        main_layout.addLayout(body, stretch=1)

        main_layout.addWidget(self._build_bottom_panel())

        self.setStyleSheet(STYLESHEET)

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._update_data)
        self._timer.start(2000)

    @property
    def _is_divine(self) -> bool:
        return ThemeManager._current_theme == "divine_dualism"

    @property
    def _is_ny_deco(self) -> bool:
        return ThemeManager._current_theme == "ny_art_deco"

    def _init_data(self):
        self._live_mode = False
        live = RuntimeState.read(max_age_sec=15.0)
        if live and self._apply_live_state(live):
            self._live_mode = True
            return
        self._load_demo_data()

    def _apply_live_state(self, state: dict) -> bool:
        try:
            self._mode = state.get("mode", "PAPER")
            self._connected = bool(state.get("connected", False))
            self._portfolio_value = float(state.get("portfolio_value", 0))
            self._daily_pnl = float(state.get("daily_pnl", 0))

            self._positions = []
            for p in state.get("positions", []):
                qty = int(p.get("qty", 0))
                if qty == 0:
                    continue
                side = "LONG" if qty > 0 else "SHORT"
                avg = float(p.get("avg_price", 0))
                pnl = float(p.get("unrealized_pnl", 0))
                current = avg + (pnl / abs(qty)) if qty else avg
                self._positions.append({
                    "ticker": p.get("ticker", "?"),
                    "side": side,
                    "qty": abs(qty),
                    "entry": avg,
                    "current": round(current, 2),
                    "pnl": round(pnl, 2),
                    "agent": "Live",
                })

            self._trades = []
            for t in state.get("trades", [])[-30:]:
                side = str(t.get("side", "BUY")).upper()
                qty = int(t.get("qty", 0))
                price = float(t.get("price", 0))
                self._trades.append({
                    "time": t.get("timestamp", "")[-8:] if t.get("timestamp") else datetime.now(MOSCOW_TZ).strftime("%H:%M:%S"),
                    "ticker": t.get("ticker", "?"),
                    "side": side,
                    "qty": qty,
                    "price": price,
                    "pnl": 0.0,
                })

            self._agent_signals = {a[1]: 0 for a in AGENTS}
            self._agent_pnl = {a[1]: 0.0 for a in AGENTS}
            for agent in state.get("agents", []):
                name = str(agent.get("name", "")).upper().replace(" ", "_")
                for _, agent_key, _ in AGENTS:
                    if agent_key.replace(" ", "_") == name or agent_key.split()[0] in name:
                        self._agent_signals[agent_key] = int(agent.get("signals", 0))
                        break

            self._events = []
            for msg in state.get("events", [])[-20:]:
                ts = datetime.now(MOSCOW_TZ).strftime("%H:%M:%S")
                self._events.append((ts, "⟐", "gold", str(msg)))
            if state.get("daily_loss_locked"):
                ts = datetime.now(MOSCOW_TZ).strftime("%H:%M:%S")
                self._events.append((ts, "⚠", "crimson_bright", "Daily loss lock ACTIVE — trading halted"))
            if state.get("emergency_stop"):
                ts = datetime.now(MOSCOW_TZ).strftime("%H:%M:%S")
                self._events.append((ts, "⛔", "crimson_bright", "EMERGENCY STOP ACTIVE"))
            return True
        except Exception:
            return False

    def _load_demo_data(self):
        self._positions = []
        num = random.randint(8, 12)
        chosen = random.sample(TICKERS, num)
        for ticker in chosen:
            side = random.choice(["LONG", "SHORT"])
            qty = random.randint(1, 500) * 10
            entry = round(random.uniform(80, 5000), 2)
            current = round(entry * random.uniform(0.92, 1.10), 2)
            pnl = round((current - entry) * qty * (1 if side == "LONG" else -1), 2)
            agent = random.choice(["Scalping", "DayTrade", "LongTerm", "Quant", "Hedging"])
            self._positions.append({
                "ticker": ticker, "side": side, "qty": qty,
                "entry": entry, "current": current, "pnl": pnl, "agent": agent,
            })

        self._trades = []
        for _ in range(15):
            self._trades.append(self._random_trade())

        self._portfolio_value = round(random.uniform(5_000_000, 15_000_000), 2)
        self._daily_pnl = round(random.uniform(-200_000, 400_000), 2)
        self._connected = True
        self._mode = "PAPER"

        self._agent_signals = {a[1]: random.randint(0, 120) for a in AGENTS}
        self._agent_pnl = {a[1]: round(random.uniform(-50000, 150000), 2) for a in AGENTS}

        self._events = []
        templates = [
            ("⟐", "gold", "Trade executed: {ticker} {side} x{qty}"),
            ("⚠", "crimson_bright", "Risk alert: drawdown approaching limit"),
            ("⚙", "silver", "System heartbeat OK — all agents responsive"),
            ("⟐", "gold", "Signal generated by QUANT for {ticker}"),
            ("⚙", "silver", "Portfolio rebalance scheduled"),
            ("⚠", "crimson_bright", "Volatility spike detected on {ticker}"),
        ]
        for _ in range(12):
            tmpl = random.choice(templates)
            msg = tmpl[2].format(ticker=random.choice(TICKERS), side=random.choice(["BUY", "SELL"]), qty=random.randint(10, 200))
            self._events.append((datetime.now(MOSCOW_TZ).strftime("%H:%M:%S"), tmpl[0], tmpl[1], msg))

    def _random_trade(self):
        ticker = random.choice(TICKERS)
        side = random.choice(["BUY", "SELL"])
        qty = random.randint(1, 100) * 10
        price = round(random.uniform(80, 5000), 2)
        pnl = round(random.uniform(-5000, 8000), 2)
        ts = datetime.now(MOSCOW_TZ).strftime("%H:%M:%S")
        return {"ts": ts, "ticker": ticker, "side": side, "qty": qty, "price": price, "pnl": pnl}

    def _build_title_bar(self):
        if self._is_divine:
            return DualismHeader("◇  LUX NOX CAPITAL  ◇  MONOLITH  ◇")
        if self._is_ny_deco:
            return DualismHeader("◆  LUX NOX CAPITAL  ◆  MANHATTAN  ◆")

        from pathlib import Path

        frame = QFrame()
        frame.setFixedHeight(68)
        frame.setStyleSheet(f"background-color: {COLORS['bg_void']}; border: none;")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(0, 4, 0, 4)
        layout.setSpacing(0)

        chevron_top = QLabel("═══════════════════════════════════════════════════════════════════════════════")
        chevron_top.setAlignment(Qt.AlignmentFlag.AlignCenter)
        chevron_top.setStyleSheet(f"color: {COLORS['gold_dim']}; font-size: 8px; font-family: Consolas;")
        layout.addWidget(chevron_top)

        title_row = QHBoxLayout()
        title_row.setSpacing(8)
        title_row.addStretch()

        lux_label = QLabel("LUX")
        lux_label.setStyleSheet(
            f"color: {COLORS['gold']}; font-size: 18px; font-weight: bold; "
            f"letter-spacing: 6px; font-family: 'Segoe UI';")
        title_row.addWidget(lux_label)

        logo_path = Path(__file__).resolve().parent.parent / "assets" / "logo_sun.png"
        if logo_path.exists():
            logo_pixmap = QPixmap(str(logo_path)).scaled(
                30, 30, Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation)
            logo_label = QLabel()
            logo_label.setPixmap(logo_pixmap)
            logo_label.setStyleSheet("background: transparent;")
            title_row.addWidget(logo_label)
        else:
            sun_label = QLabel("☉")
            sun_label.setStyleSheet(
                f"color: {COLORS['gold']}; font-size: 20px; background: transparent;")
            title_row.addWidget(sun_label)

        nox_label = QLabel("NOX")
        nox_label.setStyleSheet(
            f"color: {COLORS['gold']}; font-size: 18px; font-weight: bold; "
            f"letter-spacing: 6px; font-family: 'Segoe UI';")
        title_row.addWidget(nox_label)
        title_row.addStretch()

        layout.addLayout(title_row)

        capital_label = QLabel("CAPITAL")
        capital_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        capital_label.setStyleSheet(
            f"color: {COLORS['gold_dim']}; font-size: 10px; letter-spacing: 8px;")
        layout.addWidget(capital_label)

        monolith_label = QLabel("MONOLITH")
        monolith_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        monolith_label.setStyleSheet(
            f"color: {COLORS['ivory_dim']}; font-size: 9px; letter-spacing: 4px;")
        layout.addWidget(monolith_label)

        chevron_bot = QLabel("═══════════════════════════════════════════════════════════════════════════════")
        chevron_bot.setAlignment(Qt.AlignmentFlag.AlignCenter)
        chevron_bot.setStyleSheet(f"color: {COLORS['gold_dim']}; font-size: 8px; font-family: Consolas;")
        layout.addWidget(chevron_bot)

        return frame

    def _build_status_bar(self):
        frame = QFrame()
        frame.setFixedHeight(36)
        frame.setStyleSheet(
            f"background-color: {COLORS['bg_dark']}; border: 1px solid {COLORS['gold_dim']}; border-radius: 2px;"
        )
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(12, 0, 12, 0)
        layout.setSpacing(0)

        def add_item(text, color=COLORS["ivory"]):
            lbl = QLabel(text)
            lbl.setStyleSheet(f"color: {color}; font-family: Consolas; font-size: 11px;")
            layout.addWidget(lbl)
            return lbl

        def add_divider():
            d = QLabel(" ◆ ")
            d.setStyleSheet(f"color: {COLORS['gold_dim']}; font-size: 10px;")
            layout.addWidget(d)

        self._lbl_mode = add_item(f"MODE: {self._mode}", COLORS["gold_light"])
        add_divider()
        conn_color = COLORS["gold"] if self._connected else COLORS["crimson_bright"]
        self._lbl_conn = add_item(f"● QUIK", conn_color)
        add_divider()
        self._lbl_portfolio = add_item(f"PORTFOLIO: {self._portfolio_value:,.0f} ₽", COLORS["gold"])
        add_divider()
        pnl_color = COLORS["gold"] if self._daily_pnl >= 0 else COLORS["crimson_bright"]
        sign = "+" if self._daily_pnl >= 0 else ""
        self._lbl_pnl = add_item(f"P&L: {sign}{self._daily_pnl:,.0f} ₽", pnl_color)
        add_divider()
        now_msk = datetime.now(MOSCOW_TZ).strftime("%H:%M:%S MSK")
        self._lbl_time = add_item(now_msk, COLORS["silver"])

        layout.addStretch()

        # Health indicator
        self._lbl_health = QLabel("🟢 ЗДОРОВ")
        self._lbl_health.setStyleSheet(
            f"color: {COLORS['emerald_bright']}; font-family: Consolas; font-size: 11px; font-weight: bold;"
        )
        layout.addWidget(self._lbl_health)

        add_divider()

        # Emergency stop button
        stop_btn = QPushButton("⛔ СТОП")
        stop_btn.setFixedSize(80, 28)
        stop_btn.setStyleSheet(
            f"QPushButton {{ background: {COLORS['crimson']}; color: {COLORS['ivory']}; "
            f"border: 2px solid {COLORS['crimson_bright']}; border-radius: 3px; "
            f"font-weight: bold; font-size: 11px; }}"
            f"QPushButton:hover {{ background: {COLORS['crimson_bright']}; }}"
        )
        stop_btn.clicked.connect(self._on_emergency_stop)
        layout.addWidget(stop_btn)

        return frame

    def _on_emergency_stop(self):
        reply = QMessageBox.warning(
            self, "ЭКСТРЕННАЯ ОСТАНОВКА",
            "Вы уверены? Все позиции будут закрыты!\n\nДля подтверждения нажмите ОК.",
            QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel,
        )
        if reply == QMessageBox.StandardButton.Ok:
            RuntimeState.request_emergency_stop()
            self._mode = "STOPPED"
            self._lbl_mode.setText("MODE: STOPPED")
            self._lbl_mode.setStyleSheet(
                f"color: {COLORS['crimson_bright']}; font-family: Consolas; font-size: 11px; font-weight: bold;"
            )
            ts = datetime.now(MOSCOW_TZ).strftime("%H:%M:%S")
            self._events.append((ts, "⛔", "crimson_bright", "EMERGENCY STOP REQUESTED — signal sent to main process"))
            self._populate_events()

    def _build_left_panel(self):
        if self._is_divine or self._is_ny_deco:
            frame = TexturedCard(texture="dark")
        else:
            frame = DecorativeFrame(draw_corners=True)
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(4)

        header = QLabel("THE SACRED LEDGER — Scales of Judgement")
        header.setStyleSheet(
            f"color: {COLORS['gold']}; font-size: 13px; font-weight: bold; letter-spacing: 3px;"
        )
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(header)

        self._positions_table = QTableWidget()
        self._positions_table.setColumnCount(7)
        self._positions_table.setHorizontalHeaderLabels(["Ticker", "Side", "Qty", "Entry", "Current", "P&L", "Agent"])
        self._positions_table.setAlternatingRowColors(True)
        self._positions_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._positions_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._positions_table.verticalHeader().setVisible(False)
        self._positions_table.setShowGrid(False)
        h = self._positions_table.horizontalHeader()
        h.setStretchLastSection(True)
        h.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._populate_positions()
        layout.addWidget(self._positions_table, stretch=3)

        if self._is_divine or self._is_ny_deco:
            layout.addWidget(SacredSeparator())
        else:
            layout.addWidget(SeparatorLine())

        trades_header = QLabel("RECENT TRADES — The Eternal Record")
        trades_header.setStyleSheet(
            f"color: {COLORS['gold_dim']}; font-size: 11px; font-weight: bold; letter-spacing: 2px;"
        )
        trades_header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(trades_header)

        self._trades_text = QTextEdit()
        self._trades_text.setReadOnly(True)
        self._trades_text.setMaximumHeight(160)
        self._populate_trades()
        layout.addWidget(self._trades_text, stretch=1)

        return frame

    def _populate_positions(self):
        table = self._positions_table
        table.setRowCount(len(self._positions))
        for row, pos in enumerate(self._positions):
            side_color = COLORS["gold"] if pos["side"] == "LONG" else COLORS["crimson_bright"]
            border_color = COLORS["gold_dim"] if pos["side"] == "LONG" else COLORS["crimson"]

            items = [
                pos["ticker"], pos["side"], str(pos["qty"]),
                f"{pos['entry']:.2f}", f"{pos['current']:.2f}",
                f"{pos['pnl']:+,.0f}", pos["agent"],
            ]
            for col, text in enumerate(items):
                item = QTableWidgetItem(text)
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if col == 1:
                    item.setForeground(QColor(side_color))
                elif col == 5:
                    pnl_color = COLORS["emerald_bright"] if pos["pnl"] >= 0 else COLORS["crimson_bright"]
                    item.setForeground(QColor(pnl_color))
                else:
                    item.setForeground(QColor(COLORS["ivory"]))
                table.setItem(row, col, item)

    def _populate_trades(self):
        lines = []
        for t in self._trades[-15:]:
            prefix = f"<span style='color:{COLORS['gold']}'>△</span>" if t["side"] == "BUY" else f"<span style='color:{COLORS['crimson_bright']}'>▽</span>"
            pnl_color = COLORS["emerald_bright"] if t["pnl"] >= 0 else COLORS["crimson_bright"]
            line = (
                f"<span style='color:{COLORS['ivory_dim']}'>{t['ts']}</span> "
                f"{prefix} "
                f"<span style='color:{COLORS['ivory']}'>{t['ticker']:5s}</span> "
                f"<span style='color:{COLORS['ivory_dim']}'>{t['side']:4s} x{t['qty']:<4d} @ {t['price']:.2f}</span> "
                f"<span style='color:{pnl_color}'>P&L: {t['pnl']:+,.0f}</span>"
            )
            lines.append(line)
        self._trades_text.setHtml("<br>".join(reversed(lines)))

    def _build_right_panel(self):
        if self._is_divine or self._is_ny_deco:
            frame = TexturedCard(texture="dark")
        else:
            frame = DecorativeFrame(draw_corners=True)
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(4)

        header = QLabel("THE PANTHEON — Agent Council")
        header.setStyleSheet(
            f"color: {COLORS['gold']}; font-size: 13px; font-weight: bold; letter-spacing: 3px;"
        )
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(header)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        scroll_content = QWidget()
        scroll_content.setStyleSheet("background: transparent;")
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setContentsMargins(4, 4, 4, 4)
        scroll_layout.setSpacing(4)

        _AGENT_ICON_MAP = {
            "ORCHESTRATOR": "crown.svg",
            "SCALPING": "zap.svg",
            "DAY TRADING": "sun.svg",
            "LONG TERM": "infinity.svg",
            "NEWS": "newspaper.svg",
            "RISK SHIELD": "shield.svg",
            "QUANT": "atom.svg",
            "HEDGING": "lock.svg",
            "SRE": "settings.svg",
        }

        self._agent_labels = {}
        for symbol, name, title in AGENTS:
            if self._is_divine:
                icon_file = _AGENT_ICON_MAP.get(name, "settings.svg")
                card = AgentCard(icon_file, name, title)
                signals = self._agent_signals.get(name, 0)
                pnl = self._agent_pnl.get(name, 0)
                card.detail_label.setText(f"Signals: {signals}  |  P&L: {pnl:+,.0f}")
                self._agent_labels[name] = card.detail_label
                scroll_layout.addWidget(card)
            else:
                card = QFrame()
                card.setStyleSheet(
                    f"QFrame {{ background-color: {COLORS['bg_card']}; border: 1px solid {COLORS['gold_dim']}; border-radius: 2px; }}"
                )
                card.setFixedHeight(56)
                card_layout = QHBoxLayout(card)
                card_layout.setContentsMargins(10, 4, 10, 4)
                card_layout.setSpacing(8)

                icon_lbl = QLabel(symbol)
                icon_lbl.setStyleSheet(f"font-size: 18px; color: {COLORS['gold']};")
                icon_lbl.setFixedWidth(24)
                card_layout.addWidget(icon_lbl)

                info_layout = QVBoxLayout()
                info_layout.setSpacing(1)
                name_lbl = QLabel(f"{name} · {title}")
                name_lbl.setStyleSheet(f"color: {COLORS['gold']}; font-size: 11px; font-weight: bold; letter-spacing: 1px;")
                info_layout.addWidget(name_lbl)

                signals = self._agent_signals.get(name, 0)
                pnl = self._agent_pnl.get(name, 0)
                detail_lbl = QLabel(f"Signals: {signals}  |  P&L: {pnl:+,.0f}")
                detail_lbl.setStyleSheet(f"color: {COLORS['ivory_dim']}; font-size: 10px; font-family: Consolas;")
                info_layout.addWidget(detail_lbl)
                self._agent_labels[name] = detail_lbl

                card_layout.addLayout(info_layout, stretch=1)

                status_lbl = QLabel("●")
                status_lbl.setStyleSheet(f"color: {COLORS['emerald_bright']}; font-size: 14px;")
                status_lbl.setFixedWidth(20)
                status_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
                card_layout.addWidget(status_lbl)

                scroll_layout.addWidget(card)

        scroll_layout.addStretch()
        scroll.setWidget(scroll_content)
        layout.addWidget(scroll)

        return frame

    def _build_bottom_panel(self):
        frame = QFrame()
        frame.setFixedHeight(150)
        frame.setStyleSheet(
            f"QFrame {{ background-color: {COLORS['bg_dark']}; border: 1px solid {COLORS['gold_dim']}; border-radius: 2px; }}"
        )
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(2)

        header = QLabel("THE ORACLE'S WHISPER — Event Chronicle")
        header.setStyleSheet(
            f"color: {COLORS['gold_dim']}; font-size: 11px; font-weight: bold; letter-spacing: 2px;"
        )
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(header)

        self._event_log = QTextEdit()
        self._event_log.setReadOnly(True)
        self._event_log.setStyleSheet(
            f"background-color: {COLORS['bg_void']}; border: none; font-family: Consolas; font-size: 11px;"
        )
        self._populate_events()
        layout.addWidget(self._event_log)

        return frame

    def _populate_events(self):
        lines = []
        for ts, icon, color_key, msg in self._events[-20:]:
            color = COLORS.get(color_key, COLORS["ivory_dim"])
            line = f"<span style='color:{COLORS['ivory_dim']}'>[{ts}]</span> <span style='color:{color}'>{icon} {msg}</span>"
            lines.append(line)
        self._event_log.setHtml("<br>".join(reversed(lines)))

    def _update_data(self):
        live = RuntimeState.read(max_age_sec=15.0)
        if live and self._apply_live_state(live):
            self._live_mode = True
            self._lbl_mode.setText(f"MODE: {self._mode} ● LIVE")
            conn_color = COLORS["gold"] if self._connected else COLORS["crimson_bright"]
            self._lbl_conn.setText("● CONNECTED" if self._connected else "● OFFLINE")
            self._lbl_conn.setStyleSheet(f"color: {conn_color}; font-family: Consolas; font-size: 11px;")
            self._populate_positions()
            self._lbl_portfolio.setText(f"PORTFOLIO: {self._portfolio_value:,.0f} ₽")
            pnl_color = COLORS["gold"] if self._daily_pnl >= 0 else COLORS["crimson_bright"]
            sign = "+" if self._daily_pnl >= 0 else ""
            self._lbl_pnl.setText(f"P&L: {sign}{self._daily_pnl:,.0f} ₽")
            self._lbl_pnl.setStyleSheet(f"color: {pnl_color}; font-family: Consolas; font-size: 11px;")
            self._lbl_time.setText(datetime.now(MOSCOW_TZ).strftime("%H:%M:%S MSK"))
            self._populate_trades()
            for symbol, name, title in AGENTS:
                lbl = self._agent_labels.get(name)
                if lbl:
                    lbl.setText(f"Signals: {self._agent_signals.get(name, 0)}")
            self._populate_events()
            health = "🟢 ЗДОРОВ" if self._connected and self._mode != "STOPPED" else "🔴 СТОП"
            self._lbl_health.setText(health)
            return

        self._live_mode = False
        for pos in self._positions:
            delta = pos["current"] * random.uniform(-0.005, 0.005)
            pos["current"] = round(pos["current"] + delta, 2)
            pos["pnl"] = round(
                (pos["current"] - pos["entry"]) * pos["qty"] * (1 if pos["side"] == "LONG" else -1), 2
            )
        self._populate_positions()

        self._portfolio_value += random.uniform(-20000, 30000)
        self._daily_pnl += random.uniform(-5000, 7000)

        self._lbl_portfolio.setText(f"PORTFOLIO: {self._portfolio_value:,.0f} ₽")
        pnl_color = COLORS["gold"] if self._daily_pnl >= 0 else COLORS["crimson_bright"]
        sign = "+" if self._daily_pnl >= 0 else ""
        self._lbl_pnl.setText(f"P&L: {sign}{self._daily_pnl:,.0f} ₽")
        self._lbl_pnl.setStyleSheet(f"color: {pnl_color}; font-family: Consolas; font-size: 11px;")
        self._lbl_time.setText(datetime.now(MOSCOW_TZ).strftime("%H:%M:%S MSK"))

        new_trade = self._random_trade()
        self._trades.append(new_trade)
        self._trades = self._trades[-30:]
        self._populate_trades()

        for name in self._agent_signals:
            self._agent_signals[name] += random.randint(0, 3)
            self._agent_pnl[name] += random.uniform(-2000, 3000)
        for symbol, name, title in AGENTS:
            lbl = self._agent_labels.get(name)
            if lbl:
                signals = self._agent_signals[name]
                pnl = self._agent_pnl[name]
                lbl.setText(f"Signals: {signals}  |  P&L: {pnl:+,.0f}")

        event_templates = [
            ("⟐", "gold", f"Trade executed: {random.choice(TICKERS)} {random.choice(['BUY','SELL'])} x{random.randint(10,200)}"),
            ("⚠", "crimson_bright", f"Risk alert: position concentration on {random.choice(TICKERS)}"),
            ("⚙", "silver", "System heartbeat OK — all agents responsive"),
        ]
        tmpl = random.choice(event_templates)
        ts = datetime.now(MOSCOW_TZ).strftime("%H:%M:%S")
        self._events.append((ts, tmpl[0], tmpl[1], tmpl[2]))
        self._events = self._events[-20:]
        self._populate_events()


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = AlchemyDashboard()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
