"""Главное окно: боковое меню, навигация, общий контекст приложения."""
from __future__ import annotations

from typing import Dict, Optional

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (QApplication, QButtonGroup, QFrame, QHBoxLayout,
                               QLabel, QMainWindow, QPushButton, QScrollArea,
                               QStackedWidget, QVBoxLayout, QWidget)

from app.core.backup_manager import BackupManager
from app.core.rcon_client import RCONClient, RCONError
from app.core.server_manager import ServerManager
from app.models.server_profile import ServerProfile
from app.assets.styles.variables import build_qss
from app.services.logger import AppLogger
from app.services.profile_service import ProfileService
from app.services.settings_service import SettingsService

NAV_ITEMS = [
    ("dashboard", "⌂  Главная"),
    ("server", "⚙  Сервер"),
    ("players", "☻  Игроки"),
    ("console", ">_  Консоль"),
    ("plugins", "✚  Плагины"),
    ("maps", "▦  Карты"),
    ("configs", "✎  Конфиги"),
    ("profiles", "▤  Профили"),
    ("backups", "❒  Бэкапы"),
    ("logs", "≡  Логи"),
    ("settings", "⚒  Настройки"),
    ("ui_settings", "✦  Интерфейс"),
]

AUTOBACKUP_INTERVALS = {
    "hourly": 3600, "every6h": 6 * 3600, "daily": 24 * 3600, "weekly": 7 * 24 * 3600,
}


