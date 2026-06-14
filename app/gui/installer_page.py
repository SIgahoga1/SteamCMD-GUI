"""Мастер установки нового сервера (пошаговый wizard)."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (QCheckBox, QComboBox, QFileDialog, QGridLayout,
                               QHBoxLayout, QLabel, QLineEdit, QPlainTextEdit,
                               QProgressBar, QSpinBox, QVBoxLayout, QWidget)

from app.core import update_manager
from app.core.config_manager import ConfigManager
from app.core.steamcmd_manager import SteamCMDManager
from app.gui.widgets import Card, Worker, make_button, page_header, show_error
from app.models.server_profile import ServerProfile
from app.services.logger import AppLogger

TEMPLATE_NAMES = ["Public", "Retake", "Deathmatch", "Bhop", "Training", "Custom"]

GAME_MODES = {
    "Public": ("0", "1"), "Retake": ("0", "0"), "Deathmatch": ("1", "2"),
    "Bhop": ("0", "0"), "Training": ("0", "0"), "Custom": ("0", "1"),
}


class InstallerPage(QWidget):
    """Шаги: параметры → SteamCMD → CS2 → Metamod → CSSharp → конфиги → профиль."""

    def __init__(self, ctx) -> None:
        super().__init__()
        self.ctx = ctx
        self.setObjectName("Page")
        self._worker: Worker | None = None
        self._steps: list[tuple[str, callable]] = []
        self._step_index = 0

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)
        layout.addWidget(page_header("Установка нового сервера",
                                     "Мастер скачает SteamCMD, установит CS2 Dedicated Server "
                                     "и (по желанию) Metamod + CounterStrikeSharp."))

        params = Card("Параметры установки")
        grid = QGridLayout()
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(8)

        grid.addWidget(QLabel("Папка установки:"), 0, 0)
        self.path_edit = QLineEdit()
        self.path_edit.setPlaceholderText(r"C:\cs2-server")
        grid.addWidget(self.path_edit, 0, 1)
        grid.addWidget(make_button("Обзор…", on_click=self._browse), 0, 2)

        grid.addWidget(QLabel("Название сервера:"), 1, 0)
        self.name_edit = QLineEdit("Мой CS2 сервер")
        grid.addWidget(self.name_edit, 1, 1, 1, 2)

        grid.addWidget(QLabel("Порт:"), 2, 0)
        self.port_spin = QSpinBox()
        self.port_spin.setRange(1024, 65535)
        self.port_spin.setValue(int(self.ctx.settings.get("server_defaults.port", 27015)))
        grid.addWidget(self.port_spin, 2, 1, 1, 2)

        grid.addWidget(QLabel("Стартовая карта:"), 3, 0)
        self.map_edit = QLineEdit(self.ctx.settings.get("server_defaults.start_map", "de_dust2"))
        grid.addWidget(self.map_edit, 3, 1, 1, 2)

        grid.addWidget(QLabel("RCON пароль:"), 4, 0)
        self.rcon_edit = QLineEdit()
        self.rcon_edit.setPlaceholderText("обязательно для удалённого управления")
        grid.addWidget(self.rcon_edit, 4, 1, 1, 2)

        grid.addWidget(QLabel("Шаблон сервера:"), 5, 0)
        self.template_combo = QComboBox()
        self.template_combo.addItems(TEMPLATE_NAMES)
        grid.addWidget(self.template_combo, 5, 1, 1, 2)
        params.add_layout(grid)

        self.metamod_check = QCheckBox("Установить Metamod:Source")
        self.metamod_check.setChecked(True)
        params.add(self.metamod_check)
        self.cssharp_check = QCheckBox("Установить CounterStrikeSharp")
        self.cssharp_check.setChecked(True)
        params.add(self.cssharp_check)
        self.base_plugins_check = QCheckBox(
            "Установить базовые плагины (откроется Магазин — TODO, пока вручную на стр. Плагины)")
        self.base_plugins_check.setEnabled(False)  # TODO: интеграция с онлайн-каталогом плагинов
        params.add(self.base_plugins_check)
        layout.addWidget(params)

        progress_card = Card("Прогресс установки")
        self.step_label = QLabel("Готов к установке.")
        progress_card.add(self.step_label)
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        progress_card.add(self.progress)
        self.console = QPlainTextEdit()
        self.console.setObjectName("Console")
        self.console.setReadOnly(True)
        self.console.setMinimumHeight(220)
        progress_card.add(self.console)
        layout.addWidget(progress_card)

        row = QHBoxLayout()
        self.start_btn = make_button("⚡ Начать установку", "Primary", self._start)
        row.addWidget(self.start_btn)
        row.addStretch(1)
        layout.addLayout(row)
        layout.addStretch(1)

    # ------------------------------------------------------------ helpers

    def _browse(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Папка установки сервера")
        if folder:
            self.path_edit.setText(folder)

    def _log(self, line: str) -> None:
        self.console.appendPlainText(line)
        sb = self.console.verticalScrollBar()
        sb.setValue(sb.maximum())

    def _set_progress(self, done: int, total: int) -> None:
        if total > 0:
            self.progress.setValue(int(done / total * 100))

    # -------------------------------------------------------------- wizard

    def _start(self) -> None:
        folder = self.path_edit.text().strip()
        if not folder:
            show_error(self, "Установка", "Укажите папку установки.")
            return
        if not self.rcon_edit.text().strip():
            show_error(self, "Установка", "Укажите RCON пароль.")
            return
        self.install_dir = Path(folder)
        try:
            self.install_dir.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            show_error(self, "Установка", f"Не удалось создать папку: {exc}")
            return
        self.steamcmd_dir = self.install_dir / "steamcmd"
        self.start_btn.setEnabled(False)
        self.console.clear()

        self._steps = [("Установка SteamCMD", self._step_steamcmd),
                       ("Загрузка CS2 Dedicated Server (app_update 730) — это долго, ~30+ ГБ",
                        self._step_cs2)]
        if self.metamod_check.isChecked():
            self._steps.append(("Установка Metamod:Source", self._step_metamod))
        if self.cssharp_check.isChecked():
            self._steps.append(("Установка CounterStrikeSharp", self._step_cssharp))
        self._steps.append(("Создание конфигов из шаблона", self._step_configs))
        self._steps.append(("Сохранение профиля", self._step_profile))
        self._step_index = 0
        self._run_next_step()

    def _run_next_step(self) -> None:
        if self._step_index >= len(self._steps):
            self.step_label.setText("✔ Установка завершена!")
            self._log("=== УСТАНОВКА ЗАВЕРШЕНА ===")
            self.start_btn.setEnabled(True)
            self.ctx.show_page("dashboard")
            return
        name, fn = self._steps[self._step_index]
        self.step_label.setText(
            f"Шаг {self._step_index + 1}/{len(self._steps)}: {name}")
        self._log(f"--- {name} ---")
        self.progress.setValue(0)
        fn()

    def _step_done(self, ok: bool, error: str = "") -> None:
        if not ok:
            self.step_label.setText("✖ Ошибка установки")
            self._log(f"[ОШИБКА] {error or 'шаг не выполнен'}")
            self.start_btn.setEnabled(True)
            show_error(self, "Установка", error or "Шаг установки не выполнен. См. вывод.")
            return
        self._step_index += 1
        self._run_next_step()

    def _run_worker(self, fn, *args, use_progress=False, use_output=False) -> None:
        self._worker = Worker(fn, *args, use_progress=use_progress, use_output=use_output)
        if use_progress:
            self._worker.progress.connect(self._set_progress)
        if use_output:
            self._worker.output.connect(self._log)
        self._worker.finished_ok.connect(
            lambda result: self._step_done(bool(result),
                                           "" if result else "операция вернула ошибку"))
        self._worker.failed.connect(lambda err: self._step_done(False, err))
        self._worker.start()

    # --------------------------------------------------------------- шаги

    def _step_steamcmd(self) -> None:
        manager = SteamCMDManager(str(self.steamcmd_dir))
        if manager.is_installed():
            self._log("SteamCMD уже установлен — пропускаю.")
            self._step_done(True)
            return
        self._run_worker(manager.install, str(self.steamcmd_dir), use_progress=True)

    def _step_cs2(self) -> None:
        manager = SteamCMDManager(str(self.steamcmd_dir))

        def job(stdout_callback=None):
            return manager.install_cs2_server(str(self.install_dir),
                                              progress_callback=stdout_callback)
        self._run_worker(job, use_output=True)

    def _step_metamod(self) -> None:
        self._run_worker(update_manager.install_metamod, str(self.install_dir),
                         use_progress=True)

    def _step_cssharp(self) -> None:
        self._run_worker(update_manager.install_cssharp, str(self.install_dir),
                         use_progress=True)

    def _step_configs(self) -> None:
        try:
            manager = ConfigManager(str(self.install_dir))
            template = self.template_combo.currentText()
            manager.create_from_template(template, "server.cfg",
                                         hostname=self.name_edit.text().strip(),
                                         rcon_password=self.rcon_edit.text().strip())
            self._log(f"server.cfg создан из шаблона {template}")
            self._step_done(True)
        except Exception as exc:  # noqa: BLE001
            self._step_done(False, str(exc))

    def _step_profile(self) -> None:
        try:
            template = self.template_combo.currentText()
            game_type, game_mode = GAME_MODES.get(template, ("0", "1"))
            profile = ServerProfile(
                name=self.name_edit.text().strip() or "CS2 Server",
                server_path=str(self.install_dir),
                port=self.port_spin.value(),
                start_map=self.map_edit.text().strip() or "de_dust2",
                launch_args=f"-dedicated -usercon +game_type {game_type} "
                            f"+game_mode {game_mode}",
                game_mode=template.lower(),
                rcon_password=self.rcon_edit.text().strip(),
                description=f"Установлен мастером SteamCMD v2 (шаблон {template})",
            )
            self.ctx.settings.set("paths.steamcmd", str(self.steamcmd_dir))
            self.ctx.profiles.add(profile)
            self.ctx.set_active_profile(profile)
            AppLogger.info("Установка завершена, профиль создан: %s", profile.name)
            self._step_done(True)
        except Exception as exc:  # noqa: BLE001
            self._step_done(False, str(exc))

    def on_show(self) -> None:
        pass
