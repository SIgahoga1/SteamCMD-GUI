"""Сборка SteamCMDv2.exe (PyInstaller onefile). Запуск: python build.py"""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def main() -> int:
    for folder in ("build", "dist"):
        shutil.rmtree(ROOT / folder, ignore_errors=True)

    sep = ";" if sys.platform == "win32" else ":"
    args = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm", "--clean",
        "--onefile", "--windowed",
        "--name", "SteamCMDv2",
        "--add-data", f"app/assets{sep}app/assets",
        "--hidden-import", "psutil",
    ]
    icon = ROOT / "app" / "assets" / "app.ico"
    if icon.exists():
        args += ["--icon", str(icon)]
    args.append(str(ROOT / "main.py"))

    print(">>", " ".join(args))
    result = subprocess.run(args, cwd=ROOT, check=False)
    if result.returncode != 0:
        print("ОШИБКА СБОРКИ"); return result.returncode

    exe = ROOT / "dist" / ("SteamCMDv2.exe" if sys.platform == "win32" else "SteamCMDv2")
    print(f"\nГотово: {exe}" if exe.exists() else "\nexe не найден — смотри вывод выше")
    return 0 if exe.exists() else 1


if __name__ == "__main__":
    sys.exit(main())
