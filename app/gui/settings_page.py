"""Настройки приложения: пути, дефолты сервера, автоматизация, быстрые команды."""
from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtWidgets import (QCheckBox, QFileDialog, QGridLayout, QHBoxLayout,
                               QLabel, QLineEdit, QPlainTextEdit, QSpinBox,
                               QVBoxLayout, QWidget)

from app.gui.widgets import Card, confirm, make_button, page_header, show_error, show_info


class SettingsPage(QWidget):
    def __init__(self, ctx) -> None:
        super().__init__()
        self.ctx = ctx
        self.setObjectName("Page")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)
        layout.addWidget(page_header("Настройки приложения"))

        # --- пути ---
        paths = Card("Пути")
        grid = QGridLayout()
        grid.addWidget(QLabel("SteamCMD:"), 0, 0)
        self.steamcmd_edit = QLineEdit()
        grid.addWidget(self.steamcmd_edit, 0, 1)
        grid.addWidget(make_button("Обзор…", on_click=lambda: self._browse(self.steamcmd_edit)),
                       0, 2)
        grid.addWidget(QLabel("Папка бэкапов:"), 1, 0)
        self.backups_edit = QLineEdit()
        self.backups_edit.setPlaceholderText("пусто = папка приложения по умолчанию")
        grid.addWidget(self.backups_edit, 1, 1)
        grid.addWidget(make_button("Обзор…", on_click=lambda: self._browse(self.backups_edit)),
                       1, 2)
        paths.add_layout(grid)
        layout.addWidget(paths)

        # --- дефолты сервера ---
        defaults = Card("Сервер по умолчанию (для новых профилей)")
        dgrid = QGridLayout()
        dgrid.addWidget(QLabel("Порт:"), 0, 0)
        self.port_spin = QSpinBox()
        self.port_spin.setRange(1024, 65535)
        dgrid.addWidget(self.port_spin, 0, 1)
        dgrid.addWidget(QLabel("Стартовая карта:"), 0, 2)
        self.map_edit = QLineEdit()
        dgrid.addWidget(self.map_edit, 0, 3)
        dgrid.addWidget(QLabel("Параметры запуска:"), 1, 0)
        self.args_edit = QLineEdit()
        dgrid.addWidget(self.args_edit, 1, 1, 1, 3)
        defaults.add_layout(dgrid)
        layout.addWidget(defaults)

        # --- автоматизация ---
        auto = Card("Автоматизация")
        self.auto_update_check = QCheckBox("Автообновление сервера перед запуском "
                                           "(app_update 730)")
        auto.add(self.auto_update_check)
        notif = QCheckBox("Уведомления о событиях (TODO)")
        notif.setEnabled(False)  # TODO: реализация уведомлений
        auto.add(notif)
        auto.add(QLabel("Расписание автобэкапов настраивается на странице «Бэкапы»."))
        layout.addWidget(auto)

        # --- быстрые команды и карты ---
        row = QHBoxLayout()
        quick = Card("Быстрые команды консоли (по одной в строке)")
        self.quick_edit = QPlainTextEdit()
        self.quick_edit.setMaximumHeight(140)
        quick.add(self.quick_edit)
        row.addWidget(quick)
        favs = Card("Избранные карты (по одной в строке)")
        self.favs_edit = QPlainTextEdit()
        self.favs_edit.setMaximumHeight(140)
        favs.add(self.favs_edit)
        row.addWidget(favs)
        layout.addLayout(row)

        # --- кнопки ---
        buttons = QHBoxLayout()
        buttons.addWidget(make_button("💾 Сохранить настройки", "Primary", self._save))
        buttons.addWidget(make_button("↩ Сбросить к значениям по умолчанию", "Danger",
                                      self._reset))
        buttons.addWidget(make_button("⤒ Экспорт настроек", on_click=self._export))
        buttons.addWidget(make_button("⤓ Импорт настроек", on_click=self._import))
        buttons.addStretch(1)
        layout.addLayout(buttons)
        layout.addStretch(1)

        self.load()

    # ------------------------------------------------------------- данные

    def load(self) -> None:
        s = self.ctx.settings
        self.steamcmd_edit.setText(s.get("paths.steamcmd", ""))
        self.backups_edit.setText(s.get("paths.backups", ""))
        self.port_spin.setValue(int(s.get("server_defaults.port", 27015)))
        self.map_edit.setText(s.get("server_defaults.start_map", "de_dust2"))
        self.args_edit.setText(s.get("server_defaults.launch_args", ""))
        self.auto_update_check.setChecked(s.get("automation.auto_update_on_start", False))
        self.quick_edit.setPlainText("\n".join(s.get("quick_commands", [])))
        self.favs_edit.setPlainText("\n".join(s.get("favorite_maps", [])))

    def _browse(self, edit: QLineEdit) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Выбор папки")
        if folder:
            edit.setText(folder)

    # ----------------------------------------------------------- действия

    def _save(self) -> None:
        s = self.ctx.settings
        s.set("paths.steamcmd", self.steamcmd_edit.text().strip(), save=False)
        s.set("paths.backups", self.backups_edit.text().strip(), save=False)
        s.set("server_defaults.port", self.port_spin.value(), save=False)
        s.set("server_defaults.start_map", self.map_edit.text().strip() or "de_dust2",
              save=False)
        s.set("server_defaults.launch_args", self.args_edit.text().strip(), save=False)
        s.set("automation.auto_update_on_start", self.auto_update_check.isChecked(),
              save=False)
        s.set("quick_commands",
              [c.strip() for c in self.quick_edit.toPlainText().splitlines() if c.strip()],
              save=False)
        s.set("favorite_maps",
              [m.strip() for m in self.favs_edit.toPlainText().splitlines() if m.strip()])
        show_info(self, "Настройки", "Настройки сохранены.")

    def _reset(self) -> None:
        if not confirm(self, "Сброс", "Сбросить ВСЕ настройки приложения к значениям "
                       "по умолчанию? (профили не трогаем)", danger=True):
            return
        self.ctx.settings.reset()
        self.load()
        self.ctx.apply_theme()
        show_info(self, "Настройки", "Настройки сброшены.")

    def _export(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Экспорт настроек",
                                              "steamcmdv2_settings.json", "JSON (*.json)")
        if not path:
            return
        try:
            self.ctx.settings.export_to(Path(path))
            show_info(self, "Экспорт", f"Сохранено: {path}")
        except OSError as exc:
            show_error(self, "Экспорт", str(exc))

    def _import(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Импорт настроек", "", "JSON (*.json)")
        if not path:
            return
        try:
            data = json.loads(Path(path).read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                raise ValueError("Файл не похож на настройки SteamCMD v2")
            self.ctx.settings.import_from(Path(path))
            self.load()
            self.ctx.apply_theme()
            show_info(self, "Импорт", "Настройки импортированы и применены.")
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            show_error(self, "Импорт", str(exc))

    def on_show(self) -> None:
        self.load()
