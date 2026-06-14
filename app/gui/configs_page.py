"""Редактор конфигов с подсветкой и шаблонами."""
from __future__ import annotations

import re
from pathlib import Path

from PySide6.QtCore import QRegularExpression
from PySide6.QtGui import (QColor, QFont, QSyntaxHighlighter, QTextCharFormat)
from PySide6.QtWidgets import (QComboBox, QHBoxLayout, QInputDialog, QListWidget,
                               QPlainTextEdit, QVBoxLayout, QWidget)

from app.core.config_manager import TEMPLATES, ConfigManager
from app.core.rcon_client import RCONError
from app.gui.widgets import (Card, Worker, confirm, make_button, page_header,
                             show_error, show_info)


class CfgHighlighter(QSyntaxHighlighter):
    """Подсветка: // комментарии — серые, значения в кавычках — зелёные."""

    def __init__(self, document, accent: str = "#00ff41") -> None:
        super().__init__(document)
        self.comment_fmt = QTextCharFormat()
        self.comment_fmt.setForeground(QColor("#6a8a6a"))
        self.comment_fmt.setFontItalic(True)
        self.value_fmt = QTextCharFormat()
        self.value_fmt.setForeground(QColor(accent))
        self.cvar_fmt = QTextCharFormat()
        self.cvar_fmt.setForeground(QColor("#9ecbff"))
        self.cvar_fmt.setFontWeight(QFont.Weight.Bold)

    def highlightBlock(self, text: str) -> None:  # noqa: N802
        m = re.match(r"^\s*([A-Za-z_][\w]*)", text)
        if m and not text.lstrip().startswith("//"):
            self.setFormat(m.start(1), m.end(1) - m.start(1), self.cvar_fmt)
        it = QRegularExpression('"[^"]*"').globalMatch(text)
        while it.hasNext():
            match = it.next()
            self.setFormat(match.capturedStart(), match.capturedLength(), self.value_fmt)
        idx = text.find("//")
        if idx >= 0:
            self.setFormat(idx, len(text) - idx, self.comment_fmt)


class ConfigsPage(QWidget):
    def __init__(self, ctx) -> None:
        super().__init__()
        self.ctx = ctx
        self.setObjectName("Page")
        self._current: Path | None = None
        self._original = ""

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)
        layout.addWidget(page_header("Конфиги", "Файлы game/csgo/cfg/*.cfg"))

        body = QHBoxLayout()
        list_card = Card("Файлы")
        self.file_list = QListWidget()
        self.file_list.setMinimumWidth(240)
        self.file_list.currentTextChanged.connect(self._load_file)
        list_card.add(self.file_list)
        tpl_row = QHBoxLayout()
        self.template_combo = QComboBox()
        self.template_combo.addItems(list(TEMPLATES.keys()))
        tpl_row.addWidget(self.template_combo, 1)
        list_card.add_layout(tpl_row)
        list_card.add(make_button("Создать из шаблона", on_click=self._create_from_template))
        body.addWidget(list_card, 1)

        editor_card = Card("Редактор")
        self.editor = QPlainTextEdit()
        self.editor.setObjectName("Console")
        self.editor.setMinimumHeight(420)
        accent = self.ctx.settings.get("ui.accent_color", "#00ff41")
        self._highlighter = CfgHighlighter(self.editor.document(), accent)
        editor_card.add(self.editor)
        btn_row = QHBoxLayout()
        btn_row.addWidget(make_button("💾 Сохранить", "Primary", self._save))
        btn_row.addWidget(make_button("💾 Сохранить и перезапустить сервер", "Warning",
                                      self._save_restart))
        btn_row.addWidget(make_button("↩ Сбросить изменения", on_click=self._revert))
        btn_row.addStretch(1)
        editor_card.add_layout(btn_row)
        body.addWidget(editor_card, 3)
        layout.addLayout(body)
        layout.addStretch(1)

        self.ctx.profile_changed.connect(lambda _: self.refresh())
        self.refresh()

    # ------------------------------------------------------------ helpers

    def _manager(self) -> ConfigManager | None:
        profile = self.ctx.active_profile
        return ConfigManager(profile.server_path) if profile else None

    def refresh(self) -> None:
        manager = self._manager()
        self.file_list.clear()
        self._current = None
        self.editor.clear()
        if manager is None:
            return
        for path in manager.list_configs():
            self.file_list.addItem(path.name)

    def _load_file(self, name: str) -> None:
        manager = self._manager()
        if manager is None or not name:
            return
        path = manager.cfg_dir / name
        try:
            self._original = manager.read(path)
            self._current = path
            self.editor.setPlainText(self._original)
        except OSError as exc:
            show_error(self, "Конфиги", str(exc))

    # ----------------------------------------------------------- действия

    def _save(self) -> bool:
        manager = self._manager()
        if manager is None or self._current is None:
            show_info(self, "Конфиги", "Сначала выберите файл.")
            return False
        try:
            manager.write(self._current, self.editor.toPlainText())
            self._original = self.editor.toPlainText()
            show_info(self, "Конфиги", f"Сохранено: {self._current.name} (+ .bak копия)")
            return True
        except OSError as exc:
            show_error(self, "Конфиги", str(exc))
            return False

    def _save_restart(self) -> None:
        if not self._save():
            return
        if self.ctx.server_manager and self.ctx.server_manager.is_running():
            if confirm(self, "Перезапуск", "Перезапустить сервер сейчас?", danger=True):
                self._worker = Worker(self.ctx.server_manager.restart)
                self._worker.start()
        else:
            show_info(self, "Перезапуск", "Сервер не запущен — конфиг применится при старте.")

    def _revert(self) -> None:
        if self._current is not None:
            self.editor.setPlainText(self._original)

    def _create_from_template(self) -> None:
        manager = self._manager()
        if manager is None:
            show_error(self, "Конфиги", "Нет активного профиля.")
            return
        template = self.template_combo.currentText()
        default_name = "server.cfg" if template != "Custom" else "custom.cfg"
        name, ok = QInputDialog.getText(self, "Новый конфиг",
                                        "Имя файла:", text=default_name)
        if not ok or not name.strip():
            return
        profile = self.ctx.active_profile
        try:
            path = manager.create_from_template(
                template, name.strip(),
                hostname=profile.name if profile else "CS2 Server",
                rcon_password=profile.rcon_password if profile else "")
            self.refresh()
            show_info(self, "Конфиги", f"Создан: {path.name}")
        except (OSError, KeyError) as exc:
            show_error(self, "Конфиги", str(exc))

    def on_show(self) -> None:
        if self._current is None:
            self.refresh()
