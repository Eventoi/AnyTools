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
    """Возвращает дату бэкапа из штампа в имени, а при ошибке — время изменения."""
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
    """Логика резервного копирования сэйвов игры."""

    @staticmethod
    def backup_saves(config: GameConfig, now: datetime | None = None) -> Path:
        """Выполняет бэкап сэйвов по правилам МОДУЛЯ "Бэкап сэйвов".

        1. В папке игры создаётся новая папка "{Название игры} {дата и время}",
           в неё копируются сэйвы. Если сэйв — файл (режим Dark Souls), копируются
           оригинальный файл и все его бэкапы со штампом даты и времени.
        2. Все предыдущие папки бэкапов архивируются.
        3. Архивов хранится не больше MAX_ARCHIVES, лишние старые уходят в корзину.

        Возвращает путь к созданной папке бэкапа.
        """
        saves = Path(config.saves_path)
        if not saves.exists():
            raise FileNotFoundError(f"Путь к сэйвам не найден: {saves}")

        game_dir = Path(config.backup_path) / config.name
        game_dir.mkdir(parents=True, exist_ok=True)

        # Предыдущие папки бэкапов определяем до создания новой
        previous = BackupService._find_backup_folders(game_dir)

        stamp = (now or datetime.now()).strftime(STAMP_FORMAT)
        new_dir = game_dir / f"{config.name} {stamp}"
        new_dir.mkdir()
        try:
            if saves.is_dir():
                shutil.copytree(saves, new_dir, dirs_exist_ok=True)
            else:
                # Файл сэйва (режим Dark Souls): копируются оригинальный файл и все
                # созданные бэкапы со штампом даты и времени, чтобы можно было
                # откатить сэйв на более старое время
                BackupService._copy_dark_souls_files(saves, new_dir)

                # Копирование только текущего файла сэйва. Отключено; возможно,
                # будет использоваться для чекбокса "Копировать только текущий файл":
                # shutil.copy2(saves, new_dir)
        except Exception:
            # Недокопированный бэкап удаляем, предыдущие бэкапы не трогаем
            shutil.rmtree(new_dir, ignore_errors=True)
            raise

        for folder in previous:
            BackupService._archive_folder(folder)
        BackupService._trim_archives(game_dir)
        return new_dir

    @staticmethod
    def backup_single_file(source: Path, now: datetime | None = None) -> Path:
        """Делает бэкап одного файла сэйва для режима Dark Souls.

        Копия создаётся в той же папке со штампом даты и времени.
        Хранится не больше DARK_SOULS_MAX_BACKUPS копий: при превышении
        удаляется самая старая, новая копия становится самой свежей.
        """
        stamp = (now or datetime.now()).strftime(STAMP_FORMAT)
        existing = BackupService._find_dark_souls_backups(source)
        # После создания новой копии должно остаться не больше лимита
        excess = len(existing) - (DARK_SOULS_MAX_BACKUPS - 1)
        for old in existing[: max(excess, 0)]:
            old.unlink()

        target = source.with_name(f"{source.stem}_{stamp}{source.suffix}")
        shutil.copy2(source, target)
        return target

    @staticmethod
    def _dark_souls_backup_pattern(source: Path) -> re.Pattern:
        """Шаблон имени бэкапа файла сэйва: "{имя}_{штамп}{расширение}"."""
        return re.compile(
            rf"^{re.escape(source.stem)}_(?P<stamp>{STAMP_REGEX}){re.escape(source.suffix)}$"
        )

    @staticmethod
    def _find_dark_souls_backups(source: Path) -> list[Path]:
        """Ищет бэкапы файла сэйва в его папке (от старых к новым)."""
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
        """Копирует в папку бэкапа оригинальный файл сэйва и все его бэкапы со штампом.

        Файлы остаются и в папке сэйвов: оригинал нужен игре, а бэкапы со штампом
        участвуют в ротации режима Dark Souls.
        """
        for file in [source, *BackupService._find_dark_souls_backups(source)]:
            shutil.copy2(file, target_dir)

    @staticmethod
    def _find_backup_folders(game_dir: Path) -> list[Path]:
        """Ищет папки предыдущих бэкапов (от старых к новым)."""
        folders = [
            item
            for item in game_dir.iterdir()
            if item.is_dir() and _FOLDER_RE.match(item.name)
        ]
        return sorted(folders, key=lambda item: _stamp_of(item, _FOLDER_RE))

    @staticmethod
    def _archive_folder(folder: Path) -> None:
        """Архивирует папку бэкапа в zip и удаляет исходную папку."""
        shutil.make_archive(
            str(folder.parent / folder.name),
            "zip",
            root_dir=str(folder.parent),
            base_dir=folder.name,
        )
        shutil.rmtree(folder)

    @staticmethod
    def _trim_archives(game_dir: Path) -> None:
        """Оставляет не больше MAX_ARCHIVES архивов, самые старые отправляет в корзину."""
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
                # Бэкап уже сделан, поэтому сбой очистки не считаем ошибкой бэкапа
                logger.exception("Не удалось отправить архив в корзину: %s", old)
