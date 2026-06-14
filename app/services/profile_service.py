"""Хранилище профилей серверов: %APPDATA%/SteamCMDv2/profiles.json."""
from __future__ import annotations

import json
from pathlib import Path
from typing import List, Optional

from app.models.server_profile import ServerProfile
from app.services.logger import AppLogger, app_data_dir


class ProfileService:
    """CRUD профилей серверов. Singleton."""

    _instance: "ProfileService | None" = None

    def __init__(self) -> None:
        self._path = app_data_dir() / "profiles.json"
        self._profiles: List[ServerProfile] = []
        self.load()

    @classmethod
    def instance(cls) -> "ProfileService":
        if cls._instance is None:
            cls._instance = ProfileService()
        return cls._instance

    def load(self) -> None:
        self._profiles = []
        try:
            if self._path.exists():
                raw = json.loads(self._path.read_text(encoding="utf-8"))
                self._profiles = [ServerProfile.from_dict(item) for item in raw]
        except (OSError, json.JSONDecodeError, TypeError) as exc:
            AppLogger.error("Не удалось прочитать profiles.json: %s", exc)

    def save(self) -> None:
        try:
            self._path.write_text(
                json.dumps([p.to_dict() for p in self._profiles], ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except OSError as exc:
            AppLogger.error("Не удалось сохранить profiles.json: %s", exc)

    # --- CRUD ---

    def all(self) -> List[ServerProfile]:
        return list(self._profiles)

    def is_empty(self) -> bool:
        return not self._profiles

    def get(self, profile_id: str) -> Optional[ServerProfile]:
        return next((p for p in self._profiles if p.id == profile_id), None)

    def add(self, profile: ServerProfile) -> None:
        self._profiles.append(profile)
        self.save()
        AppLogger.info("Профиль добавлен: %s (%s)", profile.name, profile.id)

    def update(self, profile: ServerProfile) -> None:
        for i, existing in enumerate(self._profiles):
            if existing.id == profile.id:
                self._profiles[i] = profile
                break
        self.save()

    def delete(self, profile_id: str) -> None:
        self._profiles = [p for p in self._profiles if p.id != profile_id]
        self.save()
        AppLogger.info("Профиль удалён: %s", profile_id)

    def clone(self, profile_id: str) -> Optional[ServerProfile]:
        src = self.get(profile_id)
        if src is None:
            return None
        data = src.to_dict()
        data.pop("id", None)
        data.pop("created_at", None)
        data["name"] = f"{src.name} (копия)"
        copy_profile = ServerProfile.from_dict(data)
        self.add(copy_profile)
        return copy_profile

    # --- импорт/экспорт ---

    def export_profile(self, profile_id: str, path: Path) -> bool:
        profile = self.get(profile_id)
        if profile is None:
            return False
        path.write_text(
            json.dumps(profile.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return True

    def import_profile(self, path: Path) -> ServerProfile:
        data = json.loads(path.read_text(encoding="utf-8"))
        profile = ServerProfile.from_dict(data)
        if self.get(profile.id):  # не допускаем дубликат id
            data.pop("id", None)
            profile = ServerProfile.from_dict(data)
        self.add(profile)
        return profile
