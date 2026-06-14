"""Модель игрока на сервере."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Player:
    slot: int
    nickname: str
    steam_id: str
    ip: str = ""
    ping: int = 0
    score: int = 0
    time_online: str = ""
    status: str = "active"
    userid: str = ""  # userid из вывода status — нужен для kickid
