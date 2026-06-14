"""Загрузка файлов с коллбэком прогресса. Используется для SteamCMD/Metamod/CSSharp."""
from __future__ import annotations

import zipfile
from pathlib import Path
from typing import Callable, Optional

import requests

from app.services.logger import AppLogger

ProgressCb = Optional[Callable[[int, int], None]]  # (загружено_байт, всего_байт)

CHUNK = 64 * 1024
TIMEOUT = 30


def download_file(url: str, dest: Path, progress_callback: ProgressCb = None) -> Path:
    """Скачивает url в dest. Возвращает dest, бросает исключение при ошибке."""
    AppLogger.info("Загрузка: %s -> %s", url, dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    with requests.get(url, stream=True, timeout=TIMEOUT) as resp:
        resp.raise_for_status()
        total = int(resp.headers.get("Content-Length", 0))
        done = 0
        with open(dest, "wb") as fh:
            for chunk in resp.iter_content(CHUNK):
                fh.write(chunk)
                done += len(chunk)
                if progress_callback:
                    progress_callback(done, total)
    AppLogger.info("Загрузка завершена: %s (%d байт)", dest.name, dest.stat().st_size)
    return dest


def extract_zip(archive: Path, target_dir: Path,
                progress_callback: ProgressCb = None) -> None:
    """Распаковывает zip-архив в target_dir с защитой от path traversal."""
    target_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive) as zf:
        members = zf.infolist()
        total = len(members)
        for i, member in enumerate(members, 1):
            resolved = (target_dir / member.filename).resolve()
            if not str(resolved).startswith(str(target_dir.resolve())):
                AppLogger.warning("Пропущен подозрительный путь в архиве: %s", member.filename)
                continue
            zf.extract(member, target_dir)
            if progress_callback:
                progress_callback(i, total)
    AppLogger.info("Распакован архив %s -> %s", archive.name, target_dir)
