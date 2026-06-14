"""Управление картами: сканирование .vpk, кастомные карты, mapcycle/maplist."""
from __future__ import annotations

from pathlib import Path
from typing import List

from app.services.logger import AppLogger

STANDARD_MAPS = [
    "de_dust2", "de_mirage", "de_inferno", "de_nuke", "de_ancient",
    "de_anubis", "de_overpass", "de_vertigo", "de_train", "cs_office", "cs_italy",
]


class MapManager:
    def __init__(self, server_path: str) -> None:
        self.server_path = Path(server_path)
        self.maps_dir = self.server_path / "game" / "csgo" / "maps"
        self.cfg_dir = self.server_path / "game" / "csgo" / "cfg"

    def scan_vpk_maps(self) -> List[str]:
        """Карты из game/csgo/maps/*.vpk (без служебных vanity/workshop-префиксов)."""
        if not self.maps_dir.is_dir():
            return []
        names = set()
        for vpk in self.maps_dir.glob("*.vpk"):
            stem = vpk.stem
            if stem.endswith("_vanity") or stem == "graphics_settings":
                continue
            names.add(stem)
        return sorted(names)

    def all_maps(self, custom_maps: List[str]) -> List[str]:
        found = self.scan_vpk_maps()
        merged = list(dict.fromkeys(found + STANDARD_MAPS + list(custom_maps)))
        return merged

    def check_integrity(self) -> List[str]:
        """Возвращает список проблем (нулевой размер vpk и т.п.)."""
        issues: List[str] = []
        if not self.maps_dir.is_dir():
            issues.append(f"Папка карт не найдена: {self.maps_dir}")
            return issues
        for vpk in self.maps_dir.glob("*.vpk"):
            try:
                if vpk.stat().st_size == 0:
                    issues.append(f"Файл нулевого размера: {vpk.name}")
            except OSError as exc:
                issues.append(f"Не читается {vpk.name}: {exc}")
        return issues

    def generate_mapcycle(self, maps: List[str]) -> Path:
        self.cfg_dir.mkdir(parents=True, exist_ok=True)
        path = self.cfg_dir / "mapcycle.txt"
        path.write_text("\n".join(maps) + "\n", encoding="utf-8")
        AppLogger.info("mapcycle.txt сгенерирован (%d карт)", len(maps))
        return path

    def generate_maplist(self, maps: List[str]) -> Path:
        self.cfg_dir.mkdir(parents=True, exist_ok=True)
        path = self.cfg_dir / "maplist.txt"
        path.write_text("\n".join(maps) + "\n", encoding="utf-8")
        AppLogger.info("maplist.txt сгенерирован (%d карт)", len(maps))
        return path
