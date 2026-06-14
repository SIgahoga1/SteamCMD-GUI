"""Модель плагина сервера."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List


@dataclass
class Plugin:
    name: str
    version: str
    plugin_type: str  # "CounterStrikeSharp" | "Metamod"
    enabled: bool
    folder_path: str
    description: str = ""
    errors: List[str] = field(default_factory=list)
