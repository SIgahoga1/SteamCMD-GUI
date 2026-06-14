"""Сканирование, установка и управление плагинами (CounterStrikeSharp / Metamod)."""
from __future__ import annotations

import json
import shutil
import zipfile
from pathlib import Path
from typing import List

from app.models.plugin import Plugin
from app.services.logger import AppLogger


class PluginManager:
    def __init__(self, server_path: str) -> None:
        self.server_path = Path(server_path)
        self.csgo = self.server_path / "game" / "csgo"
        self.css_plugins_dir = self.csgo / "addons" / "counterstrikesharp" / "plugins"
        self.metamod_dir = self.csgo / "addons" / "metamod"

    # --- сканирование ---

    def list_plugins(self) -> List[Plugin]:
        plugins: List[Plugin] = []
        if self.css_plugins_dir.is_dir():
            for folder in sorted(self.css_plugins_dir.iterdir()):
                if not folder.is_dir() or folder.name == "disabled":
                    continue
                plugins.append(self._read_css_plugin(folder))
        # Metamod-плагины: .vdf в addons/metamod (кроме metaplugins.ini)
        if self.metamod_dir.is_dir():
            for vdf in sorted(self.metamod_dir.glob("*.vdf")):
                if vdf.stem.lower() == "metamod":
                    continue
                plugins.append(Plugin(
                    name=vdf.stem, version="", plugin_type="Metamod",
                    enabled=True, folder_path=str(vdf.parent),
                ))
        return plugins

    def _read_css_plugin(self, folder: Path) -> Plugin:
        dlls = list(folder.glob("*.dll"))
        disabled_dlls = list(folder.glob("*.dll.disabled"))
        enabled = bool(dlls) or not disabled_dlls
        version = ""
        description = ""
        meta = folder / "plugin.json"
        if meta.is_file():
            try:
                data = json.loads(meta.read_text(encoding="utf-8", errors="replace"))
                version = str(data.get("version", data.get("Version", "")))
                description = str(data.get("description", data.get("Description", "")))
            except json.JSONDecodeError:
                pass
        deps_file = folder / f"{folder.name}.deps.json"
        if not version and deps_file.is_file():
            try:
                libs = json.loads(deps_file.read_text(encoding="utf-8")).get("libraries", {})
                for key in libs:
                    if key.startswith(f"{folder.name}/"):
                        version = key.split("/", 1)[1]
                        break
            except (json.JSONDecodeError, OSError):
                pass
        return Plugin(
            name=folder.name, version=version, plugin_type="CounterStrikeSharp",
            enabled=enabled, folder_path=str(folder), description=description,
        )

    # --- действия ---

    def install_from_zip(self, zip_path: str) -> Plugin:
        """Распаковывает zip с плагином в plugins/. Определяет корневую папку плагина."""
        archive = Path(zip_path)
        self.css_plugins_dir.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(archive) as zf:
            names = zf.namelist()
            # Если внутри архива структура addons/... — распаковываем в csgo/
            if any(n.replace("\\", "/").startswith("addons/") for n in names):
                target = self.csgo
            else:
                roots = {n.replace("\\", "/").split("/")[0] for n in names if n.strip("/")}
                if len(roots) == 1 and not any("." in r for r in roots):
                    target = self.css_plugins_dir  # архив уже содержит папку плагина
                else:
                    target = self.css_plugins_dir / archive.stem
            target.mkdir(parents=True, exist_ok=True)
            for member in zf.infolist():
                resolved = (target / member.filename).resolve()
                if not str(resolved).startswith(str(self.csgo.resolve())):
                    continue
                zf.extract(member, target)
        AppLogger.info("Плагин установлен из %s", archive.name)
        # Возвращаем последний изменённый плагин
        plugins = self.list_plugins()
        css = [p for p in plugins if p.plugin_type == "CounterStrikeSharp"]
        return max(css, key=lambda p: Path(p.folder_path).stat().st_mtime) if css else Plugin(
            name=archive.stem, version="", plugin_type="CounterStrikeSharp",
            enabled=True, folder_path=str(self.css_plugins_dir))

    def set_enabled(self, plugin: Plugin, enabled: bool) -> bool:
        """Вкл/выкл через переименование .dll <-> .dll.disabled."""
        if plugin.plugin_type != "CounterStrikeSharp":
            return False  # TODO: управление Metamod-плагинами через metaplugins.ini
        folder = Path(plugin.folder_path)
        changed = False
        if enabled:
            for dll in folder.glob("*.dll.disabled"):
                dll.rename(dll.with_name(dll.name[: -len(".disabled")]))
                changed = True
        else:
            for dll in folder.glob("*.dll"):
                dll.rename(dll.with_name(dll.name + ".disabled"))
                changed = True
        AppLogger.info("Плагин %s: enabled=%s", plugin.name, enabled)
        return changed

    def delete(self, plugin: Plugin) -> bool:
        if plugin.plugin_type != "CounterStrikeSharp":
            return False
        folder = Path(plugin.folder_path)
        if folder.is_dir() and folder.parent == self.css_plugins_dir:
            shutil.rmtree(folder)
            AppLogger.info("Плагин удалён: %s", plugin.name)
            return True
        return False

    def get_plugin_errors(self, plugin: Plugin) -> List[str]:
        """Ищет упоминания плагина в логах CounterStrikeSharp."""
        errors: List[str] = []
        logs_dir = self.csgo / "addons" / "counterstrikesharp" / "logs"
        if not logs_dir.is_dir():
            return errors
        files = sorted(logs_dir.glob("*.txt"), key=lambda f: f.stat().st_mtime)
        if not files:
            return errors
        try:
            for line in files[-1].read_text(encoding="utf-8", errors="replace").splitlines():
                if plugin.name.lower() in line.lower() and \
                        any(lvl in line for lvl in ("[ERRO", "[WARN", "error", "Exception")):
                    errors.append(line.strip())
        except OSError:
            pass
        return errors[-10:]
