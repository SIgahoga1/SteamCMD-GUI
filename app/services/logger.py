"""Единый логгер приложения. Пишет в %APPDATA%/SteamCMDv2/logs/app.log с ротацией."""
from __future__ import annotations

import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path


def app_data_dir() -> Path:
    """Папка данных приложения (создаётся при первом обращении)."""
    if os.name == "nt":
        base = Path(os.environ.get("APPDATA", Path.home()))
    else:  # dev-режим на Linux/Mac
        base = Path.home() / ".config"
    path = base / "SteamCMDv2"
    path.mkdir(parents=True, exist_ok=True)
    return path


class AppLogger:
    """Singleton-обёртка над logging."""

    _logger: logging.Logger | None = None

    @classmethod
    def init(cls) -> logging.Logger:
        if cls._logger is not None:
            return cls._logger
        logger = logging.getLogger("SteamCMDv2")
        logger.setLevel(logging.DEBUG)
        fmt = logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s", "%Y-%m-%d %H:%M:%S"
        )

        log_dir = app_data_dir() / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        fh = RotatingFileHandler(
            log_dir / "app.log", maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
        )
        fh.setFormatter(fmt)
        fh.setLevel(logging.DEBUG)
        logger.addHandler(fh)

        sh = logging.StreamHandler(sys.stderr)
        sh.setFormatter(fmt)
        sh.setLevel(logging.INFO)
        logger.addHandler(sh)

        cls._logger = logger
        return logger

    @classmethod
    def get(cls) -> logging.Logger:
        return cls._logger or cls.init()

    @classmethod
    def log_file(cls) -> Path:
        return app_data_dir() / "logs" / "app.log"

    # Удобные методы
    @classmethod
    def info(cls, msg: str, *args) -> None:
        cls.get().info(msg, *args)

    @classmethod
    def warning(cls, msg: str, *args) -> None:
        cls.get().warning(msg, *args)

    @classmethod
    def error(cls, msg: str, *args, exc_info=False) -> None:
        cls.get().error(msg, *args, exc_info=exc_info)

    @classmethod
    def debug(cls, msg: str, *args) -> None:
        cls.get().debug(msg, *args)
