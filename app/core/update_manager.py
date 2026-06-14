"""Определение установленных компонентов и их версий + загрузка Metamod/CSSharp."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Callable, Optional

import requests

from app.services.downloader import download_file, extract_zip
from app.services.logger import AppLogger

ProgressCb = Optional[Callable[[int, int], None]]

METAMOD_DL_PAGE = "https://www.sourcemm.net/downloads.php?branch=master"
CSSHARP_API = "https://api.github.com/repos/roflmuffin/CounterStrikeSharp/releases/latest"
HTTP_TIMEOUT = 20


def detect_components(server_path: str) -> dict:
    """Возвращает словарь компонентов: {name: {installed: bool, version: str, path: str}}."""
    root = Path(server_path)
    csgo = root / "game" / "csgo"
    result: dict = {}

    exe = None
    for cand in (root / "game" / "bin" / "win64" / "cs2.exe", root / "cs2.exe",
                 root / "srcds.exe"):
        if cand.is_file():
            exe = cand
            break
    cs2_version = ""
    steam_inf = csgo / "steam.inf"
    if steam_inf.is_file():
        m = re.search(r"PatchVersion\s*=\s*([\d.]+)",
                      steam_inf.read_text(encoding="utf-8", errors="replace"))
        if m:
            cs2_version = m.group(1)
    result["CS2 Server"] = {"installed": exe is not None, "version": cs2_version,
                            "path": str(exe) if exe else ""}

    mm_dir = csgo / "addons" / "metamod"
    mm_version = ""
    if mm_dir.is_dir():
        for vdf in mm_dir.glob("*.vdf"):
            m = re.search(r'"version"\s+"([^"]+)"',
                          vdf.read_text(encoding="utf-8", errors="replace"))
            if m:
                mm_version = m.group(1)
                break
    result["Metamod:Source"] = {"installed": mm_dir.is_dir(), "version": mm_version,
                                "path": str(mm_dir) if mm_dir.is_dir() else ""}

    css_dir = csgo / "addons" / "counterstrikesharp"
    css_version = ""
    vjson = css_dir / "version.json"
    if vjson.is_file():
        try:
            css_version = str(json.loads(vjson.read_text(encoding="utf-8")).get("version", ""))
        except (json.JSONDecodeError, OSError):
            pass
    result["CounterStrikeSharp"] = {"installed": css_dir.is_dir(), "version": css_version,
                                    "path": str(css_dir) if css_dir.is_dir() else ""}
    return result


def get_metamod_windows_url() -> str:
    """Берёт актуальную dev-сборку Metamod:Source 2.x для Windows со страницы загрузок."""
    resp = requests.get(METAMOD_DL_PAGE, timeout=HTTP_TIMEOUT)
    resp.raise_for_status()
    m = re.search(r'href="(https://mms\.alliedmods\.net/mmsdrop/[^"]+windows\.zip)"',
                  resp.text)
    if not m:
        raise RuntimeError("Не удалось найти ссылку на Metamod (windows.zip)")
    return m.group(1)


def get_cssharp_windows_url() -> str:
    """Берёт последний релиз CounterStrikeSharp (windows, with-runtime) с GitHub."""
    resp = requests.get(CSSHARP_API, timeout=HTTP_TIMEOUT,
                        headers={"Accept": "application/vnd.github+json"})
    resp.raise_for_status()
    assets = resp.json().get("assets", [])
    def score(asset: dict) -> int:
        name = asset["name"].lower()
        if "linux" in name or not name.endswith(".zip"):
            return -1
        sc = 0
        if "windows" in name or "win" in name:
            sc += 2
        if "with-runtime" in name:
            sc += 1
        return sc
    best = max(assets, key=score, default=None)
    if not best or score(best) < 2:
        raise RuntimeError("Не найден windows-архив CounterStrikeSharp в релизе")
    return best["browser_download_url"]


def install_metamod(server_path: str, progress_callback: ProgressCb = None) -> bool:
    """Скачивает и распаковывает Metamod:Source в game/csgo/."""
    try:
        url = get_metamod_windows_url()
        csgo = Path(server_path) / "game" / "csgo"
        archive = csgo / "_metamod_tmp.zip"
        download_file(url, archive, progress_callback)
        extract_zip(archive, csgo)
        archive.unlink(missing_ok=True)
        patch_gameinfo(server_path)
        return (csgo / "addons" / "metamod").is_dir()
    except Exception as exc:  # noqa: BLE001
        AppLogger.error("Установка Metamod не удалась: %s", exc, exc_info=True)
        return False


def install_cssharp(server_path: str, progress_callback: ProgressCb = None) -> bool:
    """Скачивает и распаковывает CounterStrikeSharp в game/csgo/."""
    try:
        url = get_cssharp_windows_url()
        csgo = Path(server_path) / "game" / "csgo"
        archive = csgo / "_cssharp_tmp.zip"
        download_file(url, archive, progress_callback)
        extract_zip(archive, csgo)
        archive.unlink(missing_ok=True)
        return (csgo / "addons" / "counterstrikesharp").is_dir()
    except Exception as exc:  # noqa: BLE001
        AppLogger.error("Установка CounterStrikeSharp не удалась: %s", exc, exc_info=True)
        return False


def patch_gameinfo(server_path: str) -> bool:
    """Добавляет 'Game csgo/addons/metamod' в gameinfo.gi (нужно для загрузки Metamod)."""
    gi = Path(server_path) / "game" / "csgo" / "gameinfo.gi"
    if not gi.is_file():
        return False
    text = gi.read_text(encoding="utf-8", errors="replace")
    if "csgo/addons/metamod" in text:
        return True
    new_text, count = re.subn(
        r"(Game_LowViolence\s+csgo_lv\s*(?://[^\n]*)?\n)",
        r"\1\t\t\tGame\tcsgo/addons/metamod\n",
        text, count=1,
    )
    if count == 0:
        new_text, count = re.subn(
            r"(SearchPaths\s*\{\s*\n)",
            r"\1\t\t\tGame\tcsgo/addons/metamod\n",
            text, count=1,
        )
    if count:
        backup = gi.with_suffix(".gi.bak")
        if not backup.exists():
            backup.write_text(text, encoding="utf-8")
        gi.write_text(new_text, encoding="utf-8")
        AppLogger.info("gameinfo.gi пропатчен (metamod searchpath)")
        return True
    AppLogger.warning("Не удалось пропатчить gameinfo.gi автоматически")
    return False
