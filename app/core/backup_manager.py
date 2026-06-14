"""Создание/восстановление бэкапов (zip)."""
from __future__ import annotations

import json
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Callable, List, Optional

from app.models.backup import Backup
from app.services.logger import AppLogger

ProgressCb = Optional[Callable[[int, int], None]]

TYPE_SUBPATH = {
    "full": "",
    "configs": "game/csgo/cfg",
    "plugins": "game/csgo/addons",
}

SKIP_DIRS_FULL = {"steamapps", "__pycache__"}  # steamapps можно перекачать заново


class BackupManager:
    def __init__(self, backup_dir: str) -> None:
        self.backup_dir = Path(backup_dir)
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        self._index_path = self.backup_dir / "backups_index.json"

    # --- индекс ---

    def _load_index(self) -> list[dict]:
        try:
            if self._index_path.exists():
                return json.loads(self._index_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            pass
        return []

    def _save_index(self, items: list[dict]) -> None:
        self._index_path.write_text(
            json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")

    # --- API ---

    def create_backup(self, server_path: str, backup_type: str,
                      profile_id: str = "", progress_callback: ProgressCb = None) -> Backup:
        if backup_type not in TYPE_SUBPATH:
            raise ValueError(f"Неизвестный тип бэкапа: {backup_type}")
        root = Path(server_path)
        source = root / TYPE_SUBPATH[backup_type] if TYPE_SUBPATH[backup_type] else root
        if not source.is_dir():
            raise FileNotFoundError(f"Папка для бэкапа не найдена: {source}")

        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"backup_{backup_type}_{stamp}.zip"
        filepath = self.backup_dir / filename

        files = [f for f in source.rglob("*") if f.is_file()]
        if backup_type == "full":
            files = [f for f in files
                     if not (set(f.relative_to(root).parts) & SKIP_DIRS_FULL)]
        total = len(files)
        AppLogger.info("Бэкап %s: %d файлов из %s", backup_type, total, source)
        with zipfile.ZipFile(filepath, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
            for i, file in enumerate(files, 1):
                zf.write(file, file.relative_to(root))
                if progress_callback:
                    progress_callback(i, total)

        backup = Backup(
            filename=filename, filepath=str(filepath), backup_type=backup_type,
            created_at=datetime.now().isoformat(timespec="seconds"),
            size_bytes=filepath.stat().st_size, profile_id=profile_id,
        )
        index = self._load_index()
        index.append(backup.to_dict())
        self._save_index(index)
        return backup

    def list_backups(self) -> List[Backup]:
        backups: List[Backup] = []
        index = self._load_index()
        changed = False
        for item in index:
            if Path(item["filepath"]).is_file():
                backups.append(Backup(**item))
            else:
                changed = True
        if changed:
            self._save_index([b.to_dict() for b in backups])
        backups.sort(key=lambda b: b.created_at, reverse=True)
        return backups

    def restore_backup(self, backup: Backup, target_path: str,
                       progress_callback: ProgressCb = None) -> bool:
        archive = Path(backup.filepath)
        if not archive.is_file():
            raise FileNotFoundError(f"Файл бэкапа не найден: {archive}")
        target = Path(target_path)
        target.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(archive) as zf:
            members = zf.infolist()
            total = len(members)
            for i, member in enumerate(members, 1):
                resolved = (target / member.filename).resolve()
                if not str(resolved).startswith(str(target.resolve())):
                    continue
                zf.extract(member, target)
                if progress_callback:
                    progress_callback(i, total)
        AppLogger.info("Бэкап восстановлен: %s -> %s", archive.name, target)
        return True

    def delete_backup(self, backup: Backup) -> bool:
        Path(backup.filepath).unlink(missing_ok=True)
        index = [item for item in self._load_index()
                 if item.get("filepath") != backup.filepath]
        self._save_index(index)
        AppLogger.info("Бэкап удалён: %s", backup.filename)
        return True

    def cleanup_old_backups(self, max_count: int) -> int:
        backups = self.list_backups()
        removed = 0
        for backup in backups[max_count:]:
            self.delete_backup(backup)
            removed += 1
        return removed
