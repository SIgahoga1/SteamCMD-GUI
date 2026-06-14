"""Генерация диагностического отчёта."""
from __future__ import annotations

import json
import platform
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

from app.models.server_profile import ServerProfile
from app.services.logger import AppLogger, app_data_dir
from app.services.settings_service import SettingsService

APP_VERSION = "2.0.0"
TAIL_LINES = 50


def _tail(path: Path, lines: int = TAIL_LINES) -> str:
    try:
        if not path.exists():
            return "<файл не найден>"
        content = path.read_text(encoding="utf-8", errors="replace").splitlines()
        return "\n".join(content[-lines:])
    except OSError as exc:
        return f"<ошибка чтения: {exc}>"


def generate_report(profile: Optional[ServerProfile] = None,
                    components: Optional[dict] = None,
                    plugins: Optional[list] = None) -> dict:
    """Собирает диагностический отчёт в виде dict."""
    settings = SettingsService.instance()
    report: dict = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "app_version": APP_VERSION,
        "python_version": sys.version,
        "os": f"{platform.system()} {platform.release()} ({platform.version()})",
        "machine": platform.machine(),
        "processor": platform.processor(),
        "settings": {
            "paths": settings.get("paths"),
            "automation": settings.get("automation"),
            "ui": settings.get("ui"),
        },
    }
    if profile:
        report["profile"] = {
            "name": profile.name,
            "server_path": profile.server_path,
            "port": profile.port,
            "start_map": profile.start_map,
            "launch_args": profile.launch_args,
            "game_mode": profile.game_mode,
        }
    report["components"] = components or {}
    report["plugins"] = plugins or []

    logs: dict = {"app_log": _tail(app_data_dir() / "logs" / "app.log")}
    if profile:
        server_root = Path(profile.server_path)
        logs_dir = server_root / "game" / "csgo" / "logs"
        if logs_dir.is_dir():
            files = sorted(logs_dir.glob("*.log"), key=lambda f: f.stat().st_mtime)
            if files:
                logs[f"server_log ({files[-1].name})"] = _tail(files[-1])
        css_log_dir = server_root / "game" / "csgo" / "addons" / "counterstrikesharp" / "logs"
        if css_log_dir.is_dir():
            files = sorted(css_log_dir.glob("*.txt"), key=lambda f: f.stat().st_mtime)
            if files:
                logs[f"cssharp_log ({files[-1].name})"] = _tail(files[-1])
    report["logs"] = logs
    return report


def export_report(path: Path, profile: Optional[ServerProfile] = None,
                  components: Optional[dict] = None,
                  plugins: Optional[list] = None) -> Path:
    """Экспортирует отчёт в текстовый файл."""
    report = generate_report(profile, components, plugins)
    lines = ["=== SteamCMD v2 — Диагностический отчёт ===", ""]
    for key, value in report.items():
        if isinstance(value, (dict, list)):
            lines.append(f"--- {key} ---")
            lines.append(json.dumps(value, ensure_ascii=False, indent=2, default=str))
        else:
            lines.append(f"{key}: {value}")
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")
    AppLogger.info("Диагностический отчёт сохранён: %s", path)
    return path
