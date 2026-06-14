"""Просмотр логов: сервер, приложение, ошибки компонентов + диагностика."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (QComboBox, QFileDialog, QHBoxLayout, QLineEdit,
                               QPlainTextEdit, QTabWidget, QVBoxLayout, QWidget)

from app.gui.widgets import Card, Worker, make_button, page_header, show_error, show_info
from app.services import diagnostics
from app.services.logger import AppLogger

MAX_SHOW = 3000


class LogView(QWidget):
    """Одна вкладка: фильтр + поиск + текст."""

    def __init__(self) -> None:
        super().__init__()
        self._lines: list[str] = []
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 6, 0, 0)
        tools = QHBoxLayout()
        self.filter_combo = QComboBox()
        self.filter_combo.addItems(["All", "INFO", "WARNING", "ERROR"])
        self.filter_combo.currentTextChanged.connect(lambda _: self.render())
        tools.addWidget(self.filter_combo)
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Поиск…")
        self.search_edit.textChanged.connect(lambda _: self.render())
        tools.addWidget(self.search_edit, 1)
        layout.addLayout(tools)
        self.text = QPlainTextEdit()
        self.text.setObjectName("Console")
        self.text.setReadOnly(True)
        self.text.setMinimumHeight(360)
        layout.addWidget(self.text)

    def set_lines(self, lines: list[str]) -> None:
        self._lines = lines[-MAX_SHOW:]
        self.render()

    def render(self) -> None:
        flt = self.filter_combo.currentText()
        needle = self.search_edit.text().strip().lower()
        out = []
        for line in self._lines:
            low = line.lower()
            if flt == "ERROR" and not any(t in low for t in ("error", "exception", "failed")):
                continue
            if flt == "WARNING" and "warn" not in low:
                continue
            if flt == "INFO" and any(t in low for t in ("error", "exception", "warn")):
                continue
            if needle and needle not in low:
                continue
            out.append(line)
        self.text.setPlainText("\n".join(out))
        sb = self.text.verticalScrollBar()
        sb.setValue(sb.maximum())

    def current_text(self) -> str:
        return self.text.toPlainText()


class LogsPage(QWidget):
    def __init__(self, ctx) -> None:
        super().__init__()
        self.ctx = ctx
        self.setObjectName("Page")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)
        layout.addWidget(page_header("Логи", "Логи сервера, приложения и компонентов"))

        controls = QHBoxLayout()
        controls.addWidget(make_button("⟳ Обновить", "Primary", self.refresh))
        controls.addWidget(make_button("⤒ Экспорт текущей вкладки", on_click=self._export))
        controls.addWidget(make_button("🩺 Диагностический отчёт", "Warning", self._diagnostics))
        controls.addStretch(1)
        layout.addLayout(controls)

        card = Card()
        self.tabs = QTabWidget()
        self.server_view = LogView()
        self.app_view = LogView()
        self.components_view = LogView()
        self.tabs.addTab(self.server_view, "Логи сервера")
        self.tabs.addTab(self.app_view, "app.log")
        self.tabs.addTab(self.components_view, "Ошибки компонентов")
        card.add(self.tabs)
        layout.addWidget(card)
        layout.addStretch(1)

    # ------------------------------------------------------------- данные

    def refresh(self) -> None:
        # app.log
        try:
            log_file = AppLogger.log_file()
            app_lines = (log_file.read_text(encoding="utf-8", errors="replace").splitlines()
                         if log_file.exists() else ["app.log пока пуст"])
        except OSError as exc:
            app_lines = [f"Не удалось прочитать app.log: {exc}"]
        self.app_view.set_lines(app_lines)

        profile = self.ctx.active_profile
        if profile is None:
            self.server_view.set_lines(["Нет активного профиля"])
            self.components_view.set_lines(["Нет активного профиля"])
            return

        def job():
            root = Path(profile.server_path)
            server_lines: list[str] = []
            logs_dir = root / "game" / "csgo" / "logs"
            if logs_dir.is_dir():
                files = sorted(logs_dir.glob("*.txt"), key=lambda p: p.stat().st_mtime)
                files += sorted(logs_dir.glob("*.log"), key=lambda p: p.stat().st_mtime)
                if files:
                    newest = files[-1]
                    server_lines.append(f"=== {newest} ===")
                    server_lines += newest.read_text(
                        encoding="utf-8", errors="replace").splitlines()[-MAX_SHOW:]
            console_log = root / "game" / "csgo" / "console.log"
            if console_log.is_file():
                server_lines.append(f"=== {console_log} ===")
                server_lines += console_log.read_text(
                    encoding="utf-8", errors="replace").splitlines()[-MAX_SHOW:]
            if not server_lines:
                server_lines = ["Файлы логов сервера не найдены "
                                "(game/csgo/logs/, console.log)"]

            comp_lines: list[str] = []
            for rel, label in [
                ("game/csgo/addons/counterstrikesharp/logs", "CounterStrikeSharp"),
                ("game/csgo/addons/metamod/logs", "Metamod"),
            ]:
                folder = root / rel
                if folder.is_dir():
                    files = sorted(folder.glob("*"), key=lambda p: p.stat().st_mtime)
                    if files:
                        comp_lines.append(f"=== {label}: {files[-1].name} ===")
                        comp_lines += files[-1].read_text(
                            encoding="utf-8", errors="replace").splitlines()[-500:]
            if not comp_lines:
                comp_lines = ["Логи Metamod/CounterStrikeSharp не найдены"]
            return server_lines, comp_lines

        def done(result) -> None:
            server_lines, comp_lines = result
            self.server_view.set_lines(server_lines)
            self.components_view.set_lines(comp_lines)

        self._worker = Worker(job)
        self._worker.finished_ok.connect(done)
        self._worker.failed.connect(lambda err: self.server_view.set_lines([f"Ошибка: {err}"]))
        self._worker.start()

    # ----------------------------------------------------------- действия

    def _current_view(self) -> LogView:
        return self.tabs.currentWidget()  # type: ignore[return-value]

    def _export(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Экспорт лога", "log_export.txt",
                                              "Текст (*.txt *.log)")
        if not path:
            return
        try:
            Path(path).write_text(self._current_view().current_text(), encoding="utf-8")
            show_info(self, "Экспорт", f"Сохранено: {path}")
        except OSError as exc:
            show_error(self, "Экспорт", str(exc))

    def _diagnostics(self) -> None:
        profile = self.ctx.active_profile

        def job():
            report = diagnostics.generate_report(self.ctx.settings, profile)
            return diagnostics.export_report(report)

        self._diag_worker = Worker(job)
        self._diag_worker.finished_ok.connect(
            lambda p: show_info(self, "Диагностика", f"Отчёт сохранён:\n{p}"))
        self._diag_worker.failed.connect(lambda err: show_error(self, "Диагностика", err))
        self._diag_worker.start()

    def on_show(self) -> None:
        self.refresh()
