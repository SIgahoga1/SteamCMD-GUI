"""Общие виджеты и утилиты GUI: карточки, графики, фоновый Worker, диалоги."""
from __future__ import annotations

from typing import Callable, List, Optional, Sequence

from PySide6.QtCore import QPointF, Qt, QThread, Signal
from PySide6.QtGui import QColor, QPainter, QPen, QPolygonF
from PySide6.QtWidgets import (QFrame, QHBoxLayout, QLabel, QMessageBox,
                               QPushButton, QVBoxLayout, QWidget)

from app.services.logger import AppLogger


class Worker(QThread):
    """Универсальный фоновый поток: выполняет fn(*args, progress=..., output=...).

    Сигналы:
        progress(int, int)  — текущий/всего
        output(str)         — строка вывода
        finished_ok(object) — результат fn
        failed(str)         — текст ошибки
    """

    progress = Signal(int, int)
    output = Signal(str)
    finished_ok = Signal(object)
    failed = Signal(str)

    def __init__(self, fn: Callable, *args, use_progress: bool = False,
                 use_output: bool = False, parent: Optional[QWidget] = None, **kwargs):
        super().__init__(parent)
        self._fn = fn
        self._args = args
        self._kwargs = kwargs
        self._use_progress = use_progress
        self._use_output = use_output

    def run(self) -> None:  # noqa: D102
        try:
            kwargs = dict(self._kwargs)
            if self._use_progress:
                kwargs["progress_callback"] = lambda done, total: self.progress.emit(done, total)
            if self._use_output:
                kwargs["stdout_callback"] = lambda line: self.output.emit(line)
            result = self._fn(*self._args, **kwargs)
            self.finished_ok.emit(result)
        except Exception as exc:  # noqa: BLE001 — ошибки показываем пользователю
            AppLogger.error("Worker ошибка: %s", exc, exc_info=True)
            self.failed.emit(str(exc))


def confirm(parent: QWidget, title: str, text: str, danger: bool = False) -> bool:
    """Диалог подтверждения опасного действия."""
    box = QMessageBox(parent)
    box.setWindowTitle(title)
    box.setText(text)
    box.setIcon(QMessageBox.Icon.Warning if danger else QMessageBox.Icon.Question)
    yes = box.addButton("Да", QMessageBox.ButtonRole.YesRole)
    box.addButton("Отмена", QMessageBox.ButtonRole.RejectRole)
    box.exec()
    return box.clickedButton() is yes


def show_error(parent: QWidget, title: str, text: str) -> None:
    QMessageBox.critical(parent, title, text)


def show_info(parent: QWidget, title: str, text: str) -> None:
    QMessageBox.information(parent, title, text)


class Card(QFrame):
    """Карточка с рамкой (стиль QFrame#Card)."""

    def __init__(self, title: str = "", parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("Card")
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(14, 12, 14, 12)
        self._layout.setSpacing(8)
        if title:
            label = QLabel(title.upper())
            label.setObjectName("CardTitle")
            self._layout.addWidget(label)

    def add(self, widget: QWidget) -> QWidget:
        self._layout.addWidget(widget)
        return widget

    def add_layout(self, layout) -> None:
        self._layout.addLayout(layout)


class StatCard(Card):
    """Карточка «заголовок + крупное значение»."""

    def __init__(self, title: str, value: str = "—", parent: Optional[QWidget] = None) -> None:
        super().__init__(title, parent)
        self.value_label = QLabel(value)
        self.value_label.setObjectName("CardValue")
        self.value_label.setWordWrap(True)
        self._layout.addWidget(self.value_label)

    def set_value(self, value: str) -> None:
        self.value_label.setText(value)


class Sparkline(QWidget):
    """Простой линейный график последних N точек (без внешних зависимостей)."""

    def __init__(self, max_points: int = 60, color: str = "#00ff41",
                 parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.max_points = max_points
        self.color = QColor(color)
        self.values: List[float] = []
        self.setMinimumHeight(64)

    def set_color(self, color: str) -> None:
        self.color = QColor(color)
        self.update()

    def add_point(self, value: float) -> None:
        self.values.append(float(value))
        if len(self.values) > self.max_points:
            self.values = self.values[-self.max_points:]
        self.update()

    def clear(self) -> None:
        self.values.clear()
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect().adjusted(2, 4, -2, -4)
        if len(self.values) < 2:
            pen = QPen(QColor(self.color))
            pen.setWidth(1)
            painter.setPen(pen)
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "нет данных")
            return
        max_v = max(self.values) or 1.0
        min_v = min(self.values)
        span = (max_v - min_v) or 1.0
        step = rect.width() / (self.max_points - 1)
        points = []
        offset = self.max_points - len(self.values)
        for i, value in enumerate(self.values):
            x = rect.left() + (offset + i) * step
            y = rect.bottom() - (value - min_v) / span * rect.height()
            points.append(QPointF(x, y))
        # заливка под линией
        fill = QPolygonF(points)
        fill.append(QPointF(points[-1].x(), rect.bottom()))
        fill.append(QPointF(points[0].x(), rect.bottom()))
        fill_color = QColor(self.color)
        fill_color.setAlpha(40)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(fill_color)
        painter.drawPolygon(fill)
        # линия
        pen = QPen(self.color)
        pen.setWidthF(1.6)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPolyline(QPolygonF(points))


def page_header(title: str, subtitle: str = "") -> QWidget:
    """Заголовок страницы."""
    box = QWidget()
    layout = QVBoxLayout(box)
    layout.setContentsMargins(0, 0, 0, 6)
    layout.setSpacing(2)
    label = QLabel(title)
    label.setObjectName("PageTitle")
    layout.addWidget(label)
    if subtitle:
        sub = QLabel(subtitle)
        sub.setObjectName("Muted")
        sub.setWordWrap(True)
        layout.addWidget(sub)
    return box


def hbox(widgets: Sequence[QWidget], stretch_last: bool = False) -> QHBoxLayout:
    layout = QHBoxLayout()
    layout.setContentsMargins(0, 0, 0, 0)
    for widget in widgets:
        layout.addWidget(widget)
    if not stretch_last:
        layout.addStretch(1)
    return layout


def make_button(text: str, role: str = "", on_click: Optional[Callable] = None,
                enabled: bool = True) -> QPushButton:
    btn = QPushButton(text)
    if role:
        btn.setObjectName(role)  # Primary | Danger | Warning
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    btn.setEnabled(enabled)
    if on_click:
        btn.clicked.connect(on_click)
    return btn
