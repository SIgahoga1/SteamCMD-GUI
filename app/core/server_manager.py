"""Запуск/остановка/перезапуск процесса CS2 Dedicated Server."""
from __future__ import annotations

import os
import shlex
import subprocess
import threading
import time
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QObject, Signal

from app.core.process_manager import ProcessManager
from app.models.server_profile import ServerProfile
from app.services.logger import AppLogger

STATE_OFFLINE = "OFFLINE"
STATE_STARTING = "STARTING"
STATE_ONLINE = "ONLINE"
STATE_STOPPING = "STOPPING"


def find_server_exe(server_path: Path) -> Optional[Path]:
    """Ищет исполняемый файл сервера в папке установки."""
    candidates = [
        server_path / "game" / "bin" / "win64" / "cs2.exe",
        server_path / "cs2.exe",
        server_path / "srcds.exe",
    ]
    for cand in candidates:
        if cand.is_file():
            return cand
    return None


class ServerManager(QObject):
    """Управляет жизненным циклом серверного процесса.

    Сигналы:
        state_changed(str)  — OFFLINE/STARTING/ONLINE/STOPPING
        output_line(str)    — строка stdout сервера
        crashed()           — процесс умер без команды stop
    """

    state_changed = Signal(str)
    output_line = Signal(str)
    crashed = Signal()

    def __init__(self, profile: ServerProfile, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self.profile = profile
        self.process_manager = ProcessManager()
        self._proc: Optional[subprocess.Popen] = None
        self._state = STATE_OFFLINE
        self._intentional_stop = False
        self._reader: Optional[threading.Thread] = None

    # --- состояние ---

    @property
    def state(self) -> str:
        return self._state

    def _set_state(self, state: str) -> None:
        if state != self._state:
            self._state = state
            self.state_changed.emit(state)

    def is_running(self) -> bool:
        return self._proc is not None and self._proc.poll() is None

    # --- команды ---

    def get_launch_command(self) -> list:
        exe = find_server_exe(Path(self.profile.server_path))
        if exe is None:
            raise FileNotFoundError(
                f"Не найден cs2.exe/srcds.exe в {self.profile.server_path}")
        args = shlex.split(self.profile.launch_args, posix=False)
        cmd = [str(exe)] + args
        if "-port" not in self.profile.launch_args:
            cmd += ["-port", str(self.profile.port)]
        if "+map" not in self.profile.launch_args and self.profile.start_map:
            cmd += ["+map", self.profile.start_map]
        if self.profile.rcon_password and "rcon_password" not in self.profile.launch_args:
            cmd += ["+rcon_password", self.profile.rcon_password]
        return cmd

    def start(self) -> bool:
        if self.is_running():
            return True
        try:
            cmd = self.get_launch_command()
        except FileNotFoundError as exc:
            AppLogger.error(str(exc))
            self.output_line.emit(f"[ОШИБКА] {exc}")
            return False
        self._intentional_stop = False
        self._set_state(STATE_STARTING)
        AppLogger.info("Запуск сервера: %s", " ".join(cmd))
        try:
            creationflags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
            self._proc = subprocess.Popen(
                cmd,
                cwd=str(Path(cmd[0]).parent),
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
                creationflags=creationflags,
            )
        except OSError as exc:
            AppLogger.error("Не удалось запустить сервер: %s", exc)
            self.output_line.emit(f"[ОШИБКА] Не удалось запустить сервер: {exc}")
            self._set_state(STATE_OFFLINE)
            return False
        self.process_manager.attach(self._proc.pid)
        self._reader = threading.Thread(target=self._read_output, daemon=True)
        self._reader.start()
        return True

    def _read_output(self) -> None:
        proc = self._proc
        if proc is None or proc.stdout is None:
            return
        marked_online = False
        for line in proc.stdout:
            line = line.rstrip("\n")
            self.output_line.emit(line)
            if not marked_online:
                lowered = line.lower()
                if any(tok in lowered for tok in
                       ("host activate", "vac secure mode", "server is hibernating",
                        "gc connection established", "connection to steam servers successful")):
                    marked_online = True
                    self._set_state(STATE_ONLINE)
        proc.wait()
        code = proc.returncode
        self.process_manager.detach()
        was_intentional = self._intentional_stop
        self._set_state(STATE_OFFLINE)
        AppLogger.info("Сервер завершился (код %s, ожидаемо=%s)", code, was_intentional)
        if not was_intentional:
            self.crashed.emit()

    def send_stdin(self, command: str) -> bool:
        """Отправка команды в stdin серверного процесса."""
        if self._proc and self._proc.poll() is None and self._proc.stdin:
            try:
                self._proc.stdin.write(command + "\n")
                self._proc.stdin.flush()
                return True
            except OSError as exc:
                AppLogger.error("Ошибка записи в stdin: %s", exc)
        return False

    def stop(self) -> bool:
        if not self.is_running():
            self._set_state(STATE_OFFLINE)
            return True
        self._intentional_stop = True
        self._set_state(STATE_STOPPING)
        assert self._proc is not None
        self.send_stdin("quit")
        try:
            self._proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            AppLogger.warning("Сервер не вышел по quit — terminate()")
            self._proc.terminate()
            try:
                self._proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._proc.kill()
        self.process_manager.detach()
        self._set_state(STATE_OFFLINE)
        return True

    def restart(self) -> bool:
        self.stop()
        time.sleep(1.0)
        return self.start()

    def get_process_info(self) -> dict:
        return self.process_manager.get_info()
