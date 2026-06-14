"""Настройки интерфейса: темы, цвета, шрифты — применяются без перезапуска."""
from __future__ import annotations

from PySide6.QtWidgets import (QCheckBox, QColorDialog, QComboBox, QFontComboBox,
                               QGridLayout, QHBoxLayout, QLabel, QPushButton,
                               QSlider, QSpinBox, QVBoxLayout, QWidget)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor

from app.gui.widgets import Card, make_button, page_header, show_info

THEME_LABELS = {"Green Dark (по умолчанию)": "green_dark", "Dark": "dark",
                "Glass": "glass", "Light": "light"}
SPEED_LABELS = {"Быстро": "fast", "Нормально": "normal", "Медленно": "slow"}


class ColorButton(QPushButton):
    """Кнопка-образец цвета, открывает QColorDialog."""

    def __init__(self, color: str) -> None:
        super().__init__()
        self.setFixedSize(80, 28)
        self.set_color(color)
        self.clicked.connect(self._pick)

    def set_color(self, color: str) -> None:
        self._color = color
        self.setText(color)
        self.setStyleSheet(f"background-color: {color}; color: #000; border-radius: 6px;")

    def color(self) -> str:
        return self._color

    def _pick(self) -> None:
        chosen = QColorDialog.getColor(QColor(self._color), self, "Выбор цвета")
        if chosen.isValid():
            self.set_color(chosen.name())


