"""Бэкапы: создание, восстановление, автобэкап."""
from __future__ import annotations

import os
import subprocess

from PySide6.QtWidgets import (QCheckBox, QComboBox, QHBoxLayout, QLabel,
                               QProgressBar, QSpinBox, QTableWidget,
                               QTableWidgetItem, QVBoxLayout, QWidget)

from app.core.backup_manager import BackupManager
from app.gui.widgets import (Card, Worker, confirm, make_button, page_header,
                             show_error, show_info)
from app.models.backup import Backup

COLUMNS = ["Название", "Дата", "Тип", "Размер"]
TYPE_LABELS = {"full": "Полный", "configs": "Конфиги", "plugins": "Плагины"}
SCHEDULES = {"Каждый час": "hourly", "Каждые 6 часов": "every6h",
             "Ежедневно": "daily", "Еженедельно": "weekly"}


class BackupsPage(QWidget):
    def __init__(self, ctx) -> None:
        super().__init__()
        self.ctx = ctx
        self.setObjectName("Page")
        self._backups: list[Backup] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)
        layout.addWidget(page_header("Бэкапы", "Резервные копии сервера (zip)"))

        controls = QHBoxLayout()
        controls.addWidget(QLabel("Тип:"))
        self.type_combo = QComboBox()
        for key, label in TYPE_LABELS.items():
            self.type_combo.addItem(f"{label} ({key})", key)
        controls.addWidget(self.type_combo)
        self.create_btn = make_button("❒ Создать бэкап сейчас", "Primary", self._create)
        controls.addWidget(self.create_btn)
        controls.addWidget(make_button("♻ Восстановить", "Warning", self._restore))
        controls.addWidget(make_button("🗑 Удалить", "Danger", self._delete))
        controls.addWidget(make_button("📂 Папка бэкапов", on_click=self._open_folder))
        controls.addStretch(1)
        layout.addLayout(controls)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setVisible(False)
        layout.addWidget(self.progress)

        table_card = Card()
        self.table = QTableWidget(0, len(COLUMNS))
        self.table.setHorizontalHeaderLabels(COLUMNS)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setColumnWidth(0, 320)
        self.table.setColumnWidth(1, 170)
        self.table.setMinimumHeight(280)
        table_card.add(self.table)
        layout.addWidget(table_card)

        auto_card = Card("Автобэкап")
        auto_row = QHBoxLayout()
        self.auto_check = QCheckBox("Включить автобэкап")
        auto_row.addWidget(self.auto_check)
        auto_row.addWidget(QLabel("Расписание:"))
        self.schedule_combo = QComboBox()
        self.schedule_combo.addItems(list(SCHEDULES.keys()))
        auto_row.addWidget(self.schedule_combo)
        auto_row.addWidget(QLabel("Тип:"))
        self.auto_type_combo = QComboBox()
        for key, label in TYPE_LABELS.items():
            self.auto_type_combo.addItem(label, key)
        auto_row.addWidget(self.auto_type_combo)
        auto_row.addWidget(QLabel("Максимум копий:"))
        self.max_spin = QSpinBox()
        self.max_spin.setRange(1, 100)
        auto_row.addWidget(self.max_spin)
        auto_row.addWidget(make_button("Сохранить", "Primary", self._save_auto))
        auto_row.addStretch(1)
        auto_card.add_layout(auto_row)
        layout.addWidget(auto_card)
        layout.addStretch(1)

        self._load_auto_settings()
        self.refresh()

    # ------------------------------------------------------------ helpers

    def _manager(self) -> BackupManager:
        return BackupManager(str(self.ctx.settings.backups_dir()))

    def _selected(self) -> Backup | None:
        row = self.table.currentRow()
        if 0 <= row < len(self._backups):
            return self._backups[row]
        return None

    def refresh(self) -> None:
        self._backups = self._manager().list_backups()
        self.table.setRowCount(len(self._backups))
        for row, backup in enumerate(self._backups):
            values = [backup.filename, backup.created_at.replace("T", " "),
                      TYPE_LABELS.get(backup.backup_type, backup.backup_type),
                      backup.size_human]
            for col, value in enumerate(values):
                self.table.setItem(row, col, QTableWidgetItem(value))

    # ----------------------------------------------------------- действия

    def _create(self) -> None:
        profile = self.ctx.active_profile
        if profile is None:
            show_error(self, "Бэкап", "Нет активного профиля.")
            return
        backup_type = self.type_combo.currentData()
        if backup_type == "full" and not confirm(
                self, "Полный бэкап",
                "Полный бэкап может занять много места и времени "
                "(папка steamapps пропускается). Продолжить?"):
            return
        self.create_btn.setEnabled(False)
        self.progress.setVisible(True)
        self.progress.setValue(0)
        manager = self._manager()
        self._worker = Worker(manager.create_backup, profile.server_path, backup_type,
                              profile.id, use_progress=True)
        self._worker.progress.connect(self._on_progress)
        self._worker.finished_ok.connect(self._on_created)
        self._worker.failed.connect(self._on_failed)
        self._worker.start()

    def _on_progress(self, done: int, total: int) -> None:
        if total:
            self.progress.setValue(int(done / total * 100))

    def _on_created(self, backup: Backup) -> None:
        self.create_btn.setEnabled(True)
        self.progress.setVisible(False)
        show_info(self, "Бэкап", f"Создан: {backup.filename} ({backup.size_human})")
        self.refresh()

    def _on_failed(self, err: str) -> None:
        self.create_btn.setEnabled(True)
        self.progress.setVisible(False)
        show_error(self, "Бэкап", err)

    def _restore(self) -> None:
        backup = self._selected()
        profile = self.ctx.active_profile
        if backup is None:
            show_info(self, "Восстановление", "Выберите бэкап в списке.")
            return
        if profile is None:
            show_error(self, "Восстановление", "Нет активного профиля (куда восстанавливать).")
            return
        if self.ctx.server_manager and self.ctx.server_manager.is_running():
            show_error(self, "Восстановление", "Сначала остановите сервер.")
            return
        if not confirm(self, "Восстановление",
                       f"Восстановить {backup.filename} в\n{profile.server_path}?\n"
                       "Существующие файлы будут перезаписаны!", danger=True):
            return
        self.progress.setVisible(True)
        self.progress.setValue(0)
        manager = self._manager()
        self._restore_worker = Worker(manager.restore_backup, backup, profile.server_path,
                                      use_progress=True)
        self._restore_worker.progress.connect(self._on_progress)
        self._restore_worker.finished_ok.connect(
            lambda _: (self.progress.setVisible(False),
                       show_info(self, "Восстановление", "Готово ✔")))
        self._restore_worker.failed.connect(self._on_failed)
        self._restore_worker.start()

    def _delete(self) -> None:
        backup = self._selected()
        if backup is None:
            return
        if not confirm(self, "Удаление", f"Удалить бэкап {backup.filename}?", danger=True):
            return
        self._manager().delete_backup(backup)
        self.refresh()

    def _open_folder(self) -> None:
        path = self.ctx.settings.backups_dir()
        if os.name == "nt":
            os.startfile(str(path))  # noqa: S606
        else:
            subprocess.Popen(["xdg-open", str(path)])  # noqa: S603,S607

    # ---------------------------------------------------------- автобэкап

    def _load_auto_settings(self) -> None:
        settings = self.ctx.settings
        self.auto_check.setChecked(settings.get("automation.auto_backup_enabled", False))
        schedule = settings.get("automation.auto_backup_schedule", "daily")
        for label, key in SCHEDULES.items():
            if key == schedule:
                self.schedule_combo.setCurrentText(label)
        auto_type = settings.get("automation.auto_backup_type", "configs")
        index = self.auto_type_combo.findData(auto_type)
        if index >= 0:
            self.auto_type_combo.setCurrentIndex(index)
        self.max_spin.setValue(int(settings.get("automation.auto_backup_max_count", 10)))

    def _save_auto(self) -> None:
        settings = self.ctx.settings
        settings.set("automation.auto_backup_enabled", self.auto_check.isChecked(), save=False)
        settings.set("automation.auto_backup_schedule",
                     SCHEDULES[self.schedule_combo.currentText()], save=False)
        settings.set("automation.auto_backup_type", self.auto_type_combo.currentData(),
                     save=False)
        settings.set("automation.auto_backup_max_count", self.max_spin.value())
        show_info(self, "Автобэкап", "Настройки автобэкапа сохранены.")

    def on_show(self) -> None:
        self.refresh()
