"""Automates QUIK setup: script installation, auto-launch, diagnostics."""
from __future__ import annotations

import shutil
import socket
import subprocess
import os
from pathlib import Path
from typing import Any

from ..utils.logger import get_logger

log = get_logger("quik.auto_setup")


class QuikAutoSetup:
    """Helps users set up QUIK with minimal effort."""

    LUA_SCRIPT_NAME = "hedge_fund_server.lua"
    DEFAULT_PORT = 34130

    def __init__(self, quik_path: str | None = None):
        self.quik_path = Path(quik_path) if quik_path else self._find_quik()

    # ── Detection ──────────────────────────────────────────────

    def _find_quik(self) -> Path | None:
        """Auto-detect QUIK installation path."""
        common = [
            Path("C:/QUIK"), Path("C:/QUIK_Sber"), Path("C:/QUIK-Junior"),
            Path("C:/Program Files/QUIK"), Path("C:/Program Files (x86)/QUIK"),
            Path.home() / "Desktop" / "QUIK",
        ]
        for p in common:
            if p.exists() and (p / "info.exe").exists():
                log.info("QUIK found at %s", p)
                return p

        try:
            import psutil
            for proc in psutil.process_iter(["name", "exe"]):
                name = proc.info.get("name") or ""
                if "info.exe" in name.lower():
                    exe = proc.info.get("exe")
                    if exe:
                        found = Path(exe).parent
                        log.info("QUIK detected via running process: %s", found)
                        return found
        except Exception:
            pass

        try:
            import winreg
            for hive in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
                try:
                    with winreg.OpenKey(hive, r"SOFTWARE\QUIK") as key:
                        val, _ = winreg.QueryValueEx(key, "InstallPath")
                        p = Path(val)
                        if p.exists():
                            return p
                except OSError:
                    continue
        except Exception:
            pass

        return None

    def is_quik_installed(self) -> bool:
        return self.quik_path is not None and (self.quik_path / "info.exe").exists()

    def is_quik_running(self) -> bool:
        try:
            import psutil
            for proc in psutil.process_iter(["name"]):
                name = proc.info.get("name") or ""
                if "info.exe" in name.lower():
                    return True
        except Exception:
            pass
        return False

    # ── LUA script management ─────────────────────────────────

    def _lua_source(self) -> Path:
        return Path(__file__).parent / "lua" / "main.lua"

    def _lua_dest(self) -> Path | None:
        if not self.quik_path:
            return None
        return self.quik_path / "lua" / self.LUA_SCRIPT_NAME

    def check_lua_script_installed(self) -> bool:
        dest = self._lua_dest()
        return dest is not None and dest.exists()

    def install_lua_script(self) -> bool:
        """Copy our LUA script to QUIK's lua/ directory."""
        if not self.quik_path:
            log.error("QUIK path not set — cannot install script")
            return False
        src = self._lua_source()
        if not src.exists():
            log.error("Source LUA script not found: %s", src)
            return False
        dest = self._lua_dest()
        assert dest is not None
        dest.parent.mkdir(parents=True, exist_ok=True)
        try:
            shutil.copy2(src, dest)
            log.info("LUA script installed: %s -> %s", src, dest)
            return True
        except Exception as exc:
            log.error("Failed to install LUA script: %s", exc)
            return False

    # ── Launch ────────────────────────────────────────────────

    def launch_quik(self, minimized: bool = True) -> bool:
        if not self.quik_path:
            return False
        exe = self.quik_path / "info.exe"
        if not exe.exists():
            return False
        try:
            si = subprocess.STARTUPINFO()
            if minimized:
                si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                si.wShowWindow = 6  # SW_MINIMIZE
            subprocess.Popen([str(exe)], cwd=str(self.quik_path), startupinfo=si)
            log.info("QUIK launched from %s", exe)
            return True
        except Exception as exc:
            log.error("Failed to launch QUIK: %s", exc)
            return False

    # ── Diagnostics ───────────────────────────────────────────

    def _check_port(self, host: str = "127.0.0.1", port: int = DEFAULT_PORT,
                    timeout: float = 2.0) -> bool:
        try:
            with socket.create_connection((host, port), timeout=timeout):
                return True
        except (OSError, socket.timeout):
            return False

    def run_diagnostics(self) -> dict[str, Any]:
        issues: list[str] = []
        fixes: list[str] = []

        quik_found = self.is_quik_installed()
        quik_running = self.is_quik_running()
        lua_installed = self.check_lua_script_installed()
        port_open = self._check_port()
        conn_test = False

        quik_version = ""
        if self.quik_path:
            ver_file = self.quik_path / "Version.txt"
            if ver_file.exists():
                try:
                    quik_version = ver_file.read_text(encoding="utf-8").strip()[:50]
                except Exception:
                    pass

        if not quik_found:
            issues.append("QUIK не найден на компьютере")
            fixes.append("Установите QUIK или укажите путь вручную")
        if quik_found and not quik_running:
            issues.append("QUIK не запущен")
            fixes.append("Запустите QUIK и авторизуйтесь у брокера")
        if quik_found and not lua_installed:
            issues.append("LUA-скрипт не установлен в QUIK")
            fixes.append("Нажмите 'Автонастройка QUIK' для установки скрипта")
        if not port_open:
            issues.append(f"TCP порт {self.DEFAULT_PORT} не отвечает")
            fixes.append("Убедитесь, что LUA-скрипт запущен в QUIK "
                         "(Сервисы → LUA скрипты → Запустить)")
        else:
            conn_test = True

        return {
            "quik_found": quik_found,
            "quik_path": str(self.quik_path) if self.quik_path else "",
            "quik_running": quik_running,
            "quik_version": quik_version,
            "lua_script_installed": lua_installed,
            "tcp_port_open": port_open,
            "connection_test": conn_test,
            "issues": issues,
            "fixes": fixes,
        }

    # ── Setup wizard (PyQt6) ──────────────────────────────────

    @staticmethod
    def show_setup_wizard(parent) -> bool:
        """PyQt6 wizard that guides through QUIK setup."""
        from PyQt6.QtWidgets import (
            QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
            QLineEdit, QFileDialog, QMessageBox, QStackedWidget, QWidget,
        )
        from PyQt6.QtCore import Qt

        COLORS = {
            "bg_void": "#0A0A0F", "bg_dark": "#0D0D14", "bg_card": "#13131F",
            "gold": "#D4AF37", "gold_light": "#F0D060", "gold_dim": "#8B7424",
            "crimson": "#8B0000", "crimson_bright": "#DC143C",
            "ivory": "#FAEBD7", "ivory_dim": "#B8A88A",
            "obsidian": "#1A1A2E", "emerald": "#50C878", "bronze": "#CD7F32",
        }
        C = COLORS

        dlg = QDialog(parent)
        dlg.setWindowTitle("⟐ Мастер настройки QUIK ⟐")
        dlg.resize(600, 450)
        dlg.setStyleSheet(
            f"QDialog {{ background: {C['bg_void']}; color: {C['ivory']}; "
            f"font-family: 'Segoe UI'; font-size: 10pt; }}"
            f"QLabel {{ color: {C['ivory']}; }}"
            f"QLineEdit {{ background: {C['bg_card']}; color: {C['ivory']}; "
            f"border: 1px solid {C['gold_dim']}; border-radius: 3px; padding: 5px 8px; }}"
            f"QLineEdit:focus {{ border-color: {C['gold']}; }}"
        )

        btn_style = (
            f"QPushButton {{ background: {C['bg_card']}; color: {C['gold']}; "
            f"border: 1px solid {C['gold_dim']}; border-radius: 4px; "
            f"padding: 7px 20px; font-weight: bold; }}"
            f"QPushButton:hover {{ border-color: {C['gold']}; color: {C['gold_light']}; }}"
        )

        root = QVBoxLayout(dlg)
        root.setContentsMargins(20, 16, 20, 16)

        title = QLabel("⟐ Мастер настройки QUIK ⟐")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet(
            f"color: {C['gold']}; font-size: 14pt; font-weight: bold; padding: 4px 0 12px 0;")
        root.addWidget(title)

        stack = QStackedWidget()
        root.addWidget(stack, 1)

        # --- Page 0: detect path ---
        page0 = QWidget()
        p0 = QVBoxLayout(page0)
        p0.addWidget(QLabel("Шаг 1: Путь к QUIK"))

        setup = QuikAutoSetup()
        path_edit = QLineEdit(str(setup.quik_path) if setup.quik_path else "")
        path_edit.setPlaceholderText("C:\\QUIK")
        p0.addWidget(path_edit)

        browse_btn = QPushButton("📂 Выбрать папку...")
        browse_btn.setStyleSheet(btn_style)

        def _browse():
            d = QFileDialog.getExistingDirectory(dlg, "Выберите папку QUIK")
            if d:
                path_edit.setText(d)
        browse_btn.clicked.connect(_browse)
        p0.addWidget(browse_btn)

        if setup.quik_path:
            p0.addWidget(QLabel(f"✓ QUIK обнаружен автоматически: {setup.quik_path}"))
        else:
            lbl = QLabel("QUIK не обнаружен автоматически. Укажите путь вручную.")
            lbl.setStyleSheet(f"color: {C['crimson_bright']};")
            p0.addWidget(lbl)
        p0.addStretch()
        stack.addWidget(page0)

        # --- Page 1: install script ---
        page1 = QWidget()
        p1 = QVBoxLayout(page1)
        p1.addWidget(QLabel("Шаг 2: Установка LUA-скрипта"))
        install_status = QLabel("")
        p1.addWidget(install_status)
        p1.addWidget(QLabel(
            "Скрипт будет скопирован в папку lua/ вашего QUIK.\n"
            "Это необходимо для связи программы с терминалом."))
        p1.addStretch()
        stack.addWidget(page1)

        # --- Page 2: instructions ---
        page2 = QWidget()
        p2 = QVBoxLayout(page2)
        p2.addWidget(QLabel("Шаг 3: Запуск скрипта в QUIK"))
        instructions = QLabel(
            "1. Откройте QUIK и авторизуйтесь\n"
            "2. Меню: Сервисы → Lua скрипты\n"
            "3. Нажмите 'Добавить' и выберите файл:\n"
            f"   lua/{QuikAutoSetup.LUA_SCRIPT_NAME}\n"
            "4. Нажмите 'Запустить'\n\n"
            "После запуска скрипт откроет TCP-порт для подключения."
        )
        instructions.setWordWrap(True)
        instructions.setStyleSheet(f"color: {C['ivory']}; font-size: 10pt; line-height: 1.6;")
        p2.addWidget(instructions)
        p2.addStretch()
        stack.addWidget(page2)

        # --- Page 3: test ---
        page3 = QWidget()
        p3 = QVBoxLayout(page3)
        p3.addWidget(QLabel("Шаг 4: Проверка подключения"))
        test_status = QLabel("Нажмите 'Проверить' для тестирования.")
        p3.addWidget(test_status)

        def _run_test():
            s = QuikAutoSetup(path_edit.text().strip() or None)
            diag = s.run_diagnostics()
            lines = []
            for key, label in [
                ("quik_found", "QUIK найден"), ("quik_running", "QUIK запущен"),
                ("lua_script_installed", "Скрипт установлен"),
                ("tcp_port_open", "TCP порт открыт"), ("connection_test", "Соединение"),
            ]:
                ok = diag[key]
                lines.append(f"{'✓' if ok else '✗'} {label}")
            if diag["issues"]:
                lines.append("")
                for issue in diag["issues"]:
                    lines.append(f"⚠ {issue}")
            for fix in diag["fixes"]:
                lines.append(f"💡 {fix}")
            test_status.setText("\n".join(lines))

        test_btn = QPushButton("🔍 Проверить")
        test_btn.setStyleSheet(btn_style)
        test_btn.clicked.connect(_run_test)
        p3.addWidget(test_btn)
        p3.addStretch()
        stack.addWidget(page3)

        # --- Page 4: done ---
        page4 = QWidget()
        p4 = QVBoxLayout(page4)
        done_lbl = QLabel("✓ Настройка завершена!")
        done_lbl.setStyleSheet(f"color: {C['emerald']}; font-size: 14pt; font-weight: bold;")
        done_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        p4.addWidget(done_lbl)
        p4.addWidget(QLabel("Теперь вы можете использовать QUIK для торговли."))
        p4.addStretch()
        stack.addWidget(page4)

        # --- Navigation ---
        nav = QHBoxLayout()
        btn_back = QPushButton("← Назад")
        btn_back.setStyleSheet(btn_style)
        btn_next = QPushButton("Далее →")
        btn_next.setStyleSheet(btn_style)
        nav.addWidget(btn_back)
        nav.addStretch()
        nav.addWidget(btn_next)
        root.addLayout(nav)

        result_holder = [False]

        def _update_nav():
            idx = stack.currentIndex()
            btn_back.setEnabled(idx > 0)
            btn_next.setText("Готово" if idx == stack.count() - 1 else "Далее →")

        def _next():
            idx = stack.currentIndex()
            if idx == 0:
                qpath = path_edit.text().strip()
                if qpath:
                    s = QuikAutoSetup(qpath)
                else:
                    s = QuikAutoSetup()
                if s.install_lua_script():
                    install_status.setText("✓ Скрипт успешно установлен!")
                    install_status.setStyleSheet(f"color: {C['emerald']}; font-size: 11pt;")
                else:
                    install_status.setText(
                        "✗ Не удалось установить скрипт.\n"
                        "Попробуйте скопировать вручную.")
                    install_status.setStyleSheet(f"color: {C['crimson_bright']}; font-size: 11pt;")
            if idx >= stack.count() - 1:
                result_holder[0] = True
                dlg.accept()
                return
            stack.setCurrentIndex(idx + 1)
            _update_nav()

        def _back():
            idx = stack.currentIndex()
            if idx > 0:
                stack.setCurrentIndex(idx - 1)
                _update_nav()

        btn_next.clicked.connect(_next)
        btn_back.clicked.connect(_back)
        _update_nav()

        dlg.exec()
        return result_holder[0]
