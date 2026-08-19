"""Автоматическое резервное копирование конфигурации."""

from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
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

MAX_BACKUPS = 10


class ConfigBackup:
    """Управление резервными копиями settings.yaml."""

    def __init__(self, config_path: Optional[str] = None, backup_dir: Optional[str] = None):
        base = Path(__file__).parent.parent / "config"
        self.config_path = Path(config_path) if config_path else base / "settings.yaml"
        self.backup_dir = Path(backup_dir) if backup_dir else base / "backups"
        self.backup_dir.mkdir(parents=True, exist_ok=True)

    def create_backup(self) -> Optional[Path]:
        """Создаёт резервную копию с таймстемпом."""
        if not self.config_path.exists():
            logger.warning("Config file not found, skipping backup")
            return None

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        backup_name = f"settings_{timestamp}.yaml"
        backup_path = self.backup_dir / backup_name
        shutil.copy2(self.config_path, backup_path)
        logger.info(f"Backup created: {backup_name}")

        self._cleanup_old_backups()
        return backup_path

    def list_backups(self) -> list[dict]:
        """Возвращает список бэкапов с метаданными."""
        backups = []
        for f in sorted(self.backup_dir.glob("settings_*.yaml"), reverse=True):
            stat = f.stat()
            backups.append({
                "name": f.name,
                "path": str(f),
                "date": datetime.fromtimestamp(stat.st_mtime),
                "size_kb": stat.st_size / 1024,
            })
        return backups

    def restore_backup(self, backup_name: str) -> bool:
        """Восстанавливает конфигурацию из бэкапа."""
        backup_path = self.backup_dir / backup_name
        if not backup_path.exists():
            logger.error(f"Backup not found: {backup_name}")
            return False

        self.create_backup()
        shutil.copy2(backup_path, self.config_path)
        logger.info(f"Restored backup: {backup_name}")
        return True

    def auto_backup_on_save(self) -> None:
        """Вызывается перед каждым сохранением конфигурации."""
        self.create_backup()

    def _cleanup_old_backups(self) -> None:
        """Оставляет только последние MAX_BACKUPS копий."""
        backups = sorted(self.backup_dir.glob("settings_*.yaml"), reverse=True)
        for old in backups[MAX_BACKUPS:]:
            old.unlink()
            logger.debug(f"Deleted old backup: {old.name}")

    @staticmethod
    def show_backup_manager_dialog(parent: QWidget) -> None:
        """Показывает диалог управления бэкапами в стиле Art Deco."""
        dialog = _BackupManagerDialog(parent)
        dialog.exec()


class _BackupManagerDialog(QDialog):
    """Диалог управления резервными копиями."""

    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self.setWindowTitle("Резервные копии")
        self.setMinimumSize(500, 400)
        self._backup = ConfigBackup()
        self._setup_ui()
        self._refresh_list()

    def _setup_ui(self) -> None:
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {COLORS['bg_void']};
            }}
            QLabel {{
                color: {COLORS['ivory']};
            }}
            QListWidget {{
                background-color: {COLORS['bg_card']};
                border: 1px solid {COLORS['gold_dim']};
                border-radius: 4px;
                color: {COLORS['ivory']};
                font-size: 12px;
            }}
            QListWidget::item:selected {{
                background-color: {COLORS['obsidian']};
            }}
            QPushButton {{
                background-color: {COLORS['bg_card']};
                border: 1px solid {COLORS['gold_dim']};
                border-radius: 4px;
                padding: 8px 16px;
                color: {COLORS['gold']};
                font-weight: bold;
            }}
            QPushButton:hover {{
                border-color: {COLORS['gold']};
            }}
        """)

        layout = QVBoxLayout(self)

        title = QLabel("✦ Резервные копии настроек ✦")
        title.setStyleSheet(f"font-size: 16px; font-weight: bold; color: {COLORS['gold']};")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        self._list = QListWidget()
        layout.addWidget(self._list)

        btn_layout = QHBoxLayout()
        btn_restore = QPushButton("Восстановить")
        btn_restore.clicked.connect(self._restore)
        btn_delete = QPushButton("Удалить")
        btn_delete.clicked.connect(self._delete)
        btn_layout.addWidget(btn_restore)
        btn_layout.addWidget(btn_delete)
        layout.addLayout(btn_layout)

    def _refresh_list(self) -> None:
        self._list.clear()
        for b in self._backup.list_backups():
            date_str = b["date"].strftime("%d.%m.%Y %H:%M:%S")
            item = QListWidgetItem(f"{date_str}  ({b['size_kb']:.1f} КБ)")
            item.setData(Qt.ItemDataRole.UserRole, b["name"])
            self._list.addItem(item)

    def _get_selected_name(self) -> Optional[str]:
        item = self._list.currentItem()
        return item.data(Qt.ItemDataRole.UserRole) if item else None

    def _restore(self) -> None:
        name = self._get_selected_name()
        if not name:
            return
        if self._backup.restore_backup(name):
            QMessageBox.information(self, "Готово", "Настройки восстановлены. Перезапустите приложение.")
            self._refresh_list()

    def _delete(self) -> None:
        name = self._get_selected_name()
        if not name:
            return
        path = self._backup.backup_dir / name
        if path.exists():
            path.unlink()
            self._refresh_list()
