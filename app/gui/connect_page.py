"""Подключение существующего сервера: сканирование папки + создание профиля."""
from __future__ import annotations

from PySide6.QtWidgets import (QFileDialog, QHBoxLayout, QLabel, QLineEdit,
                               QPlainTextEdit, QSpinBox, QVBoxLayout, QWidget)

from app.core.server_scanner import ScanResult, scan_server_folder
from app.gui.widgets import Card, Worker, make_button, page_header, show_error
from app.models.server_profile import ServerProfile


class ConnectPage(QWidget):
    def __init__(self, ctx) -> None:
        super().__init__()
        self.ctx = ctx
        self.setObjectName("Page")
        self._scan: ScanResult | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)
        layout.addWidget(page_header("Подключить существующий сервер",
                                     "Выберите папку с установленным CS2 Dedicated Server — "
                                     "приложение проверит её и добавит профиль."))

        pick = Card("Папка сервера")
        row = QHBoxLayout()
        self.path_edit = QLineEdit()
        self.path_edit.setPlaceholderText(r"Например: C:\cs2-server")
        row.addWidget(self.path_edit, 1)
        row.addWidget(make_button("Обзор…", on_click=self._browse))
        self.scan_btn = make_button("Сканировать", "Primary", self._start_scan)
        row.addWidget(self.scan_btn)
        pick.add_layout(row)
        layout.addWidget(pick)

        report_card = Card("Отчёт сканирования")
        self.report = QPlainTextEdit()
        self.report.setObjectName("Console")
        self.report.setReadOnly(True)
        self.report.setMinimumHeight(220)
        self.report.setPlainText("Выберите папку и нажмите «Сканировать».")
        report_card.add(self.report)
        layout.addWidget(report_card)

        save_card = Card("Профиль")
        form = QHBoxLayout()
        form.addWidget(QLabel("Название:"))
        self.name_edit = QLineEdit("Мой CS2 сервер")
        form.addWidget(self.name_edit, 1)
        form.addWidget(QLabel("Порт:"))
        self.port_spin = QSpinBox()
        self.port_spin.setRange(1024, 65535)
        self.port_spin.setValue(27015)
        form.addWidget(self.port_spin)
        form.addWidget(QLabel("RCON пароль:"))
        self.rcon_edit = QLineEdit()
        form.addWidget(self.rcon_edit, 1)
        save_card.add_layout(form)
        self.save_btn = make_button("Сохранить профиль и открыть Dashboard", "Primary",
                                    self._save_profile, enabled=False)
        save_card.add(self.save_btn)
        layout.addWidget(save_card)
        layout.addStretch(1)

    def _browse(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Папка сервера CS2")
        if folder:
            self.path_edit.setText(folder)

    def _start_scan(self) -> None:
        folder = self.path_edit.text().strip()
        if not folder:
            show_error(self, "Сканирование", "Укажите папку сервера.")
            return
        self.scan_btn.setEnabled(False)
        self.report.setPlainText("Сканирование…")
        self._worker = Worker(scan_server_folder, folder)
        self._worker.finished_ok.connect(self._on_scanned)
        self._worker.failed.connect(lambda err: (self.scan_btn.setEnabled(True),
                                                 show_error(self, "Сканирование", err)))
        self._worker.start()

    def _on_scanned(self, result: ScanResult) -> None:
        self.scan_btn.setEnabled(True)
        self._scan = result
        lines = []
        lines.append(f"Статус: {'✔ СЕРВЕР НАЙДЕН' if result.ok else '✖ СЕРВЕР НЕ НАЙДЕН'}")
        lines.append(f"Путь: {result.server_path}")
        if result.exe_path:
            lines.append(f"Исполняемый файл: {result.exe_path}")
        lines.append("")
        lines.append("Компоненты:")
        for name, info in result.components.items():
            mark = "✔" if info.get("installed") else "✖"
            version = f" (v{info['version']})" if info.get("version") else ""
            lines.append(f"  {mark} {name}{version}")
        if result.plugins:
            lines.append("")
            lines.append(f"Плагины ({len(result.plugins)}): " + ", ".join(result.plugins))
        if result.configs:
            lines.append("")
            lines.append(f"Конфиги ({len(result.configs)}): " + ", ".join(result.configs[:15]) +
                         (" …" if len(result.configs) > 15 else ""))
        if result.maps:
            lines.append("")
            lines.append(f"Карты ({len(result.maps)}): " + ", ".join(result.maps[:15]) +
                         (" …" if len(result.maps) > 15 else ""))
        if result.warnings:
            lines.append("")
            lines.append("⚠ Предупреждения:")
            lines.extend(f"  • {warning}" for warning in result.warnings)
        if result.recommendations:
            lines.append("")
            lines.append("💡 Рекомендации:")
            lines.extend(f"  • {rec}" for rec in result.recommendations)
        self.report.setPlainText("\n".join(lines))

        if result.ok:
            if result.rcon_password:
                self.rcon_edit.setText(result.rcon_password)
            if result.port_hint:
                self.port_spin.setValue(result.port_hint)
        self.save_btn.setEnabled(result.ok)

    def _save_profile(self) -> None:
        if not self._scan or not self._scan.ok:
            return
        defaults = self.ctx.settings.get("server_defaults", {})
        profile = ServerProfile(
            name=self.name_edit.text().strip() or "CS2 Server",
            server_path=self._scan.server_path,
            port=self.port_spin.value(),
            start_map=defaults.get("start_map", "de_dust2"),
            launch_args=defaults.get("launch_args",
                                     "-dedicated -usercon +game_type 0 +game_mode 1"),
            rcon_password=self.rcon_edit.text().strip(),
            description="Импортирован из существующей папки",
        )
        self.ctx.profiles.add(profile)
        self.ctx.set_active_profile(profile)
        self.ctx.show_page("dashboard")

    def on_show(self) -> None:
        pass
