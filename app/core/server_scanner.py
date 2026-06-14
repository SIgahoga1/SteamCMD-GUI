"""Сканирование папки существующего сервера (для ConnectPage)."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List

from app.core.update_manager import detect_components


@dataclass
class ScanResult:
    ok: bool = False
    server_path: str = ""
    exe_path: str = ""
    components: dict = field(default_factory=dict)
    configs: List[str] = field(default_factory=list)
    plugins: List[str] = field(default_factory=list)
    maps: List[str] = field(default_factory=list)
    rcon_password: str = ""
    port_hint: int = 0
    warnings: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)


def scan_server_folder(folder: str) -> ScanResult:
    """Проверяет папку на наличие CS2 Dedicated Server и собирает отчёт."""
    result = ScanResult(server_path=str(Path(folder)))
    root = Path(folder)
    if not root.is_dir():
        result.warnings.append("Папка не существует")
        return result

    components = detect_components(str(root))
    result.components = components
    cs2 = components.get("CS2 Server", {})
    result.ok = bool(cs2.get("installed"))
    result.exe_path = cs2.get("path", "")
    if not result.ok:
        result.warnings.append("Не найден cs2.exe / srcds.exe — это не папка CS2 сервера?")
        return result

    csgo = root / "game" / "csgo"
    if not csgo.is_dir():
        result.warnings.append("Папка game/csgo/ не найдена")

    cfg_dir = csgo / "cfg"
    if cfg_dir.is_dir():
        result.configs = sorted(p.name for p in cfg_dir.glob("*.cfg"))
        server_cfg = cfg_dir / "server.cfg"
        if server_cfg.is_file():
            try:
                text = server_cfg.read_text(encoding="utf-8", errors="replace")
                m = re.search(r'rcon_password\s+"?([^"\s]+)"?', text)
                if m:
                    result.rcon_password = m.group(1)
                m = re.search(r'hostport\s+"?(\d+)"?', text)
                if m:
                    result.port_hint = int(m.group(1))
            except OSError:
                result.warnings.append("server.cfg не читается")
        else:
            result.recommendations.append(
                "Нет server.cfg — рекомендуем создать из шаблона на странице «Конфиги»")
    else:
        result.warnings.append("Папка конфигов game/csgo/cfg не найдена")

    maps_dir = csgo / "maps"
    if maps_dir.is_dir():
        result.maps = sorted(p.stem for p in maps_dir.glob("*.vpk"))
    else:
        result.warnings.append("Папка карт game/csgo/maps не найдена")

    logs_dir = csgo / "logs"
    if not logs_dir.is_dir():
        result.recommendations.append("Папка логов game/csgo/logs отсутствует "
                                      "(создастся при первом запуске)")

    plugins_dir = csgo / "addons" / "counterstrikesharp" / "plugins"
    if plugins_dir.is_dir():
        result.plugins = sorted(
            p.name for p in plugins_dir.iterdir() if p.is_dir() and p.name != "disabled")

    if not components.get("Metamod:Source", {}).get("installed"):
        result.recommendations.append(
            "Metamod:Source не установлен — нужен для плагинов")
    if not components.get("CounterStrikeSharp", {}).get("installed"):
        result.recommendations.append(
            "CounterStrikeSharp не установлен — нужен для C#-плагинов")
    if not result.rcon_password:
        result.recommendations.append(
            "RCON пароль не найден в server.cfg — укажите его вручную в профиле")
    return result
