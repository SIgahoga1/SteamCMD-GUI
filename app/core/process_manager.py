"""Мониторинг процесса сервера: PID, CPU, RAM, аптайм (через psutil)."""
from __future__ import annotations

import time
from typing import Optional

import psutil

from app.services.logger import AppLogger


class ProcessManager:
    """Следит за конкретным PID серверного процесса."""

    def __init__(self) -> None:
        self._proc: Optional[psutil.Process] = None
        self._started_at: float = 0.0

    def attach(self, pid: int) -> bool:
        try:
            self._proc = psutil.Process(pid)
            self._started_at = self._proc.create_time()
            self._proc.cpu_percent(interval=None)  # прогрев счётчика
            return True
        except (psutil.NoSuchProcess, psutil.AccessDenied) as exc:
            AppLogger.error("Не удалось подключиться к процессу %s: %s", pid, exc)
            self._proc = None
            return False

    def detach(self) -> None:
        self._proc = None
        self._started_at = 0.0

    @property
    def pid(self) -> Optional[int]:
        return self._proc.pid if self._proc else None

    def is_running(self) -> bool:
        try:
            return bool(self._proc and self._proc.is_running()
                        and self._proc.status() != psutil.STATUS_ZOMBIE)
        except psutil.NoSuchProcess:
            return False

    def get_info(self) -> dict:
        """{pid, cpu_percent, ram_mb, uptime_sec, running}"""
        if not self.is_running():
            return {"pid": None, "cpu_percent": 0.0, "ram_mb": 0.0,
                    "uptime_sec": 0, "running": False}
        assert self._proc is not None
        try:
            with self._proc.oneshot():
                cpu = self._proc.cpu_percent(interval=None) / max(psutil.cpu_count() or 1, 1)
                ram = self._proc.memory_info().rss / (1024 * 1024)
                uptime = int(time.time() - self._started_at)
            return {"pid": self._proc.pid, "cpu_percent": round(cpu, 1),
                    "ram_mb": round(ram, 1), "uptime_sec": uptime, "running": True}
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return {"pid": None, "cpu_percent": 0.0, "ram_mb": 0.0,
                    "uptime_sec": 0, "running": False}

    @staticmethod
    def format_uptime(seconds: int) -> str:
        h, rem = divmod(seconds, 3600)
        m, s = divmod(rem, 60)
        return f"{h:02d}:{m:02d}:{s:02d}"

    @staticmethod
    def find_cs2_processes() -> list[dict]:
        """Ищет запущенные процессы cs2.exe (для подключения к уже работающему серверу)."""
        found = []
        for proc in psutil.process_iter(["pid", "name", "exe", "cmdline"]):
            try:
                name = (proc.info["name"] or "").lower()
                if name in ("cs2.exe", "cs2", "srcds.exe"):
                    cmdline = proc.info.get("cmdline") or []
                    if "-dedicated" in cmdline or name == "srcds.exe":
                        found.append({"pid": proc.info["pid"], "name": proc.info["name"],
                                      "exe": proc.info.get("exe") or ""})
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        return found
