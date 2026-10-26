"""Сессия запуска игры: запуск, ожидание процесса, бэкап по таймеру и после закрытия."""
import logging
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

import psutil
from PySide6.QtCore import QThread, Signal

from . import constants as c
from .backup_service import BackupService
from .models import GameConfig

logger = logging.getLogger(__name__)

# Период опроса списка процессов, секунд
POLL_INTERVAL_SEC = 1.0
# Сколько опросов подряд процесс должен отсутствовать, чтобы считать игру закрытой
CLOSE_CONFIRM_POLLS = 3


def find_game_processes(exe_path: str) -> list[psutil.Process]:
    """Ищет запущенные процессы игры по пути или имени exe-файла."""
    target_path = os.path.normcase(os.path.abspath(exe_path))
    target_name = os.path.basename(exe_path).lower()
    found: list[psutil.Process] = []
    for process in psutil.process_iter(["name", "exe", "status"]):
        try:
            info = process.info
            if info.get("status") == psutil.STATUS_ZOMBIE:
                continue
            exe = info.get("exe")
            name = info.get("name")
            if exe and os.path.normcase(os.path.abspath(exe)) == target_path:
                found.append(process)
            elif name and name.lower() == target_name:
                found.append(process)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return found


class GameSession(QThread):
    """Фоновый поток: запускает игру, следит за процессом и делает бэкапы."""

    # Добавить строку в окно информации
    log_line = Signal(str)
    # Заменить последнюю строку окна информации (обратный таймер)
    log_replace_last = Signal(str)

    def __init__(self, config: GameConfig, parent=None) -> None:
        super().__init__(parent)
        self._config = config
        self._stop_requested = threading.Event()

    def request_stop(self) -> None:
        """Просит поток завершиться (например, при закрытии приложения)."""
        self._stop_requested.set()

    def run(self) -> None:
        try:
            self._run_session()
        except Exception:
            logger.exception("Ошибка во время сессии игры")

    # ---------------------------------------------------------- Сценарий
    def _run_session(self) -> None:
        config = self._config
        self.log_line.emit(c.MSG_WAITING_START.format(name=config.name))

        # Если игра уже запущена вручную, дубликат не запускаем
        if not find_game_processes(config.exe_path):
            try:
                self._launch_game()
            except OSError as error:
                self.log_line.emit(c.MSG_LAUNCH_ERROR.format(error=error))
                self._countdown()
                return

        if not self._wait_for_start():
            return

        self._print_game_info()
        self._wait_for_close()
        if self._stop_requested.is_set():
            return

        self.log_line.emit(c.MSG_CLOSED.format(name=config.name))
        self._run_backup_module()
        self._countdown()

    def _launch_game(self) -> None:
        """Запускает игру через игровой клиент (URL) или напрямую через exe-файл."""
        config = self._config
        if config.use_client:
            self._open_target(config.url)
            return
        exe_dir = str(Path(config.exe_path).parent)
        if sys.platform == "win32":
            # startfile корректно обрабатывает приложения, требующие повышения прав
            os.startfile(config.exe_path, cwd=exe_dir)
        else:
            subprocess.Popen([config.exe_path], cwd=exe_dir)

    @staticmethod
    def _open_target(target: str) -> None:
        """Открывает URL средствами операционной системы."""
        if sys.platform == "win32":
            os.startfile(target)
        elif sys.platform == "darwin":
            subprocess.Popen(["open", target])
        else:
            subprocess.Popen(["xdg-open", target])

    def _wait_for_start(self) -> bool:
        """Ждёт появления процесса игры. False — если ожидание прервано."""
        while not self._stop_requested.is_set():
            if find_game_processes(self._config.exe_path):
                return True
            self._stop_requested.wait(POLL_INTERVAL_SEC)
        return False

    def _print_game_info(self) -> None:
        """Выводит информацию о запущенной игре."""
        config = self._config
        lines = [
            c.MSG_STARTED.format(name=config.name),
            c.MSG_INFO_HEADER,
            c.MSG_INFO_GAME.format(name=config.name),
            c.MSG_INFO_PROCESS.format(exe=Path(config.exe_path).name),
            c.MSG_INFO_SAVES.format(saves=config.saves_path),
            c.MSG_INFO_BACKUP.format(backup=config.backup_path),
            c.MSG_INFO_FOOTER,
            c.MSG_WAITING_CLOSE.format(name=config.name),
        ]
        for line in lines:
            self.log_line.emit(line)

    def _wait_for_close(self) -> None:
        """Ждёт закрытия игры, в режиме Dark Souls делает бэкап файла по таймеру."""
        config = self._config
        next_dark_souls_backup = time.monotonic() + c.DARK_SOULS_INTERVAL_SEC
        missing_polls = 0

        while not self._stop_requested.is_set():
            if find_game_processes(config.exe_path):
                missing_polls = 0
            else:
                missing_polls += 1
                if missing_polls >= CLOSE_CONFIRM_POLLS:
                    return

            if time.monotonic() >= next_dark_souls_backup:
                next_dark_souls_backup += c.DARK_SOULS_INTERVAL_SEC
                self._dark_souls_backup()

            self._stop_requested.wait(POLL_INTERVAL_SEC)

    def _dark_souls_backup(self) -> None:
        """Бэкап выбранного файла сэйва (режим Dark Souls)."""
        config = self._config
        saves = Path(config.saves_path)
        if not (config.dark_souls_mode and saves.is_file()):
            return
        try:
            BackupService.backup_single_file(saves)
        except OSError:
            logger.exception("Не удалось сделать бэкап файла сэйва: %s", saves)

    def _run_backup_module(self) -> None:
        """Запускает МОДУЛЬ "Бэкап сэйвов" и сообщает о результате."""
        try:
            BackupService.backup_saves(self._config)
        except Exception as error:
            logger.exception("Ошибка бэкапа сэйвов")
            self.log_line.emit(c.MSG_BACKUP_ERROR.format(error=error))
            return
        self.log_line.emit(c.MSG_BACKUP_DONE)

    def _countdown(self) -> None:
        """Обратный таймер одной строкой до закрытия информации о бэкапе."""
        for seconds in range(c.COUNTDOWN_START_SEC, 0, -1):
            text = c.MSG_COUNTDOWN.format(seconds=seconds)
            if seconds == c.COUNTDOWN_START_SEC:
                self.log_line.emit(text)
            else:
                self.log_replace_last.emit(text)
            if self._stop_requested.wait(1.0):
                return
