"""Модель профиля сервера."""
from __future__ import annotations

import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime


@dataclass
class ServerProfile:
    name: str
    server_path: str
    port: int = 27015
    start_map: str = "de_dust2"
    launch_args: str = "-dedicated -usercon +game_type 0 +game_mode 1"
    game_mode: str = "competitive"
    rcon_password: str = ""
    description: str = ""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))
    last_used: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "ServerProfile":
        known = {f for f in cls.__dataclass_fields__}  # type: ignore[attr-defined]
        return cls(**{k: v for k, v in data.items() if k in known})

    def touch(self) -> None:
        self.last_used = datetime.now().isoformat(timespec="seconds")
