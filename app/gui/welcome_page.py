"""Экран первого запуска: выбор действия."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from app.gui.widgets import Card, make_button


class WelcomePage(QWidget):
    def __init__(self, ctx) -> None:
        super().__init__()
        self.ctx = ctx
        self.setObjectName("Page")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.addStretch(1)

        title = QLabel("⚡ SteamCMD v2")
        title.setObjectName("PageTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        subtitle = QLabel("Панель управления CS2 Dedicated Server.\nВыберите, с чего начать:")
        subtitle.setObjectName("Muted")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(subtitle)
        layout.addSpacing(24)

        row = QHBoxLayout()
        row.setSpacing(16)
        row.addStretch(1)
        row.addWidget(self._option_card(
            "🛠 Установить новый сервер",
            "Мастер установки: SteamCMD, CS2 Server,\nMetamod, CounterStrikeSharp и конфиги.",
            "Установить", lambda: ctx.show_page("installer"), primary=True))
        row.addWidget(self._option_card(
            "📂 Подключить существующий",
            "Импортировать уже установленный сервер:\nсканирование папки и создание профиля.",
            "Подключить", lambda: ctx.show_page("connect")))
        row.addWidget(self._option_card(
            "♻ Восстановить из бэкапа",
            "Развернуть сервер из ранее созданного\nбэкапа SteamCMD v2.",
            "К бэкапам", lambda: ctx.show_page("backups")))
        row.addStretch(1)
        layout.addLayout(row)
        layout.addStretch(2)

    def _option_card(self, title: str, description: str, button_text: str,
                     on_click, primary: bool = False) -> Card:
        card = Card()
        card.setFixedSize(300, 190)
        label = QLabel(title)
        label.setObjectName("CardValue")
        label.setWordWrap(True)
        card.add(label)
        desc = QLabel(description)
        desc.setObjectName("Muted")
        desc.setWordWrap(True)
        card.add(desc)
        card._layout.addStretch(1)
        card.add(make_button(button_text, "Primary" if primary else "", on_click))
        return card

    def on_show(self) -> None:
        pass
