"""МОДУЛЬ "Бэкап сэйвов": копирование сэйвов, архивация и ротация бэкапов."""
import logging
import re
import shutil
from datetime import datetime
from pathlib import Path

from send2trash import send2trash

from .constants import DARK_SOULS_MAX_BACKUPS, MAX_ARCHIVES, STAMP_FORMAT, STAMP_REGEX
from .models import GameConfig

logger = logging.getLogger(__name__)

# Папка бэкапа: "{Название игры} {штамп}"
_FOLDER_RE = re.compile(rf"^.+ (?P<stamp>{STAMP_REGEX})$")
# Архив бэкапа: "{Название игры} {штамп}.zip"
_ARCHIVE_RE = re.compile(rf"^.+ (?P<stamp>{STAMP_REGEX})\.zip$", re.IGNORECASE)


def _stamp_of(path: Path, regex: re.Pattern) -> datetime:
    match = regex.match(path.name)
    if match:
        try:
            return datetime.strptime(match.group("stamp"), STAMP_FORMAT)
        except ValueError:
            pass
    try:
        return datetime.fromtimestamp(path.stat().st_mtime)
    except OSError:
        return datetime.min


class BackupService:
    @staticmethod
    def backup_saves(config: GameConfig, now: datetime | None = None) -> Path:
        saves = Path(config.saves_path)
        if not saves.exists():
            raise FileNotFoundError(f"Путь к сэйвам не найден: {saves}")

        game_dir = Path(config.backup_path) / config.name
        game_dir.mkdir(parents=True, exist_ok=True)

        previous = BackupService._find_backup_folders(game_dir)

        stamp = (now or datetime.now()).strftime(STAMP_FORMAT)
        new_dir = game_dir / f"{config.name} {stamp}"
        new_dir.mkdir()
        try:
            if saves.is_dir():
                shutil.copytree(saves, new_dir, dirs_exist_ok=True)
            else:
                BackupService._copy_dark_souls_files(saves, new_dir)
        except Exception:
            shutil.rmtree(new_dir, ignore_errors=True)
            raise

        for folder in previous:
            BackupService._archive_folder(folder)
        BackupService._trim_archives(game_dir)
        return new_dir

    @staticmethod
    def backup_single_file(source: Path, now: datetime | None = None) -> Path:
        stamp = (now or datetime.now()).strftime(STAMP_FORMAT)
        existing = BackupService._find_dark_souls_backups(source)

        excess = len(existing) - (DARK_SOULS_MAX_BACKUPS - 1)
        for old in existing[: max(excess, 0)]:
            old.unlink()

        target = source.with_name(f"{source.stem}_{stamp}{source.suffix}")
        shutil.copy2(source, target)
        return target

    @staticmethod
    def _dark_souls_backup_pattern(source: Path) -> re.Pattern:
        return re.compile(
            rf"^{re.escape(source.stem)}_(?P<stamp>{STAMP_REGEX}){re.escape(source.suffix)}$"
        )

    @staticmethod
    def _find_dark_souls_backups(source: Path) -> list[Path]:
        pattern = BackupService._dark_souls_backup_pattern(source)
        return sorted(
            (
                item
                for item in source.parent.iterdir()
                if item.is_file() and item != source and pattern.match(item.name)
            ),
            key=lambda item: _stamp_of(item, pattern),
        )

    @staticmethod
    def _copy_dark_souls_files(source: Path, target_dir: Path) -> None:
        for file in [source, *BackupService._find_dark_souls_backups(source)]:
            shutil.copy2(file, target_dir)

    @staticmethod
    def _find_backup_folders(game_dir: Path) -> list[Path]:
        folders = [
            item
            for item in game_dir.iterdir()
            if item.is_dir() and _FOLDER_RE.match(item.name)
        ]
        return sorted(folders, key=lambda item: _stamp_of(item, _FOLDER_RE))

    @staticmethod
    def _archive_folder(folder: Path) -> None:
        shutil.make_archive(
            str(folder.parent / folder.name),
            "zip",
            root_dir=str(folder.parent),
            base_dir=folder.name,
        )
        shutil.rmtree(folder)

    @staticmethod
    def _trim_archives(game_dir: Path) -> None:
        archives = sorted(
            (
                item
                for item in game_dir.iterdir()
                if item.is_file() and _ARCHIVE_RE.match(item.name)
            ),
            key=lambda item: _stamp_of(item, _ARCHIVE_RE),
        )
        excess = len(archives) - MAX_ARCHIVES
        for old in archives[: max(excess, 0)]:
            try:
                send2trash(str(old))
            except Exception:
                logger.exception("Не удалось отправить архив в корзину: %s", old)
