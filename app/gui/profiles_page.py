"""Профили серверов: CRUD, клонирование, импорт/экспорт."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (QDialog, QDialogButtonBox, QFileDialog, QFormLayout,
                               QGridLayout, QHBoxLayout, QLabel, QLineEdit,
                               QPlainTextEdit, QSpinBox, QVBoxLayout, QWidget)

from app.gui.widgets import (Card, confirm, make_button, page_header, show_error,
                             show_info)
from app.models.server_profile import ServerProfile


class ProfileDialog(QDialog):
    """Форма создания/редактирования профиля."""

    def __init__(self, parent, profile: ServerProfile | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Профиль сервера")
        self.setMinimumWidth(520)
        form = QFormLayout(self)
        self.name_edit = QLineEdit()
        self.path_edit = QLineEdit()
        browse = make_button("Обзор…", on_click=self._browse)
        path_row = QHBoxLayout()
        path_row.addWidget(self.path_edit, 1)
        path_row.addWidget(browse)
        self.port_spin = QSpinBox()
        self.port_spin.setRange(1024, 65535)
        self.port_spin.setValue(27015)
        self.map_edit = QLineEdit("de_dust2")
        self.args_edit = QLineEdit("-dedicated -usercon +game_type 0 +game_mode 1")
        self.mode_edit = QLineEdit("competitive")
        self.rcon_edit = QLineEdit()
        self.desc_edit = QPlainTextEdit()
        self.desc_edit.setMaximumHeight(70)
        form.addRow("Название:", self.name_edit)
        form.addRow("Папка сервера:", path_row)
        form.addRow("Порт:", self.port_spin)
        form.addRow("Стартовая карта:", self.map_edit)
        form.addRow("Параметры запуска:", self.args_edit)
        form.addRow("Режим игры:", self.mode_edit)
        form.addRow("RCON пароль:", self.rcon_edit)
        form.addRow("Описание:", self.desc_edit)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok |
                                   QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

        self._profile = profile
        if profile:
            self.name_edit.setText(profile.name)
            self.path_edit.setText(profile.server_path)
            self.port_spin.setValue(profile.port)
            self.map_edit.setText(profile.start_map)
            self.args_edit.setText(profile.launch_args)
            self.mode_edit.setText(profile.game_mode)
            self.rcon_edit.setText(profile.rcon_password)
            self.desc_edit.setPlainText(profile.description)

    def _browse(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Папка сервера")
        if folder:
            self.path_edit.setText(folder)

    def result_profile(self) -> ServerProfile:
        if self._profile:
            profile = self._profile
        else:
            profile = ServerProfile(name="", server_path="")
        profile.name = self.name_edit.text().strip() or "CS2 Server"
        profile.server_path = self.path_edit.text().strip()
        profile.port = self.port_spin.value()
        profile.start_map = self.map_edit.text().strip() or "de_dust2"
        profile.launch_args = self.args_edit.text().strip()
        profile.game_mode = self.mode_edit.text().strip()
        profile.rcon_password = self.rcon_edit.text().strip()
        profile.description = self.desc_edit.toPlainText().strip()
        return profile


class ProfilesPage(QWidget):
    def __init__(self, ctx) -> None:
        super().__init__()
        self.ctx = ctx
        self.setObjectName("Page")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)
        layout.addWidget(page_header("Профили серверов"))

        controls = QHBoxLayout()
        controls.addWidget(make_button("+ Создать профиль", "Primary", self._create))
        controls.addWidget(make_button("⤓ Импортировать из JSON", on_click=self._import))
        controls.addStretch(1)
        layout.addLayout(controls)

        self.cards_box = QWidget()
        self.cards_grid = QGridLayout(self.cards_box)
        self.cards_grid.setContentsMargins(0, 0, 0, 0)
        self.cards_grid.setSpacing(12)
        layout.addWidget(self.cards_box)
        layout.addStretch(1)

        self.ctx.profile_changed.connect(lambda _: self.refresh())
        self.refresh()

    def refresh(self) -> None:
        while self.cards_grid.count():
            item = self.cards_grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        profiles = self.ctx.profiles.all()
        if not profiles:
            self.cards_grid.addWidget(QLabel("Профилей пока нет — создайте или "
                                             "подключите сервер."), 0, 0)
            return
        active_id = self.ctx.active_profile.id if self.ctx.active_profile else ""
        for i, profile in enumerate(profiles):
            self.cards_grid.addWidget(self._profile_card(profile, profile.id == active_id),
                                      i // 2, i % 2)

    def _profile_card(self, profile: ServerProfile, active: bool) -> Card:
        card = Card()
        title = QLabel(("▸ " if active else "") + profile.name +
                       ("   (активный)" if active else ""))
        title.setObjectName("CardValue")
        card.add(title)
        info = QLabel(f"{profile.server_path}\nПорт: {profile.port}  |  Карта: "
                      f"{profile.start_map}  |  Режим: {profile.game_mode}\n"
                      f"{profile.description}")
        info.setObjectName("Muted")
        info.setWordWrap(True)
        card.add(info)
        row = QHBoxLayout()
        row.addWidget(make_button("▶ Использовать", "Primary",
                                  lambda: self._activate(profile)))
        row.addWidget(make_button("✎", on_click=lambda: self._edit(profile)))
        row.addWidget(make_button("⧉", on_click=lambda: self._clone(profile)))
        row.addWidget(make_button("⤒ JSON", on_click=lambda: self._export(profile)))
        row.addWidget(make_button("🗑", "Danger", lambda: self._delete(profile)))
        row.addStretch(1)
        card.add_layout(row)
        return card

    # ----------------------------------------------------------- действия

    def _activate(self, profile: ServerProfile) -> None:
        self.ctx.set_active_profile(profile)
        self.ctx.show_page("dashboard")

    def _create(self) -> None:
        dialog = ProfileDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            profile = dialog.result_profile()
            if not profile.server_path:
                show_error(self, "Профиль", "Укажите папку сервера.")
                return
            self.ctx.profiles.add(profile)
            self.refresh()

    def _edit(self, profile: ServerProfile) -> None:
        dialog = ProfileDialog(self, profile)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.ctx.profiles.update(dialog.result_profile())
            if self.ctx.active_profile and self.ctx.active_profile.id == profile.id:
                self.ctx.set_active_profile(profile)
            self.refresh()

    def _clone(self, profile: ServerProfile) -> None:
        self.ctx.profiles.clone(profile.id)
        self.refresh()

    def _delete(self, profile: ServerProfile) -> None:
        if not confirm(self, "Удаление",
                       f"Удалить профиль «{profile.name}»?\n"
                       "Файлы сервера НЕ удаляются — только запись профиля.", danger=True):
            return
        self.ctx.profiles.delete(profile.id)
        if self.ctx.active_profile and self.ctx.active_profile.id == profile.id:
            remaining = self.ctx.profiles.all()
            self.ctx.set_active_profile(remaining[0] if remaining else None)
        self.refresh()

    def _export(self, profile: ServerProfile) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Экспорт профиля",
                                              f"{profile.name}.json", "JSON (*.json)")
        if path:
            self.ctx.profiles.export_profile(profile.id, Path(path))
            show_info(self, "Экспорт", f"Профиль сохранён: {path}")

    def _import(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Импорт профиля", "", "JSON (*.json)")
        if not path:
            return
        try:
            profile = self.ctx.profiles.import_profile(Path(path))
            show_info(self, "Импорт", f"Импортирован: {profile.name}")
            self.refresh()
        except Exception as exc:  # noqa: BLE001
            show_error(self, "Импорт", str(exc))

    def on_show(self) -> None:
        self.refresh()