class MainWindow(QMainWindow):
    """Главное окно. Является контекстом (ctx) для всех страниц."""

    profile_changed = Signal(object)        # ServerProfile | None
    server_manager_changed = Signal(object)  # ServerManager | None

    def __init__(self, settings: SettingsService) -> None:
        super().__init__()
        self.settings = settings
        self.profiles = ProfileService.instance()
        self.active_profile: Optional[ServerProfile] = None
        self.server_manager: Optional[ServerManager] = None
        self._rcon: Optional[RCONClient] = None

        self.setWindowTitle("SteamCMD v2 — CS2 Server Control")
        self.resize(1280, 800)

        self._build_ui()
        self.apply_theme()
        self._init_autobackup()

        # Первый запуск: нет профилей -> Welcome, иначе Dashboard активного профиля
        if self.profiles.is_empty():
            self.show_page("welcome")
        else:
            last_id = self.settings.get("active_profile_id", "")
            profile = self.profiles.get(last_id) or self.profiles.all()[0]
            self.set_active_profile(profile)
            self.show_page("dashboard")

    # ------------------------------------------------------------------ UI

    def _build_ui(self) -> None:
        root = QWidget()
        root.setObjectName("Root")
        outer = QHBoxLayout(root)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # --- сайдбар ---
        self.sidebar = QFrame()
        self.sidebar.setObjectName("Sidebar")
        self.sidebar.setFixedWidth(210)
        side = QVBoxLayout(self.sidebar)
        side.setContentsMargins(8, 8, 8, 12)
        side.setSpacing(2)

        title = QLabel("⚡ SteamCMD v2")
        title.setObjectName("SidebarTitle")
        side.addWidget(title)

        self.profile_label = QLabel("Профиль не выбран")
        self.profile_label.setObjectName("Muted")
        self.profile_label.setWordWrap(True)
        self.profile_label.setContentsMargins(10, 0, 0, 8)
        side.addWidget(self.profile_label)

        self._nav_group = QButtonGroup(self)
        self._nav_group.setExclusive(True)
        self._nav_buttons: Dict[str, QPushButton] = {}
        for key, text in NAV_ITEMS:
            btn = QPushButton(text)
            btn.setObjectName("NavButton")
            btn.setCheckable(True)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda _=False, k=key: self.show_page(k))
            self._nav_group.addButton(btn)
            self._nav_buttons[key] = btn
            side.addWidget(btn)

        side.addStretch(1)
        add_btn = QPushButton("+ Добавить сервер")
        add_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        add_btn.clicked.connect(lambda: self.show_page("welcome"))
        side.addWidget(add_btn)

        # --- стек страниц ---
        self.stack = QStackedWidget()
        self._pages: Dict[str, QWidget] = {}
        self._page_indexes: Dict[str, int] = {}

        if self.settings.get("ui.sidebar_side", "left") == "right":
            outer.addWidget(self.stack, 1)
            outer.addWidget(self.sidebar)
        else:
            outer.addWidget(self.sidebar)
            outer.addWidget(self.stack, 1)
        self.setCentralWidget(root)

        self.statusBar().showMessage("Готов")

    def _create_page(self, key: str) -> QWidget:
        """Ленивая инициализация страниц (ускоряет старт)."""
        # импорт здесь, чтобы избежать циклических зависимостей
        from app.gui.welcome_page import WelcomePage
        from app.gui.installer_page import InstallerPage
        from app.gui.connect_page import ConnectPage
        from app.gui.dashboard import DashboardPage
        from app.gui.server_page import ServerPage
        from app.gui.players_page import PlayersPage
        from app.gui.console_page import ConsolePage
        from app.gui.plugins_page import PluginsPage
        from app.gui.maps_page import MapsPage
        from app.gui.configs_page import ConfigsPage
        from app.gui.profiles_page import ProfilesPage
        from app.gui.backups_page import BackupsPage
        from app.gui.logs_page import LogsPage
        from app.gui.settings_page import SettingsPage
        from app.gui.ui_settings_page import UISettingsPage

        factories = {
            "welcome": WelcomePage, "installer": InstallerPage, "connect": ConnectPage,
            "dashboard": DashboardPage, "server": ServerPage, "players": PlayersPage,
            "console": ConsolePage, "plugins": PluginsPage, "maps": MapsPage,
            "configs": ConfigsPage, "profiles": ProfilesPage, "backups": BackupsPage,
            "logs": LogsPage, "settings": SettingsPage, "ui_settings": UISettingsPage,
        }
        page = factories[key](self)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidget(page)
        self._pages[key] = page
        self._page_indexes[key] = self.stack.addWidget(scroll)
        return page

    def show_page(self, key: str) -> None:
        if key not in self._pages:
            self._create_page(key)
        self.stack.setCurrentIndex(self._page_indexes[key])
        if key in self._nav_buttons:
            self._nav_buttons[key].setChecked(True)
        page = self._pages[key]
        if hasattr(page, "on_show"):
            page.on_show()

    def get_page(self, key: str):
        if key not in self._pages:
            self._create_page(key)
        return self._pages[key]

    # ------------------------------------------------------------ Тема

    def apply_theme(self) -> None:
        qss = build_qss(self.settings.get("ui", {}))
        app = QApplication.instance()
        if app:
            app.setStyleSheet(qss)

    # ------------------------------------------------- Профиль и сервер

    def set_active_profile(self, profile: Optional[ServerProfile]) -> None:
        if self.server_manager and self.server_manager.is_running():
            AppLogger.info("Смена профиля при запущенном сервере — сервер остаётся работать")
        self.active_profile = profile
        self.close_rcon()
        if profile is not None:
            profile.touch()
            self.profiles.update(profile)
            self.settings.set("active_profile_id", profile.id)
            self.profile_label.setText(f"▸ {profile.name}")
            self.server_manager = ServerManager(profile, self)
            self.server_manager.state_changed.connect(self._on_server_state)
            self.server_manager.crashed.connect(self._on_server_crash)
        else:
            self.profile_label.setText("Профиль не выбран")
            self.server_manager = None
        self.profile_changed.emit(profile)
        self.server_manager_changed.emit(self.server_manager)

    def _on_server_state(self, state: str) -> None:
        self.statusBar().showMessage(f"Сервер: {state}")
        if state == "OFFLINE":
            self.close_rcon()

    def _on_server_crash(self) -> None:
        AppLogger.warning("Сервер завершился аварийно")
        self.statusBar().showMessage("⚠ Сервер завершился аварийно — см. Консоль/Логи")

    # ------------------------------------------------------------- RCON

    def get_rcon(self) -> RCONClient:
        """RCON-клиент для активного профиля (создаётся лениво)."""
        if self.active_profile is None:
            raise RCONError("Нет активного профиля")
        if self._rcon is None:
            self._rcon = RCONClient("127.0.0.1", self.active_profile.port,
                                    self.active_profile.rcon_password)
        return self._rcon

    def close_rcon(self) -> None:
        if self._rcon is not None:
            self._rcon.disconnect()
            self._rcon = None

    def send_console_command(self, command: str) -> str:
        """Команда серверу: RCON, при неудаче — stdin. Возвращает ответ (если есть)."""
        if self.server_manager is None:
            raise RCONError("Сервер не настроен")
        try:
            return self.get_rcon().send_command(command)
        except RCONError as exc:
            if self.server_manager.is_running() and self.server_manager.send_stdin(command):
                return f"(отправлено в stdin, RCON недоступен: {exc})"
            raise

    # -------------------------------------------------------- Автобэкап

    def _init_autobackup(self) -> None:
        self._autobackup_timer = QTimer(self)
        self._autobackup_timer.setInterval(60 * 1000)
        self._autobackup_timer.timeout.connect(self._autobackup_tick)
        self._autobackup_timer.start()
        self._last_autobackup: float = 0.0

    def _autobackup_tick(self) -> None:
        import time
        if not self.settings.get("automation.auto_backup_enabled", False):
            return
        if self.active_profile is None:
            return
        schedule = self.settings.get("automation.auto_backup_schedule", "daily")
        interval = AUTOBACKUP_INTERVALS.get(schedule, 86400)
        if time.time() - self._last_autobackup < interval:
            return
        self._last_autobackup = time.time()
        backup_type = self.settings.get("automation.auto_backup_type", "configs")
        max_count = int(self.settings.get("automation.auto_backup_max_count", 10))
        profile = self.active_profile
        from app.gui.widgets import Worker

        def job():
            manager = BackupManager(str(self.settings.backups_dir()))
            backup = manager.create_backup(profile.server_path, backup_type, profile.id)
            manager.cleanup_old_backups(max_count)
            return backup

        self._autobackup_worker = Worker(job)
        self._autobackup_worker.finished_ok.connect(
            lambda b: self.statusBar().showMessage(f"Автобэкап создан: {b.filename}"))
        self._autobackup_worker.failed.connect(
            lambda err: AppLogger.error("Автобэкап не удался: %s", err))
        self._autobackup_worker.start()

    # ----------------------------------------------------------- Закрытие

    def closeEvent(self, event) -> None:  # noqa: N802
        if self.server_manager and self.server_manager.is_running():
            from app.gui.widgets import confirm
            if confirm(self, "Выход", "Сервер ещё работает. Остановить его и выйти?",
                       danger=True):
                self.server_manager.stop()
            else:
                event.ignore()
                return
        self.close_rcon()
        event.accept()
