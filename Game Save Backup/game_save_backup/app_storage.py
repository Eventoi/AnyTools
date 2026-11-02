"""Хранение настроек приложения: последний путь бэкапа, известные папки, черновики."""
import json
import logging
import os
from pathlib import Path

from PySide6.QtCore import QStandardPaths

logger = logging.getLogger(__name__)


def _norm(path: str) -> str:
    return os.path.normcase(os.path.normpath(path))


def _drive_available(anchor: str) -> bool:
    return os.path.exists(anchor)


def _folder_deleted(path: str) -> bool:
    try:
        folder = Path(path)
        if folder.is_dir():
            return False
        return bool(folder.anchor) and _drive_available(folder.anchor)
    except OSError:
        return False


def _default_directory() -> Path:
    location = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppDataLocation)
    return Path(location) if location else Path.home() / ".game_save_backup"


class AppSettings:
    def __init__(self, directory: Path | None = None) -> None:
        self._directory = directory or _default_directory()
        self._directory.mkdir(parents=True, exist_ok=True)
        self._file = self._directory / "settings.json"
        self._last_backup_path = ""
        self._known_roots: list[str] = []
        self._load()

    @property
    def directory(self) -> Path:
        return self._directory

    @property
    def drafts_dir(self) -> Path:
        path = self._directory / "drafts"
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def last_backup_path(self) -> str:
        return self._last_backup_path

    def set_last_backup_path(self, path: str) -> None:
        self._last_backup_path = path
        self.add_known_root(path, save=False)
        self._save()

    @property
    def known_roots(self) -> list[str]:
        return list(self._known_roots)

    def add_known_root(self, path: str, save: bool = True) -> None:
        if not path:
            return
        if all(_norm(path) != _norm(root) for root in self._known_roots):
            self._known_roots.append(path)
            if save:
                self._save()

    def prune_missing_roots(self) -> list[str]:
        forgotten = [root for root in self._known_roots if _folder_deleted(root)]
        if forgotten:
            self._known_roots = [root for root in self._known_roots if root not in forgotten]
        if self._last_backup_path and _folder_deleted(self._last_backup_path):
            forgotten.append(self._last_backup_path)
            self._last_backup_path = ""
        if forgotten:
            for root in forgotten:
                logger.info("Забыта папка бэкапа, которой больше нет: %s", root)
            self._save()
        return forgotten

    def _load(self) -> None:
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
