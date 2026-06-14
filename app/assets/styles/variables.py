"""Темы и сборка QSS из шаблона dark_green.qss.

Шаблон содержит токены вида $BG_PRIMARY$, которые подставляются из палитры
активной темы + пользовательских настроек UI (accent, радиус, шрифт...).
"""
from __future__ import annotations

import sys
from pathlib import Path


def resource_path(relative: str) -> Path:
    """Путь к ресурсу — работает и из исходников, и из PyInstaller onefile."""
    base = getattr(sys, "_MEIPASS", None)
    if base:
        return Path(base) / relative
    # app/assets/styles/variables.py -> корень проекта
    return Path(__file__).resolve().parents[3] / relative


THEMES: dict[str, dict[str, str]] = {
    "green_dark": {
        "BG_PRIMARY": "#0a0f0a",
        "BG_SECONDARY": "#0f1a0f",
        "BG_CARD": "#111c11",
        "ACCENT": "#00ff41",
        "ACCENT_DIM": "#00cc33",
        "TEXT_PRIMARY": "#e0ffe0",
        "TEXT_MUTED": "#4a7a4a",
        "BORDER": "#1a3a1a",
        "DANGER": "#ff4141",
        "WARNING": "#ffaa00",
        "SUCCESS": "#00ff41",
        "CONSOLE_BG": "#050805",
        "CONSOLE_TEXT": "#00ff41",
    },
    "dark": {
        "BG_PRIMARY": "#0d1117",
        "BG_SECONDARY": "#11171f",
        "BG_CARD": "#161b22",
        "ACCENT": "#00ff41",
        "ACCENT_DIM": "#00cc33",
        "TEXT_PRIMARY": "#e6edf3",
        "TEXT_MUTED": "#6e7681",
        "BORDER": "#21262d",
        "DANGER": "#ff4141",
        "WARNING": "#ffaa00",
        "SUCCESS": "#3fb950",
        "CONSOLE_BG": "#090c10",
        "CONSOLE_TEXT": "#9ecbff",
    },
    "glass": {
        "BG_PRIMARY": "#070d07",
        "BG_SECONDARY": "rgba(15, 26, 15, 0.82)",
        "BG_CARD": "rgba(0, 255, 65, 0.05)",
        "ACCENT": "#00ff41",
        "ACCENT_DIM": "#00cc33",
        "TEXT_PRIMARY": "#e0ffe0",
        "TEXT_MUTED": "#4a7a4a",
        "BORDER": "rgba(0, 255, 65, 0.18)",
        "DANGER": "#ff4141",
        "WARNING": "#ffaa00",
        "SUCCESS": "#00ff41",
        "CONSOLE_BG": "rgba(5, 8, 5, 0.9)",
        "CONSOLE_TEXT": "#00ff41",
    },
    "light": {
        "BG_PRIMARY": "#f2f7f2",
        "BG_SECONDARY": "#e8f0e8",
        "BG_CARD": "#ffffff",
        "ACCENT": "#00a82d",
        "ACCENT_DIM": "#008a24",
        "TEXT_PRIMARY": "#13231a",
        "TEXT_MUTED": "#5c7a64",
        "BORDER": "#c9dccd",
        "DANGER": "#d32f2f",
        "WARNING": "#b97200",
        "SUCCESS": "#00a82d",
        "CONSOLE_BG": "#102315",
        "CONSOLE_TEXT": "#27d957",
    },
}


def _hex_to_rgb(value: str) -> tuple[int, int, int]:
    value = value.lstrip("#")
    return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]


def _mix(color: str, other: tuple[int, int, int], k: float) -> str:
    if not color.startswith("#"):
        return color
    r, g, b = _hex_to_rgb(color)
    nr = int(r + (other[0] - r) * k)
    ng = int(g + (other[1] - g) * k)
    nb = int(b + (other[2] - b) * k)
    return f"#{nr:02x}{ng:02x}{nb:02x}"


def lighten(color: str, k: float = 0.15) -> str:
    return _mix(color, (255, 255, 255), k)


def darken(color: str, k: float = 0.15) -> str:
    return _mix(color, (0, 0, 0), k)


def rgba(color: str, alpha: float) -> str:
    if not color.startswith("#"):
        return color
    r, g, b = _hex_to_rgb(color)
    return f"rgba({r}, {g}, {b}, {alpha:.2f})"


def build_qss(ui_settings: dict) -> str:
    """Собирает итоговый QSS из шаблона + темы + пользовательских настроек."""
    theme_name = ui_settings.get("theme", "green_dark")
    palette = dict(THEMES.get(theme_name, THEMES["green_dark"]))

    accent = ui_settings.get("accent_color") or palette["ACCENT"]
    if accent.startswith("#") and len(accent) == 7:
        palette["ACCENT"] = accent
        palette["ACCENT_DIM"] = darken(accent, 0.2)
        if theme_name != "light":
            palette["SUCCESS"] = accent
    bg = ui_settings.get("bg_color") or ""
    if bg.startswith("#") and len(bg) == 7 and theme_name != "light":
        palette["BG_PRIMARY"] = bg
        palette["BG_SECONDARY"] = lighten(bg, 0.04)
        palette["BG_CARD"] = lighten(bg, 0.07)
        palette["BORDER"] = lighten(bg, 0.16)

    glass_opacity = max(0, min(100, int(ui_settings.get("glass_opacity", 5)))) / 100.0
    palette["GLASS_BG"] = rgba(palette["ACCENT"], glass_opacity)
    palette["ACCENT_HOVER"] = lighten(palette["ACCENT"], 0.25)
    palette["ACCENT_GLOW"] = rgba(palette["ACCENT"], 0.35)
    palette["ACCENT_FAINT"] = rgba(palette["ACCENT"], 0.12)
    palette["DANGER_DIM"] = darken(palette["DANGER"], 0.25)
    palette["TEXT_ON_ACCENT"] = "#06140a" if theme_name != "light" else "#ffffff"

    radius = int(ui_settings.get("corner_radius", 12))
    compact = bool(ui_settings.get("compact_mode", False))
    font_size = int(ui_settings.get("font_size", 13))
    palette["RADIUS"] = f"{radius}px"
    palette["RADIUS_SMALL"] = f"{max(2, radius // 2)}px"
    palette["FONT_FAMILY"] = ui_settings.get("font_family", "Segoe UI") or "Segoe UI"
    palette["FONT_SIZE"] = f"{font_size}px"
    palette["FONT_SIZE_SMALL"] = f"{max(9, font_size - 2)}px"
    palette["PAD"] = "6px" if compact else "10px"
    palette["PAD_BIG"] = "10px" if compact else "16px"

    template = resource_path("app/assets/styles/dark_green.qss").read_text(encoding="utf-8")
    for key, value in palette.items():
        template = template.replace(f"${key}$", str(value))
    return template
