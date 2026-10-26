"""Хранение настроек приложения: последний путь бэкапа, известные папки, черновики."""
import json
import logging
import os
from pathlib import Path

from PySide6.QtCore import QStandardPaths

logger = logging.getLogger(__name__)


def _norm(path: str) -> str:
    """Нормализует путь для сравнения."""
    return os.path.normcase(os.path.normpath(path))


def _default_directory() -> Path:
    """Папка данных приложения в профиле пользователя."""
    location = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppDataLocation)
    return Path(location) if location else Path.home() / ".game_save_backup"


class AppSettings:
    """Настройки приложения, сохраняемые между запусками."""

    def __init__(self, directory: Path | None = None) -> None:
        self._directory = directory or _default_directory()
        self._directory.mkdir(parents=True, exist_ok=True)
        self._file = self._directory / "settings.json"
        self._last_backup_path = ""
        self._known_roots: list[str] = []
        self._load()

    @property
    def directory(self) -> Path:
        """Папка данных приложения."""
        return self._directory

    @property
    def drafts_dir(self) -> Path:
        """Папка конфигураций, для которых ещё не указан путь бэкапа."""
        path = self._directory / "drafts"
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def last_backup_path(self) -> str:
        """Последний указанный пользователем путь в поле «Бэкап сэйвов»."""
        return self._last_backup_path

    def set_last_backup_path(self, path: str) -> None:
        """Запоминает последний путь бэкапа и добавляет его в список известных."""
        self._last_backup_path = path
        self.add_known_root(path, save=False)
        self._save()

    @property
    def known_roots(self) -> list[str]:
        """Все папки бэкапов, которые когда-либо использовались."""
        return list(self._known_roots)

    def add_known_root(self, path: str, save: bool = True) -> None:
        """Добавляет папку бэкапов в список известных (без дублей)."""
        if not path:
            return
        if all(_norm(path) != _norm(root) for root in self._known_roots):
            self._known_roots.append(path)
            if save:
                self._save()

    def _load(self) -> None:
        """Читает настройки с диска; при ошибке остаются значения по умолчанию."""
        if not self._file.is_file():
            return
        try:
            data = json.loads(self._file.read_text(encoding="utf-8"))
            last = data.get("last_backup_path", "")
            roots = data.get("known_roots", [])
            if isinstance(last, str):
                self._last_backup_path = last
            if isinstance(roots, list):
                self._known_roots = [r for r in roots if isinstance(r, str) and r]
        except (OSError, ValueError, AttributeError):
            logger.exception("Не удалось прочитать настройки")

    def _save(self) -> None:
        """Записывает настройки на диск."""
        data = {
            "last_backup_path": self._last_backup_path,
            "known_roots": self._known_roots,
        }
        try:
            tmp = self._file.with_name(self._file.name + ".tmp")
            tmp.write_text(json.dumps(data, ensure_ascii=False, indent=4), encoding="utf-8")
            os.replace(tmp, self._file)
        except OSError:
            logger.exception("Не удалось сохранить настройки")
