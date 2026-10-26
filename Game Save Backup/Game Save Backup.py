"""Точка входа приложения Game Save Backup."""
import logging
import sys
from logging.handlers import RotatingFileHandler

from PySide6.QtWidgets import QApplication

from game_save_backup.app_storage import AppSettings
from game_save_backup.constants import APP_NAME
from game_save_backup.ui.main_window import MainWindow


def setup_logging(settings: AppSettings) -> None:
    """Настраивает вывод журнала в консоль и в файл рядом с настройками."""
    handlers: list[logging.Handler] = [logging.StreamHandler()]
    try:
        handlers.append(
            RotatingFileHandler(
                settings.directory / "app.log",
                maxBytes=512 * 1024,
                backupCount=2,
                encoding="utf-8",
            )
        )
    except OSError:
        pass
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=handlers,
    )


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)

    settings = AppSettings()
    setup_logging(settings)

    window = MainWindow(settings)
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
