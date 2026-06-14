"""Установка SteamCMD и операции обновления/валидации CS2 Server."""
from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Callable, Optional

from app.services.downloader import download_file, extract_zip
from app.services.logger import AppLogger

STEAMCMD_URL = "https://steamcdn-a.akamaihd.net/client/installer/steamcmd.zip"
CS2_APP_ID = "730"

OutputCb = Optional[Callable[[str], None]]
ProgressCb = Optional[Callable[[int, int], None]]


class SteamCMDManager:
    """Обёртка над steamcmd.exe."""

    def __init__(self, steamcmd_path: str) -> None:
        """steamcmd_path — папка, где лежит (или будет лежать) steamcmd.exe."""
        self.steamcmd_dir = Path(steamcmd_path)

    @property
    def exe_path(self) -> Path:
        name = "steamcmd.exe" if os.name == "nt" else "steamcmd.sh"
        return self.steamcmd_dir / name

    def is_installed(self) -> bool:
        return self.exe_path.is_file()

    def install(self, install_path: str = "", progress_callback: ProgressCb = None) -> bool:
        """Скачивает и распаковывает SteamCMD."""
        target = Path(install_path) if install_path else self.steamcmd_dir
        target.mkdir(parents=True, exist_ok=True)
        archive = target / "steamcmd.zip"
        try:
            download_file(STEAMCMD_URL, archive, progress_callback)
            extract_zip(archive, target)
            archive.unlink(missing_ok=True)
            self.steamcmd_dir = target
            return self.is_installed()
        except Exception as exc:  # noqa: BLE001 — показываем пользователю любую ошибку
            AppLogger.error("Установка SteamCMD не удалась: %s", exc, exc_info=True)
            return False

    def run_command(self, args: list, stdout_callback: OutputCb = None) -> int:
        """Запускает steamcmd с аргументами, стримит вывод построчно."""
        if not self.is_installed():
            raise FileNotFoundError(f"SteamCMD не найден: {self.exe_path}")
        cmd = [str(self.exe_path)] + args
        AppLogger.info("SteamCMD: %s", " ".join(cmd))
        creationflags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        proc = subprocess.Popen(
            cmd,
            cwd=str(self.steamcmd_dir),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
            creationflags=creationflags,
        )
        assert proc.stdout is not None
        for line in proc.stdout:
            line = line.rstrip("\n")
            if stdout_callback:
                stdout_callback(line)
        proc.wait()
        # steamcmd часто возвращает 7 при штатном +quit на Windows — не считаем ошибкой
        AppLogger.info("SteamCMD завершился с кодом %s", proc.returncode)
        return proc.returncode

    def _app_update(self, server_path: str, validate: bool,
                    stdout_callback: OutputCb = None) -> bool:
        args = [
            "+force_install_dir", str(Path(server_path)),
            "+login", "anonymous",
            "+app_update", CS2_APP_ID,
        ]
        if validate:
            args.append("validate")
        args.append("+quit")
        code = self.run_command(args, stdout_callback)
        return code in (0, 7)

    def install_cs2_server(self, server_path: str,
                           progress_callback: OutputCb = None) -> bool:
        return self._app_update(server_path, validate=True, stdout_callback=progress_callback)

    def update_cs2_server(self, server_path: str,
                          progress_callback: OutputCb = None) -> bool:
        return self._app_update(server_path, validate=False, stdout_callback=progress_callback)

    def validate_files(self, server_path: str,
                       progress_callback: OutputCb = None) -> bool:
        return self._app_update(server_path, validate=True, stdout_callback=progress_callback)
