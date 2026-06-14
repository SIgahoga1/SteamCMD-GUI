"""Менеджер карт: сканирование vpk, кастомные карты, mapcycle/maplist."""
from __future__ import annotations

from PySide6.QtWidgets import (QHBoxLayout, QInputDialog, QListWidget, QVBoxLayout,
                               QWidget)

from app.core.map_manager import MapManager
from app.core.rcon_client import RCONError
from app.gui.widgets import (Card, confirm, make_button, page_header, show_error,
                             show_info)


class MapsPage(QWidget):
    def __init__(self, ctx) -> None:
        super().__init__()
        self.ctx = ctx
        self.setObjectName("Page")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)
        layout.addWidget(page_header("Карты", "Карты сервера и генерация mapcycle"))

        body = QHBoxLayout()

        found_card = Card("Найденные карты (game/csgo/maps/*.vpk + стандартные)")
        self.found_list = QListWidget()
        self.found_list.setMinimumHeight(340)
        found_card.add(self.found_list)
        body.addWidget(found_card)

        custom_card = Card("Кастомные карты (вручную / Workshop)")
        self.custom_list = QListWidget()
        custom_card.add(self.custom_list)
        row = QHBoxLayout()
        row.addWidget(make_button("+ Добавить", on_click=self._add_custom))
        row.addWidget(make_button("🗑 Удалить", "Danger", self._remove_custom))
        workshop_btn = make_button("Workshop…", enabled=False)
        workshop_btn.setToolTip("TODO: установка карт из Steam Workshop")
        row.addWidget(workshop_btn)  # TODO: установка карт из Steam Workshop
        custom_card.add_layout(row)
        body.addWidget(custom_card)
        layout.addLayout(body)

        actions = QHBoxLayout()
        actions.addWidget(make_button("▶ Сменить карту сейчас (RCON)", "Primary",
                                      self._change_now))
        actions.addWidget(make_button("★ Установить как стартовую", on_click=self._set_start))
        actions.addWidget(make_button("Сгенерировать mapcycle.txt",
                                      on_click=lambda: self._generate("mapcycle")))
        actions.addWidget(make_button("Сгенерировать maplist.txt",
                                      on_click=lambda: self._generate("maplist")))
        actions.addWidget(make_button("✓ Проверить целостность", on_click=self._integrity))
        actions.addStretch(1)
        layout.addLayout(actions)
        layout.addStretch(1)

        self.ctx.profile_changed.connect(lambda _: self.refresh())
        self.refresh()

    # ------------------------------------------------------------ helpers

    def _manager(self) -> MapManager | None:
        profile = self.ctx.active_profile
        return MapManager(profile.server_path) if profile else None

    def _selected_map(self) -> str:
        for lst in (self.found_list, self.custom_list):
            item = lst.currentItem()
            if item and lst.hasFocus():
                return item.text()
        item = self.found_list.currentItem() or self.custom_list.currentItem()
        return item.text() if item else ""

    def refresh(self) -> None:
        manager = self._manager()
        self.found_list.clear()
        self.custom_list.clear()
        custom = self.ctx.settings.get("custom_maps", [])
        self.custom_list.addItems(custom)
        if manager is None:
            return
        self.found_list.addItems(manager.all_maps([]))

    # ----------------------------------------------------------- действия

    def _add_custom(self) -> None:
        name, ok = QInputDialog.getText(
            self, "Кастомная карта",
            "Название карты (например de_mymap или workshop-ID):")
        name = name.strip()
        if not ok or not name:
            return
        custom = self.ctx.settings.get("custom_maps", [])
        if name not in custom:
            custom.append(name)
            self.ctx.settings.set("custom_maps", custom)
        self.refresh()

    def _remove_custom(self) -> None:
        item = self.custom_list.currentItem()
        if item is None:
            return
        if not confirm(self, "Удаление", f"Убрать карту {item.text()} из списка?",
                       danger=True):
            return
        custom = [m for m in self.ctx.settings.get("custom_maps", []) if m != item.text()]
        self.ctx.settings.set("custom_maps", custom)
        self.refresh()

    def _change_now(self) -> None:
        map_name = self._selected_map()
        if not map_name:
            show_info(self, "Карты", "Выберите карту в списке.")
            return
        try:
            self.ctx.send_console_command(f"changelevel {map_name}")
            show_info(self, "Карты", f"Команда смены карты на {map_name} отправлена.")
        except RCONError as exc:
            show_error(self, "Карты", str(exc))

    def _set_start(self) -> None:
        map_name = self._selected_map()
        profile = self.ctx.active_profile
        if not map_name or profile is None:
            return
        profile.start_map = map_name
        self.ctx.profiles.update(profile)
        show_info(self, "Карты", f"Стартовая карта профиля: {map_name}")

    def _generate(self, kind: str) -> None:
        manager = self._manager()
        if manager is None:
            return
        maps = [self.found_list.item(i).text() for i in range(self.found_list.count())]
        maps += [self.custom_list.item(i).text() for i in range(self.custom_list.count())]
        maps = list(dict.fromkeys(maps))
        try:
            path = (manager.generate_mapcycle(maps) if kind == "mapcycle"
                    else manager.generate_maplist(maps))
            show_info(self, "Карты", f"Сгенерирован файл:\n{path}")
        except OSError as exc:
            show_error(self, "Карты", str(exc))

    def _integrity(self) -> None:
        manager = self._manager()
        if manager is None:
            return
        issues = manager.check_integrity()
        if issues:
            show_error(self, "Проверка карт", "\n".join(issues))
        else:
            show_info(self, "Проверка карт", "Проблем не найдено ✔")

    def on_show(self) -> None:
        self.refresh()
