"""Управление сервером: параметры запуска, карта, конфиги, обслуживание."""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (QComboBox, QHBoxLayout, QLabel, QLineEdit,
                               QPlainTextEdit, QVBoxLayout, QWidget)

from app.core.config_manager import ConfigManager
from app.core.map_manager import MapManager
from app.core.rcon_client import RCONError
from app.core.steamcmd_manager import SteamCMDManager
from app.gui.widgets import (Card, Worker, make_button, page_header, show_error,
                             show_info)
from app.services.logger import AppLogger


class ServerPage(QWidget):
    def __init__(self, ctx) -> None:
        super().__init__()
        self.ctx = ctx
        self.setObjectName("Page")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)
        layout.addWidget(page_header("Управление сервером"))

        # --- запуск ---
        launch = Card("Запуск")
        layout_args = QHBoxLayout()
        layout_args.addWidget(QLabel("Параметры:"))
        self.args_edit = QLineEdit()
        self.args_edit.setPlaceholderText("-dedicated -usercon +game_type 0 +game_mode 1")
        layout_args.addWidget(self.args_edit, 1)
        layout_args.addWidget(make_button("Сохранить", on_click=self._save_args))
        launch.add_layout(layout_args)
        buttons = QHBoxLayout()
        self.start_btn = make_button("▶ Запустить", "Primary", self._start)
        self.stop_btn = make_button("■ Остановить", "Danger", self._stop)
        self.restart_btn = make_button("↺ Перезапустить", "Warning", self._restart)
        for btn in (self.start_btn, self.stop_btn, self.restart_btn):
            buttons.addWidget(btn)
        buttons.addStretch(1)
        launch.add_layout(buttons)
        layout.addWidget(launch)

        middle = QHBoxLayout()

        # --- карта ---
        map_card = Card("Смена карты")
        self.map_combo = QComboBox()
        self.map_combo.setEditable(True)
        map_card.add(self.map_combo)
        map_card.add(make_button("Сменить карту (RCON changelevel)", on_click=self._change_map))
        middle.addWidget(map_card)

        # --- конфиг ---
        cfg_card = Card("Применить конфиг")
        self.cfg_combo = QComboBox()
        cfg_card.add(self.cfg_combo)
        cfg_card.add(make_button("Применить (RCON exec)", on_click=self._exec_config))
        middle.addWidget(cfg_card)

        # --- обслуживание ---
        maint = Card("Обслуживание")
        maint.add(make_button("✓ Проверить файлы (validate)",
                              on_click=lambda: self._steamcmd_job(validate=True)))
        maint.add(make_button("⬆ Обновить сервер (app_update)",
                              on_click=lambda: self._steamcmd_job(validate=False)))
        maint.add(make_button("📂 Открыть папку сервера", on_click=self._open_folder))
        middle.addWidget(maint)
        layout.addLayout(middle)

        # --- инфо о процессе ---
        info_card = Card("Процесс сервера")
        self.proc_label = QLabel("—")
        info_card.add(self.proc_label)
        layout.addWidget(info_card)

        # --- вывод обслуживания ---
        out_card = Card("Вывод SteamCMD")
        self.output = QPlainTextEdit()
        self.output.setObjectName("Console")
        self.output.setReadOnly(True)
        self.output.setMinimumHeight(160)
        out_card.add(self.output)
        layout.addWidget(out_card)
        layout.addStretch(1)

        self._timer = QTimer(self)
        self._timer.setInterval(2000)
        self._timer.timeout.connect(self._tick)
        self._timer.start()

        self.ctx.profile_changed.connect(lambda _: self.refresh())
        self.refresh()

    # ------------------------------------------------------------ данные

    def refresh(self) -> None:
        profile = self.ctx.active_profile
        if profile is None:
            self.args_edit.setText("")
            return
        self.args_edit.setText(profile.launch_args)
        manager = MapManager(profile.server_path)
        custom = self.ctx.settings.get("custom_maps", [])
        favorites = self.ctx.settings.get("favorite_maps", [])
        maps = list(dict.fromkeys(favorites + manager.all_maps(custom)))
        self.map_combo.clear()
        self.map_combo.addItems(maps)
        cfg = ConfigManager(profile.server_path)
        self.cfg_combo.clear()
        self.cfg_combo.addItems([p.name for p in cfg.list_configs()])

    def _save_args(self) -> None:
        profile = self.ctx.active_profile
        if profile is None:
            return
        profile.launch_args = self.args_edit.text().strip()
        self.ctx.profiles.update(profile)
        show_info(self, "Параметры", "Параметры запуска сохранены в профиль.")

    # ------------------------------------------------------------ кнопки

    def _start(self) -> None:
        if self.ctx.server_manager is None:
            show_error(self, "Запуск", "Нет активного профиля.")
            return
        self._save_args_silent()
        if not self.ctx.server_manager.start():
            show_error(self, "Запуск", "Не удалось запустить сервер — см. Консоль/Логи.")

    def _save_args_silent(self) -> None:
        profile = self.ctx.active_profile
        if profile and self.args_edit.text().strip():
            profile.launch_args = self.args_edit.text().strip()
            self.ctx.profiles.update(profile)

    def _stop(self) -> None:
        if self.ctx.server_manager:
            self._worker = Worker(self.ctx.server_manager.stop)
            self._worker.start()

    def _restart(self) -> None:
        if self.ctx.server_manager:
            self._worker = Worker(self.ctx.server_manager.restart)
            self._worker.start()

    def _change_map(self) -> None:
        map_name = self.map_combo.currentText().strip()
        if not map_name:
            return
        try:
            self.ctx.send_console_command(f"changelevel {map_name}")
            show_info(self, "Карта", f"Команда смены карты на {map_name} отправлена.")
        except RCONError as exc:
            show_error(self, "Карта", f"Не удалось сменить карту: {exc}")

    def _exec_config(self) -> None:
        cfg = self.cfg_combo.currentText().strip()
        if not cfg:
            return
        try:
            self.ctx.send_console_command(f"exec {cfg}")
            show_info(self, "Конфиг", f"exec {cfg} отправлен серверу.")
        except RCONError as exc:
            show_error(self, "Конфиг", f"Не удалось применить конфиг: {exc}")

    def _steamcmd_job(self, validate: bool) -> None:
        profile = self.ctx.active_profile
        if profile is None:
            return
        steamcmd_path = self.ctx.settings.get("paths.steamcmd", "")
        manager = SteamCMDManager(steamcmd_path)
        if not manager.is_installed():
            show_error(self, "SteamCMD", "SteamCMD не найден. Укажите путь в Настройках.")
            return
        if self.ctx.server_manager and self.ctx.server_manager.is_running():
            show_error(self, "SteamCMD", "Сначала остановите сервер.")
            return
        self.output.clear()
        fn = manager.validate_files if validate else manager.update_cs2_server

        def job(stdout_callback=None):
            return fn(profile.server_path, progress_callback=stdout_callback)

        self._steamcmd_worker = Worker(job, use_output=True)
        self._steamcmd_worker.output.connect(self._append_output)
        self._steamcmd_worker.finished_ok.connect(
            lambda ok: self._append_output("=== ГОТОВО ===" if ok else "=== ОШИБКА ==="))
        self._steamcmd_worker.failed.connect(lambda err: self._append_output(f"[ОШИБКА] {err}"))
        self._steamcmd_worker.start()

    def _append_output(self, line: str) -> None:
        self.output.appendPlainText(line)
        sb = self.output.verticalScrollBar()
        sb.setValue(sb.maximum())

    def _open_folder(self) -> None:
        profile = self.ctx.active_profile
        if profile is None:
            return
        path = Path(profile.server_path)
        if os.name == "nt":
            os.startfile(str(path))  # noqa: S606
        else:
            subprocess.Popen(["xdg-open", str(path)])  # noqa: S603,S607

    def _tick(self) -> None:
        if not self.isVisible() or self.ctx.server_manager is None:
            return
        info = self.ctx.server_manager.get_process_info()
        if info["running"]:
            from app.core.process_manager import ProcessManager
            self.proc_label.setText(
                f"PID: {info['pid']}   |   Статус: {self.ctx.server_manager.state}   |   "
                f"Аптайм: {ProcessManager.format_uptime(info['uptime_sec'])}   |   "
                f"CPU: {info['cpu_percent']}%   |   RAM: {info['ram_mb']:.0f} MB")
        else:
            self.proc_label.setText("Процесс не запущен")

    def on_show(self) -> None:
        self.refresh()
        self._tick()
