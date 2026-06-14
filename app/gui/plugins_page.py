"""Менеджер плагинов (CounterStrikeSharp / Metamod)."""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

from PySide6.QtWidgets import (QFileDialog, QHBoxLayout, QLabel, QPlainTextEdit,
                               QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget)

from app.core.plugin_manager import PluginManager
from app.gui.widgets import (Card, Worker, confirm, make_button, page_header,
                             show_error, show_info)
from app.models.plugin import Plugin

COLUMNS = ["Название", "Версия", "Тип", "Статус", "Путь"]


class PluginsPage(QWidget):
    def __init__(self, ctx) -> None:
        super().__init__()
        self.ctx = ctx
        self.setObjectName("Page")
        self._plugins: list[Plugin] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)
        layout.addWidget(page_header("Плагины",
                                     "Установленные плагины CounterStrikeSharp и Metamod"))

        controls = QHBoxLayout()
        controls.addWidget(make_button("⟳ Обновить список", "Primary", self.refresh))
        controls.addWidget(make_button("📦 Установить из ZIP", on_click=self._install_zip))
        self.toggle_btn = make_button("Вкл/Выкл", on_click=self._toggle)
        controls.addWidget(self.toggle_btn)
        controls.addWidget(make_button("📂 Открыть папку плагина", on_click=self._open_folder))
        controls.addWidget(make_button("🗑 Удалить", "Danger", self._delete))
        catalog_btn = make_button("🛒 Открыть каталог", enabled=False)
        catalog_btn.setToolTip("TODO: интеграция с онлайн-каталогом плагинов")
        controls.addWidget(catalog_btn)  # TODO: интеграция с онлайн-каталогом
        controls.addStretch(1)
        layout.addLayout(controls)

        body = QHBoxLayout()
        table_card = Card()
        self.table = QTableWidget(0, len(COLUMNS))
        self.table.setHorizontalHeaderLabels(COLUMNS)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setColumnWidth(0, 200)
        self.table.setMinimumHeight(380)
        self.table.itemSelectionChanged.connect(self._show_details)
        table_card.add(self.table)
        body.addWidget(table_card, 3)

        info_card = Card("Информация о плагине")
        self.info_label = QLabel("Выберите плагин в списке")
        self.info_label.setWordWrap(True)
        info_card.add(self.info_label)
        errors_label = QLabel("ОШИБКИ ИЗ ЛОГА")
        errors_label.setObjectName("CardTitle")
        info_card.add(errors_label)
        self.errors_box = QPlainTextEdit()
        self.errors_box.setObjectName("Console")
        self.errors_box.setReadOnly(True)
        info_card.add(self.errors_box)
        body.addWidget(info_card, 2)
        layout.addLayout(body)
        layout.addStretch(1)

        self.ctx.profile_changed.connect(lambda _: self.refresh())

    # ------------------------------------------------------------ helpers

    def _manager(self) -> PluginManager | None:
        profile = self.ctx.active_profile
        return PluginManager(profile.server_path) if profile else None

    def _selected(self) -> Plugin | None:
        row = self.table.currentRow()
        if 0 <= row < len(self._plugins):
            return self._plugins[row]
        return None

    # ------------------------------------------------------------- данные

    def refresh(self) -> None:
        manager = self._manager()
        if manager is None:
            self.table.setRowCount(0)
            return

        def done(plugins: list) -> None:
            self._plugins = plugins
            self.table.setRowCount(len(plugins))
            for row, plugin in enumerate(plugins):
                values = [plugin.name, plugin.version or "—", plugin.plugin_type,
                          "Включён" if plugin.enabled else "Отключён", plugin.folder_path]
                for col, value in enumerate(values):
                    self.table.setItem(row, col, QTableWidgetItem(value))

        self._worker = Worker(manager.list_plugins)
        self._worker.finished_ok.connect(done)
        self._worker.failed.connect(lambda err: show_error(self, "Плагины", err))
        self._worker.start()

    def _show_details(self) -> None:
        plugin = self._selected()
        manager = self._manager()
        if plugin is None or manager is None:
            return
        self.info_label.setText(
            f"<b>{plugin.name}</b><br>Версия: {plugin.version or '—'}<br>"
            f"Тип: {plugin.plugin_type}<br>"
            f"Статус: {'Включён' if plugin.enabled else 'Отключён'}<br>"
            f"{plugin.description or ''}")
        errors = manager.get_plugin_errors(plugin)
        self.errors_box.setPlainText("\n".join(errors) if errors else "Ошибок не найдено")

    # ----------------------------------------------------------- действия

    def _install_zip(self) -> None:
        manager = self._manager()
        if manager is None:
            show_error(self, "Плагины", "Нет активного профиля.")
            return
        path, _ = QFileDialog.getOpenFileName(self, "ZIP с плагином", "", "ZIP (*.zip)")
        if not path:
            return
        self._install_worker = Worker(manager.install_from_zip, path)
        self._install_worker.finished_ok.connect(
            lambda p: (show_info(self, "Плагины", f"Установлен: {p.name}"), self.refresh()))
        self._install_worker.failed.connect(lambda err: show_error(self, "Установка", err))
        self._install_worker.start()

    def _toggle(self) -> None:
        plugin = self._selected()
        manager = self._manager()
        if plugin is None or manager is None:
            return
        if plugin.plugin_type != "CounterStrikeSharp":
            show_info(self, "Плагины",
                      "Вкл/выкл доступно только для CounterStrikeSharp-плагинов.")
            return
        manager.set_enabled(plugin, not plugin.enabled)
        self.refresh()

    def _delete(self) -> None:
        plugin = self._selected()
        manager = self._manager()
        if plugin is None or manager is None:
            return
        if not confirm(self, "Удаление", f"Удалить плагин {plugin.name}? Папка будет стёрта.",
                       danger=True):
            return
        if manager.delete(plugin):
            self.refresh()
        else:
            show_error(self, "Удаление", "Этот плагин нельзя удалить отсюда.")

    def _open_folder(self) -> None:
        plugin = self._selected()
        if plugin is None:
            return
        path = Path(plugin.folder_path)
        if os.name == "nt":
            os.startfile(str(path))  # noqa: S606
        else:
            subprocess.Popen(["xdg-open", str(path)])  # noqa: S603,S607

    def on_show(self) -> None:
        self.refresh()