class UISettingsPage(QWidget):
    def __init__(self, ctx) -> None:
        super().__init__()
        self.ctx = ctx
        self.setObjectName("Page")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)
        layout.addWidget(page_header("Настройки интерфейса",
                                     "Применяются сразу, без перезапуска"))

        theme_card = Card("Тема и цвета")
        grid = QGridLayout()
        grid.setVerticalSpacing(10)
        grid.addWidget(QLabel("Тема:"), 0, 0)
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(list(THEME_LABELS.keys()))
        grid.addWidget(self.theme_combo, 0, 1)
        grid.addWidget(QLabel("Акцентный цвет:"), 1, 0)
        self.accent_btn = ColorButton("#00ff41")
        grid.addWidget(self.accent_btn, 1, 1)
        grid.addWidget(QLabel("Цвет фона:"), 2, 0)
        self.bg_btn = ColorButton("#0a0f0a")
        grid.addWidget(self.bg_btn, 2, 1)
        grid.addWidget(QLabel("Прозрачность glass-панелей:"), 3, 0)
        self.glass_slider = QSlider(Qt.Orientation.Horizontal)
        self.glass_slider.setRange(0, 100)
        grid.addWidget(self.glass_slider, 3, 1)
        theme_card.add_layout(grid)
        layout.addWidget(theme_card)

        font_card = Card("Шрифт и форма")
        fgrid = QGridLayout()
        fgrid.setVerticalSpacing(10)
        fgrid.addWidget(QLabel("Шрифт:"), 0, 0)
        self.font_combo = QFontComboBox()
        fgrid.addWidget(self.font_combo, 0, 1)
        fgrid.addWidget(QLabel("Размер шрифта:"), 0, 2)
        self.font_size_spin = QSpinBox()
        self.font_size_spin.setRange(10, 18)
        fgrid.addWidget(self.font_size_spin, 0, 3)
        fgrid.addWidget(QLabel("Скругление углов:"), 1, 0)
        self.radius_slider = QSlider(Qt.Orientation.Horizontal)
        self.radius_slider.setRange(0, 20)
        fgrid.addWidget(self.radius_slider, 1, 1)
        self.radius_label = QLabel("12 px")
        fgrid.addWidget(self.radius_label, 1, 2)
        self.radius_slider.valueChanged.connect(
            lambda v: self.radius_label.setText(f"{v} px"))
        font_card.add_layout(fgrid)
        layout.addWidget(font_card)

        fx_card = Card("Эффекты и режимы")
        fx_row = QGridLayout()
        self.animations_check = QCheckBox("Анимации включены")
        fx_row.addWidget(self.animations_check, 0, 0)
        fx_row.addWidget(QLabel("Скорость анимаций:"), 0, 1)
        self.speed_combo = QComboBox()
        self.speed_combo.addItems(list(SPEED_LABELS.keys()))
        fx_row.addWidget(self.speed_combo, 0, 2)
        self.shadows_check = QCheckBox("Тени")
        fx_row.addWidget(self.shadows_check, 1, 0)
        self.blur_check = QCheckBox("Размытие (blur)")
        fx_row.addWidget(self.blur_check, 1, 1)
        self.compact_check = QCheckBox("Компактный режим")
        fx_row.addWidget(self.compact_check, 1, 2)
        fx_row.addWidget(QLabel("Язык:"), 2, 0)
        self.lang_combo = QComboBox()
        self.lang_combo.addItems(["Русский", "English (TODO)"])
        self.lang_combo.model().item(1).setEnabled(False)  # TODO: i18n
        fx_row.addWidget(self.lang_combo, 2, 1)
        fx_row.addWidget(QLabel("Боковое меню:"), 3, 0)
        self.sidebar_combo = QComboBox()
        self.sidebar_combo.addItems(["Слева", "Справа (после перезапуска)"])
        fx_row.addWidget(self.sidebar_combo, 3, 1)
        fx_card.add_layout(fx_row)
        layout.addWidget(fx_card)

        buttons = QHBoxLayout()
        buttons.addWidget(make_button("✦ Применить", "Primary", self._apply))
        buttons.addWidget(make_button("↩ Сбросить тему", on_click=self._reset))
        buttons.addStretch(1)
        layout.addLayout(buttons)
        layout.addStretch(1)

        self.load()

    # ------------------------------------------------------------- данные

    def load(self) -> None:
        ui = self.ctx.settings.get("ui", {})
        theme = ui.get("theme", "green_dark")
        for label, key in THEME_LABELS.items():
            if key == theme:
                self.theme_combo.setCurrentText(label)
        self.accent_btn.set_color(ui.get("accent_color", "#00ff41"))
        self.bg_btn.set_color(ui.get("bg_color", "#0a0f0a"))
        self.glass_slider.setValue(int(ui.get("glass_opacity", 5)))
        self.font_combo.setCurrentText(ui.get("font_family", "Segoe UI"))
        self.font_size_spin.setValue(int(ui.get("font_size", 13)))
        self.radius_slider.setValue(int(ui.get("corner_radius", 12)))
        self.animations_check.setChecked(bool(ui.get("animations_enabled", True)))
        for label, key in SPEED_LABELS.items():
            if key == ui.get("animation_speed", "normal"):
                self.speed_combo.setCurrentText(label)
        self.shadows_check.setChecked(bool(ui.get("shadows", True)))
        self.blur_check.setChecked(bool(ui.get("blur_effects", True)))
        self.compact_check.setChecked(bool(ui.get("compact_mode", False)))
        self.sidebar_combo.setCurrentIndex(
            1 if ui.get("sidebar_side", "left") == "right" else 0)

    def _apply(self) -> None:
        s = self.ctx.settings
        s.set("ui.theme", THEME_LABELS[self.theme_combo.currentText()], save=False)
        s.set("ui.accent_color", self.accent_btn.color(), save=False)
        s.set("ui.bg_color", self.bg_btn.color(), save=False)
        s.set("ui.glass_opacity", self.glass_slider.value(), save=False)
        s.set("ui.font_family", self.font_combo.currentText(), save=False)
        s.set("ui.font_size", self.font_size_spin.value(), save=False)
        s.set("ui.corner_radius", self.radius_slider.value(), save=False)
        s.set("ui.animations_enabled", self.animations_check.isChecked(), save=False)
        s.set("ui.animation_speed", SPEED_LABELS[self.speed_combo.currentText()], save=False)
        s.set("ui.shadows", self.shadows_check.isChecked(), save=False)
        s.set("ui.blur_effects", self.blur_check.isChecked(), save=False)
        s.set("ui.compact_mode", self.compact_check.isChecked(), save=False)
        s.set("ui.sidebar_side",
              "right" if self.sidebar_combo.currentIndex() == 1 else "left")
        self.ctx.apply_theme()

    def _reset(self) -> None:
        from app.services.settings_service import DEFAULT_SETTINGS
        self.ctx.settings.set("ui", dict(DEFAULT_SETTINGS["ui"]))
        self.load()
        self.ctx.apply_theme()
        show_info(self, "Интерфейс", "Тема сброшена к значениям по умолчанию.")

    def on_show(self) -> None:
        pass
