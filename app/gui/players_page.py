"""Игроки онлайн: таблица из RCON status + контекстные действия."""
from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (QCheckBox, QHBoxLayout, QInputDialog, QLabel, QMenu,
                               QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget)

from app.core.rcon_client import RCONError, parse_status_players
from app.gui.widgets import (Card, Worker, confirm, make_button, page_header,
                             show_error)
from app.models.player import Player

COLUMNS = ["#", "Ник", "SteamID", "IP", "Ping", "Score", "Время", "Статус"]
BAN_DURATIONS = {"1 час": 60, "24 часа": 1440, "7 дней": 10080, "30 дней": 43200}


class PlayersPage(QWidget):
    def __init__(self, ctx) -> None:
        super().__init__()
        self.ctx = ctx
        self.setObjectName("Page")
        self._players: list[Player] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)
        layout.addWidget(page_header("Игроки онлайн",
                                     "Источник: RCON `status`. ПКМ по строке — действия."))

        controls = QHBoxLayout()
        self.refresh_btn = make_button("⟳ Обновить", "Primary", self.refresh)
        controls.addWidget(self.refresh_btn)
        self.auto_check = QCheckBox("Автообновление каждые 30 сек")
        self.auto_check.setChecked(True)
        controls.addWidget(self.auto_check)
        controls.addStretch(1)
        self.count_label = QLabel("—")
        self.count_label.setObjectName("Muted")
        controls.addWidget(self.count_label)
        layout.addLayout(controls)

        card = Card()
        self.table = QTableWidget(0, len(COLUMNS))
        self.table.setHorizontalHeaderLabels(COLUMNS)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setColumnWidth(1, 220)
        self.table.setColumnWidth(2, 180)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._context_menu)
        self.table.setMinimumHeight(420)
        card.add(self.table)
        layout.addWidget(card)
        layout.addStretch(1)

        self._timer = QTimer(self)
        self._timer.setInterval(30000)
        self._timer.timeout.connect(self._auto_tick)
        self._timer.start()

    # ------------------------------------------------------------ данные

    def _auto_tick(self) -> None:
        if self.isVisible() and self.auto_check.isChecked():
            self.refresh()

    def refresh(self) -> None:
        manager = self.ctx.server_manager
        if manager is None or self.ctx.active_profile is None:
            self.count_label.setText("Нет активного профиля")
            return
        if not manager.is_running():
            self.count_label.setText("Сервер не запущен")
            self._set_players([])
            return
        self.refresh_btn.setEnabled(False)

        def job():
            return self.ctx.get_rcon().send_command("status")

        self._worker = Worker(job)
        self._worker.finished_ok.connect(self._on_status)
        self._worker.failed.connect(self._on_error)
        self._worker.start()

    def _on_status(self, output: str) -> None:
        self.refresh_btn.setEnabled(True)
        self._set_players(parse_status_players(output))

    def _on_error(self, err: str) -> None:
        self.refresh_btn.setEnabled(True)
        self.count_label.setText(f"Ошибка RCON: {err}")

    def _set_players(self, players: list[Player]) -> None:
        self._players = players
        humans = [p for p in players if p.status != "bot"]
        self.count_label.setText(f"Игроков: {len(humans)} (+{len(players) - len(humans)} бот.)")
        self.table.setRowCount(len(players))
        for row, player in enumerate(players):
            values = [str(player.slot), player.nickname, player.steam_id, player.ip,
                      str(player.ping), str(player.score), player.time_online, player.status]
            for col, value in enumerate(values):
                item = QTableWidgetItem(value)
                if col == 0:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.table.setItem(row, col, item)

    # ----------------------------------------------------------- действия

    def _context_menu(self, pos) -> None:
        row = self.table.rowAt(pos.y())
        if row < 0 or row >= len(self._players):
            return
        player = self._players[row]
        menu = QMenu(self)
        menu.addAction("👢 Kick…", lambda: self._kick(player))
        menu.addAction("⛔ Ban (навсегда)", lambda: self._ban(player, 0))
        tmp = menu.addMenu("⏱ Временный бан")
        for label, minutes in BAN_DURATIONS.items():
            tmp.addAction(label, lambda m=minutes: self._ban(player, m))
        menu.addSeparator()
        menu.addAction("🔇 Mute", lambda: self._simple_cmd(player, "css_mute"))
        menu.addAction("🔊 Unmute", lambda: self._simple_cmd(player, "css_unmute"))
        menu.addAction("💀 Slay", lambda: self._simple_cmd(player, "css_slay"))
        menu.addSeparator()
        menu.addAction("📋 Скопировать SteamID",
                       lambda: QGuiApplication.clipboard().setText(player.steam_id))
        menu.addAction("📋 Скопировать IP",
                       lambda: QGuiApplication.clipboard().setText(player.ip))
        menu.exec(self.table.viewport().mapToGlobal(pos))

    def _kick(self, player: Player) -> None:
        reason, ok = QInputDialog.getText(self, "Kick", f"Причина кика {player.nickname}:")
        if not ok:
            return
        if not confirm(self, "Kick", f"Кикнуть игрока {player.nickname}?", danger=True):
            return
        self._send(f"kickid {player.userid or player.slot}" + (f" {reason}" if reason else ""))

    def _ban(self, player: Player, minutes: int) -> None:
        label = "навсегда" if minutes == 0 else f"на {minutes} мин"
        if not confirm(self, "Ban", f"Забанить {player.nickname} {label}?", danger=True):
            return
        target = player.steam_id or f"#{player.userid}"
        try:
            rcon = self.ctx.get_rcon()
            rcon.ban_player(target, minutes, "Banned via SteamCMD v2")
        except RCONError as exc:
            show_error(self, "Ban", str(exc))
        self.refresh()

    def _simple_cmd(self, player: Player, command: str) -> None:
        target = f"#{player.userid}" if player.userid else player.nickname
        self._send(f"{command} {target}")

    def _send(self, command: str) -> None:
        try:
            self.ctx.send_console_command(command)
            self.refresh()
        except RCONError as exc:
            show_error(self, "RCON", str(exc))

    def on_show(self) -> None:
        self.refresh()
