"""Модель бэкапа."""
from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass
class Backup:
    filename: str
    filepath: str
    backup_type: str  # "full" | "configs" | "plugins"
    created_at: str
    size_bytes: int
    profile_id: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    @property
    def size_human(self) -> str:
        size = float(self.size_bytes)
        for unit in ("B", "KB", "MB", "GB"):
            if size < 1024 or unit == "GB":
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} GB"
