"""Dashboard — главная панель статуса сервера."""
from __future__ import annotations

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (QGridLayout, QHBoxLayout, QLabel, QPlainTextEdit,
                               QVBoxLayout, QWidget)

from app.core import update_manager
from app.core.process_manager import ProcessManager
from app.core.rcon_client import RCONError
from app.gui.widgets import Card, Sparkline, StatCard, Worker, make_button, page_header
from app.services.logger import AppLogger

STATE_STYLE = {
    "ONLINE": "StatusOnline", "OFFLINE": "StatusOffline",
    "STARTING": "StatusStarting", "STOPPING": "StatusStarting",
}


class DashboardPage(QWidget):
    def __init__(self, ctx) -> None:
        super().__init__()
        self.ctx = ctx
        self.setObjectName("Page")
        self._components_cache: dict = {}
        self._players_count = 0
        self._current_map = "—"

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)
        layout.addWidget(page_header("Главная", "Статус и метрики активного сервера"))

        # --- статус + кнопки ---
        top = QHBoxLayout()
        status_card = Card("Статус сервера")
        self.status_label = QLabel("OFFLINE")
        self.status_label.setObjectName("StatusOffline")
        font = self.status_label.font()
        font.setPointSize(20)
        font.setBold(True)
        self.status_label.setFont(font)
        status_card.add(self.status_label)
        self.profile_info = QLabel("—")
        self.profile_info.setObjectName("Muted")
        self.profile_info.setWordWrap(True)
        status_card.add(self.profile_info)
        btn_row = QHBoxLayout()
        self.start_btn = make_button("▶ ЗАПУСТИТЬ", "Primary", self._start)
        self.stop_btn = make_button("■ ОСТАНОВИТЬ", "Danger", self._stop, enabled=False)
        self.restart_btn = make_button("↺ ПЕРЕЗАПУСТИТЬ", "Warning", self._restart,
                                       enabled=False)
        for btn in (self.start_btn, self.stop_btn, self.restart_btn):
            btn_row.addWidget(btn)
        status_card.add_layout(btn_row)
        top.addWidget(status_card, 2)

        grid_box = QWidget()
        grid = QGridLayout(grid_box)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(12)
        self.card_port = StatCard("Порт")
        self.card_map = StatCard("Карта")
        self.card_players = StatCard("Игроки")
        self.card_pid = StatCard("PID / Аптайм")
        self.card_cpu = StatCard("CPU")
        self.card_ram = StatCard("RAM")
        cards = [self.card_port, self.card_map, self.card_players,
                 self.card_pid, self.card_cpu, self.card_ram]
        for i, card in enumerate(cards):
            grid.addWidget(card, i // 3, i % 3)
        top.addWidget(grid_box, 3)
        layout.addLayout(top)

        # --- графики ---
        charts = QHBoxLayout()
        accent = self.ctx.settings.get("ui.accent_color", "#00ff41")
        cpu_card = Card("CPU Usage (последние 5 мин)")
        self.cpu_chart = Sparkline(60, accent)
        cpu_card.add(self.cpu_chart)
        charts.addWidget(cpu_card)
        ram_card = Card("RAM Usage (последние 5 мин)")
        self.ram_chart = Sparkline(60, "#ffaa00")
        ram_card.add(self.ram_chart)
        charts.addWidget(ram_card)
        players_card = Card("Игроки online (последние 30 мин)")
        self.players_chart = Sparkline(60, "#41a7ff")
        players_card.add(self.players_chart)
        charts.addWidget(players_card)
        layout.addLayout(charts)

        # --- компоненты + ошибки ---
        bottom = QHBoxLayout()
        comp_card = Card("Установленные компоненты")
        self.components_label = QLabel("—")
        self.components_label.setWordWrap(True)
        comp_card.add(self.components_label)
        comp_card.add(make_button("Обновить список", on_click=self._refresh_components))
        bottom.addWidget(comp_card, 1)

        err_card = Card("Последние ошибки (app.log)")
        self.errors_box = QPlainTextEdit()
        self.errors_box.setObjectName("Console")
        self.errors_box.setReadOnly(True)
        self.errors_box.setMaximumHeight(130)
        err_card.add(self.errors_box)
        bottom.addWidget(err_card, 2)
        layout.addLayout(bottom)
        layout.addStretch(1)

        # таймеры
        self._timer = QTimer(self)
        self._timer.setInterval(5000)
        self._timer.timeout.connect(self._tick)
        self._timer.start()
        self._players_timer = QTimer(self)
        self._players_timer.setInterval(30000)
        self._players_timer.timeout.connect(self._poll_players)
        self._players_timer.start()

        self.ctx.profile_changed.connect(self._on_profile_changed)
        self.ctx.server_manager_changed.connect(self._on_manager_changed)
        self._on_profile_changed(self.ctx.active_profile)
        self._on_manager_changed(self.ctx.server_manager)

    # ----------------------------------------------------------- события

    def _on_profile_changed(self, profile) -> None:
        if profile is None:
            self.profile_info.setText("Профиль не выбран")
            self.card_port.set_value("—")
            return
        self.profile_info.setText(f"{profile.name}\n{profile.server_path}")
        self.card_port.set_value(str(profile.port))
        self.card_map.set_value(profile.start_map)
        self.cpu_chart.clear()
        self.ram_chart.clear()
        self.players_chart.clear()
        self._refresh_components()

    def _on_manager_changed(self, manager) -> None:
        if manager is not None:
            manager.state_changed.connect(self._on_state)
            self._on_state(manager.state)

    def _on_state(self, state: str) -> None:
        self.status_label.setText(state)
        self.status_label.setObjectName(STATE_STYLE.get(state, "StatusOffline"))
        self.status_label.style().unpolish(self.status_label)
        self.status_label.style().polish(self.status_label)
        running = state in ("ONLINE", "STARTING")
        self.start_btn.setEnabled(state == "OFFLINE" and self.ctx.active_profile is not None)
        self.stop_btn.setEnabled(running)
        self.restart_btn.setEnabled(state == "ONLINE")

    # ----------------------------------------------------------- кнопки

    def _start(self) -> None:
        if self.ctx.server_manager:
            self.ctx.server_manager.start()

    def _stop(self) -> None:
        if self.ctx.server_manager:
            self.stop_btn.setEnabled(False)
            self._stop_worker = Worker(self.ctx.server_manager.stop)
            self._stop_worker.start()

    def _restart(self) -> None:
        if self.ctx.server_manager:
            self.restart_btn.setEnabled(False)
            self._restart_worker = Worker(self.ctx.server_manager.restart)
            self._restart_worker.start()

    # ------------------------------------------------------------- тики

    def _tick(self) -> None:
        if not self.isVisible():
            return
        manager = self.ctx.server_manager
        if manager is None:
            return
        info = manager.get_process_info()
        if info["running"]:
            uptime = ProcessManager.format_uptime(info["uptime_sec"])
            self.card_pid.set_value(f"{info['pid']} / {uptime}")
            self.card_cpu.set_value(f"{info['cpu_percent']}%")
            ram = info["ram_mb"]
            self.card_ram.set_value(f"{ram / 1024:.2f} GB" if ram >= 1024 else f"{ram:.0f} MB")
            self.cpu_chart.add_point(info["cpu_percent"])
            self.ram_chart.add_point(ram)
        else:
            self.card_pid.set_value("—")
            self.card_cpu.set_value("—")
            self.card_ram.set_value("—")
        self._refresh_errors()

    def _poll_players(self) -> None:
        manager = self.ctx.server_manager
        if not (self.isVisible() and manager and manager.state == "ONLINE"
                and self.ctx.active_profile and self.ctx.active_profile.rcon_password):
            return

        def job():
            rcon = self.ctx.get_rcon()
            return rcon.send_command("status")

        def done(output: str) -> None:
            from app.core.rcon_client import parse_status_players
            players = parse_status_players(output)
            humans = [p for p in players if p.status != "bot"]
            self._players_count = len(humans)
            self.card_players.set_value(str(self._players_count))
            self.players_chart.add_point(self._players_count)
            for line in output.splitlines():
                low = line.lower().strip()
                if low.startswith("map") and ":" in line:
                    self._current_map = line.split(":", 1)[1].strip().split()[0]
                    self.card_map.set_value(self._current_map)

        self._players_worker = Worker(job)
        self._players_worker.finished_ok.connect(done)
        self._players_worker.failed.connect(lambda err: AppLogger.debug("status poll: %s", err))
        self._players_worker.start()

    def _refresh_components(self) -> None:
        profile = self.ctx.active_profile
        if profile is None:
            self.components_label.setText("Нет активного профиля")
            return

        def job():
            comps = update_manager.detect_components(profile.server_path)
            from app.core.steamcmd_manager import SteamCMDManager
            steamcmd_path = self.ctx.settings.get("paths.steamcmd", "")
            comps["SteamCMD"] = {
                "installed": bool(steamcmd_path) and
                SteamCMDManager(steamcmd_path).is_installed(),
                "version": "", "path": steamcmd_path}
            return comps

        def done(comps: dict) -> None:
            self._components_cache = comps
            lines = []
            for name in ("SteamCMD", "CS2 Server", "Metamod:Source", "CounterStrikeSharp"):
                info = comps.get(name, {})
                mark = "✔" if info.get("installed") else "✖"
                version = f"  v{info['version']}" if info.get("version") else ""
                lines.append(f"{mark}  {name}{version}")
            self.components_label.setText("\n".join(lines))

        self._comp_worker = Worker(job)
        self._comp_worker.finished_ok.connect(done)
        self._comp_worker.failed.connect(lambda err: self.components_label.setText(err))
        self._comp_worker.start()

    def _refresh_errors(self) -> None:
        try:
            log_file = AppLogger.log_file()
            if not log_file.exists():
                return
            lines = log_file.read_text(encoding="utf-8", errors="replace").splitlines()
            bad = [ln for ln in lines if "[ERROR]" in ln or "[WARNING]" in ln][-5:]
            text = "\n".join(bad) if bad else "Ошибок нет 🎉"
            if self.errors_box.toPlainText() != text:
                self.errors_box.setPlainText(text)
        except OSError:
            pass

    def on_show(self) -> None:
        self._tick()
        self._refresh_errors()

    @property
    def components(self) -> dict:
        return self._components_cache
