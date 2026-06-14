"""SteamCMD v2 — точка входа."""
from __future__ import annotations

import sys
import traceback


def main() -> int:
    from PySide6.QtWidgets import QApplication, QMessageBox

    from app.services.logger import AppLogger
    from app.services.settings_service import SettingsService

    AppLogger.init()
    AppLogger.info("=== Запуск SteamCMD v2 ===")

    app = QApplication(sys.argv)
    app.setApplicationName("SteamCMD v2")
    app.setOrganizationName("SteamCMDv2")

    def excepthook(exc_type, exc, tb) -> None:
        text = "".join(traceback.format_exception(exc_type, exc, tb))
        AppLogger.error("Необработанная ошибка:\n%s", text)
        QMessageBox.critical(None, "Ошибка SteamCMD v2",
                             f"Произошла непредвиденная ошибка:\n\n{exc}\n\n"
                             "Подробности в app.log (страница Логи).")

    sys.excepthook = excepthook

    settings = SettingsService.instance()

    from app.gui.main_window import MainWindow
    window = MainWindow(settings)
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
