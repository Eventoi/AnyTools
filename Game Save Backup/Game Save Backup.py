"""Точка входа приложения Game Save Backup."""
import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from game_save_backup.app_storage import AppSettings
from game_save_backup.constants import APP_ICON_FILE, APP_NAME
from game_save_backup.ui.main_window import MainWindow

APP_USER_MODEL_ID = "GameSaveBackup.App"


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


def find_app_icon() -> Path | None:
    folders: list[Path] = []
    bundle_dir = getattr(sys, "_MEIPASS", None)
    if bundle_dir:
        folders.append(Path(bundle_dir))
    if getattr(sys, "frozen", False):
        folders.append(Path(sys.executable).resolve().parent)
    folders.append(Path(__file__).resolve().parent)

    for folder in folders:
        icon_file = folder / APP_ICON_FILE
        if icon_file.is_file():
            return icon_file
    return None


def apply_app_icon(app: QApplication) -> bool:
    icon_file = find_app_icon()
    if icon_file is None:
        logging.getLogger(__name__).warning("Файл значка не найден: %s", APP_ICON_FILE)
        return False
    icon = QIcon(str(icon_file))
    if icon.isNull():
        logging.getLogger(__name__).warning("Не удалось загрузить значок: %s", icon_file)
        return False
    app.setWindowIcon(icon)
    return True


def set_app_user_model_id() -> None:
    if sys.platform != "win32":
        return
    try:
        import ctypes

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_USER_MODEL_ID)
    except (AttributeError, OSError):
        pass


def install_exception_hook() -> None:
    def hook(exc_type, exc_value, exc_traceback) -> None:
        logging.getLogger("uncaught").critical(
            "Необработанное исключение", exc_info=(exc_type, exc_value, exc_traceback)
        )
        sys.__excepthook__(exc_type, exc_value, exc_traceback)

    sys.excepthook = hook


def main() -> int:
    set_app_user_model_id()
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)

    settings = AppSettings()
    setup_logging(settings)
    install_exception_hook()
    apply_app_icon(app)
    logging.getLogger(__name__).info("Журнал приложения: %s", settings.directory / "app.log")

    window = MainWindow(settings)
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
