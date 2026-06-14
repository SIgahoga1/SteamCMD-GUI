"""Сервис настроек приложения (singleton). Хранит settings.json в %APPDATA%/SteamCMDv2/."""
from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

from app.services.logger import AppLogger, app_data_dir

DEFAULT_SETTINGS: dict = {
    "paths": {
        "steamcmd": "",
        "backups": "",   # пусто => %APPDATA%/SteamCMDv2/backups
        "logs": "",      # пусто => %APPDATA%/SteamCMDv2/logs
    },
    "server_defaults": {
        "port": 27015,
        "start_map": "de_dust2",
        "launch_args": "-dedicated -usercon +game_type 0 +game_mode 1",
        "rcon_password": "",
    },
    "automation": {
        "auto_update_on_start": False,
        "auto_backup_enabled": False,
        "auto_backup_schedule": "daily",  # hourly | every6h | daily | weekly
        "auto_backup_type": "configs",
        "auto_backup_max_count": 10,
        "notifications_enabled": False,  # TODO: реализация уведомлений о событиях
    },
    "quick_commands": [
        "status",
        "changelevel de_dust2",
        "mp_restartgame 1",
        "say Hello!",
        "css_plugins list",
        "meta list",
    ],
    "favorite_maps": ["de_dust2", "de_mirage", "de_inferno"],
    "custom_maps": [],
    "active_profile_id": "",
    "ui": {
        "theme": "green_dark",  # dark | green_dark | glass | light
        "accent_color": "#00ff41",
        "bg_color": "#0a0f0a",
        "glass_opacity": 5,        # 0-100 (% прозрачности glass-панелей)
        "font_family": "Segoe UI",
        "font_size": 13,
        "animations_enabled": True,
        "animation_speed": "normal",  # fast | normal | slow
        "corner_radius": 12,
        "shadows": True,
        "blur_effects": True,
        "compact_mode": False,
        "language": "ru",          # TODO: реализовать через i18n/gettext
        "sidebar_side": "left",    # left | right
    },
}


def _deep_merge(base: dict, override: dict) -> dict:
    out = copy.deepcopy(base)
    for key, value in override.items():
        if key in out and isinstance(out[key], dict) and isinstance(value, dict):
            out[key] = _deep_merge(out[key], value)
        else:
            out[key] = value
    return out


class SettingsService:
    """Singleton-доступ к настройкам. Ключи вида 'ui.theme' (через точку)."""

    _instance: "SettingsService | None" = None

    def __init__(self) -> None:
        self._path = app_data_dir() / "settings.json"
        self._data: dict = copy.deepcopy(DEFAULT_SETTINGS)
        self.load()

    @classmethod
    def instance(cls) -> "SettingsService":
        if cls._instance is None:
            cls._instance = SettingsService()
        return cls._instance

    @property
    def path(self) -> Path:
        return self._path

    def load(self) -> None:
        try:
            if self._path.exists():
                raw = json.loads(self._path.read_text(encoding="utf-8"))
                self._data = _deep_merge(DEFAULT_SETTINGS, raw)
        except (OSError, json.JSONDecodeError) as exc:
            AppLogger.error("Не удалось прочитать settings.json: %s", exc)
            self._data = copy.deepcopy(DEFAULT_SETTINGS)

    def save(self) -> None:
        try:
            self._path.write_text(
                json.dumps(self._data, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        except OSError as exc:
            AppLogger.error("Не удалось сохранить settings.json: %s", exc)

    def get(self, key: str, default: Any = None) -> Any:
        node: Any = self._data
        for part in key.split("."):
            if not isinstance(node, dict) or part not in node:
                return default
            node = node[part]
        return node

    def set(self, key: str, value: Any, save: bool = True) -> None:
        parts = key.split(".")
        node = self._data
        for part in parts[:-1]:
            node = node.setdefault(part, {})
        node[parts[-1]] = value
        if save:
            self.save()

    def reset(self) -> None:
        self._data = copy.deepcopy(DEFAULT_SETTINGS)
        self.save()

    def export_to(self, path: Path) -> None:
        path.write_text(json.dumps(self._data, ensure_ascii=False, indent=2), encoding="utf-8")

    def import_from(self, path: Path) -> None:
        raw = json.loads(path.read_text(encoding="utf-8"))
        self._data = _deep_merge(DEFAULT_SETTINGS, raw)
        self.save()

    def backups_dir(self) -> Path:
        custom = self.get("paths.backups", "")
        path = Path(custom) if custom else app_data_dir() / "backups"
        path.mkdir(parents=True, exist_ok=True)
        return path
