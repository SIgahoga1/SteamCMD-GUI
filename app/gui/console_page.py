"""Встроенная консоль: stdout сервера, команды RCON/stdin, фильтры и поиск."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QTextCharFormat, QTextCursor
from PySide6.QtWidgets import (QCheckBox, QComboBox, QFileDialog, QHBoxLayout,
                               QLineEdit, QPlainTextEdit, QVBoxLayout, QWidget)

from app.core.rcon_client import RCONError
from app.gui.widgets import Card, make_button, page_header, show_error

MAX_LINES = 5000

LEVEL_COLORS = {
    "ERROR": QColor("#ff4141"),
    "WARNING": QColor("#ffaa00"),
}


def classify(line: str) -> str:
    low = line.lower()
    if any(tok in low for tok in ("error", "exception", "failed", "critical", "[ошибка]")):
        return "ERROR"
    if any(tok in low for tok in ("warning", "warn", "deprecated")):
        return "WARNING"
    return "INFO"


class ConsolePage(QWidget):
    def __init__(self, ctx) -> None:
        super().__init__()
        self.ctx = ctx
        self.setObjectName("Page")
        self._lines: list[tuple[str, str]] = []  # (level, text)
        self._history: list[str] = []
        self._history_pos = 0

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)
        layout.addWidget(page_header("Консоль", "Вывод сервера в реальном времени + RCON"))

        tools = QHBoxLayout()
        self.filter_combo = QComboBox()
        self.filter_combo.addItems(["All", "INFO", "WARNING", "ERROR"])
        self.filter_combo.currentTextChanged.connect(lambda _: self._rerender())
        tools.addWidget(self.filter_combo)
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Поиск по логу…")
        self.search_edit.textChanged.connect(lambda _: self._rerender())
        tools.addWidget(self.search_edit, 1)
        self.autoscroll_check = QCheckBox("Автопрокрутка")
        self.autoscroll_check.setChecked(True)
        tools.addWidget(self.autoscroll_check)
        tools.addWidget(make_button("Очистить", on_click=self._clear))
        tools.addWidget(make_button("Сохранить в файл", on_click=self._save))
        layout.addLayout(tools)

        card = Card()
        self.console = QPlainTextEdit()
        self.console.setObjectName("Console")
        self.console.setReadOnly(True)
        self.console.setMinimumHeight(380)
        self.console.setMaximumBlockCount(MAX_LINES)
        card.add(self.console)
        layout.addWidget(card)

        # быстрые команды
        quick = QHBoxLayout()
        for cmd in self.ctx.settings.get("quick_commands", []):
            quick.addWidget(make_button(cmd, on_click=lambda c=cmd: self._send_command(c)))
        quick.addStretch(1)
        layout.addLayout(quick)

        # ввод команды
        input_row = QHBoxLayout()
        self.cmd_edit = QLineEdit()
        self.cmd_edit.setPlaceholderText("Команда серверу (Enter — отправить, ↑/↓ — история)")
        self.cmd_edit.returnPressed.connect(self._send_from_input)
        self.cmd_edit.installEventFilter(self)
        input_row.addWidget(self.cmd_edit, 1)
        input_row.addWidget(make_button("Отправить", "Primary", self._send_from_input))
        layout.addLayout(input_row)

        self.ctx.server_manager_changed.connect(self._attach_manager)
        self._attach_manager(self.ctx.server_manager)

    # --------------------------------------------------------------- ввод

    def eventFilter(self, obj, event) -> bool:  # noqa: N802
        if obj is self.cmd_edit and event.type() == event.Type.KeyPress:
            if event.key() == Qt.Key.Key_Up and self._history:
                self._history_pos = max(0, self._history_pos - 1)
                self.cmd_edit.setText(self._history[self._history_pos])
                return True
            if event.key() == Qt.Key.Key_Down and self._history:
                self._history_pos = min(len(self._history), self._history_pos + 1)
                self.cmd_edit.setText(
                    self._history[self._history_pos] if self._history_pos < len(self._history)
                    else "")
                return True
        return super().eventFilter(obj, event)

    def _send_from_input(self) -> None:
        command = self.cmd_edit.text().strip()
        if not command:
            return
        self.cmd_edit.clear()
        self._history.append(command)
        self._history_pos = len(self._history)
        self._send_command(command)

    def _send_command(self, command: str) -> None:
        self._append_line(f"> {command}", "INFO")
        try:
            response = self.ctx.send_console_command(command)
            if response:
                for line in response.splitlines():
                    self._append_line(line, classify(line))
        except RCONError as exc:
            self._append_line(f"[ОШИБКА] {exc}", "ERROR")

    # -------------------------------------------------------------- вывод

    def _attach_manager(self, manager) -> None:
        if manager is not None:
            manager.output_line.connect(self._on_server_line)

    def _on_server_line(self, line: str) -> None:
        self._append_line(line, classify(line))

    def _append_line(self, text: str, level: str) -> None:
        self._lines.append((level, text))
        if len(self._lines) > MAX_LINES:
            self._lines = self._lines[-MAX_LINES:]
        if self._passes_filter(level, text):
            self._write(text, level)

    def _passes_filter(self, level: str, text: str) -> bool:
        flt = self.filter_combo.currentText()
        if flt != "All" and level != flt:
            return False
        needle = self.search_edit.text().strip().lower()
        return not needle or needle in text.lower()

    def _write(self, text: str, level: str) -> None:
        cursor = self.console.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        fmt = QTextCharFormat()
        if level in LEVEL_COLORS:
            fmt.setForeground(LEVEL_COLORS[level])
        cursor.insertText(text + "\n", fmt)
        if self.autoscroll_check.isChecked():
            sb = self.console.verticalScrollBar()
            sb.setValue(sb.maximum())

    def _rerender(self) -> None:
        self.console.clear()
        for level, text in self._lines:
            if self._passes_filter(level, text):
                self._write(text, level)

    def _clear(self) -> None:
        self._lines.clear()
        self.console.clear()

    def _save(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Сохранить лог", "console.log",
                                              "Логи (*.log *.txt)")
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write("\n".join(text for _, text in self._lines))
        except OSError as exc:
            show_error(self, "Сохранение", str(exc))

    def on_show(self) -> None:
        pass
