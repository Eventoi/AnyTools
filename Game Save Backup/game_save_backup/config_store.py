"""Хранилище конфигураций: загрузка, сохранение, импорт и синхронизация с диском.

Конфигурация хранится в json-файле "{Бэкап сэйвов}/{Название игры}/{Название игры}.json".
Пока путь бэкапа не указан, конфигурация лежит в папке черновиков приложения
и переносится в папку бэкапов сразу после выбора пути.

Конфигурации, созданные или изменённые вручную вне программы, подхватываются
при сканировании папок бэкапов (см. ConfigStore.scan_root и ConfigStore.sync).
"""
import json
import logging
import os
import re
import uuid
from dataclasses import dataclass, field, replace
from pathlib import Path

from PySide6.QtCore import QObject, Signal

from .app_storage import AppSettings
from .constants import MAX_GAME_NAME_LENGTH, STAMP_REGEX
from .fs_utils import forbidden_chars, sanitize_folder_name
from .models import GameConfig

logger = logging.getLogger(__name__)

# Остаток имени бэкапа после "{Название игры} ": штамп (и .zip для архивов)
_STAMPED_TAIL_RE = re.compile(rf"^{STAMP_REGEX}(\.zip)?$", re.IGNORECASE)

# Максимальная длина названия последней папки пути в имени при импорте
_MAX_ROOT_LABEL_LENGTH = 40


@dataclass
class _Entry:
    """Конфигурация, путь к её json-файлу и состояние файла на момент последнего чтения."""

    config: GameConfig
    file: Path
    stamp: tuple[int, int] | None = None


@dataclass
class _ScanEvents:
    """Что изменилось при сканировании (сигналы отправляются после его завершения)."""

    changed: bool = False
    renamed: list[tuple[str, str]] = field(default_factory=list)
    reloaded: list[tuple[str, str]] = field(default_factory=list)
    removed: list[str] = field(default_factory=list)


def _key(name: str) -> str:
    """Ключ названия для сравнения (имена папок не зависят от регистра)."""
    return name.casefold()


def _norm(path: str | Path) -> str:
    """Нормализует путь для сравнения."""
    return os.path.normcase(os.path.normpath(str(path)))


def _stamp(file: Path) -> tuple[int, int] | None:
    """Время изменения и размер файла (для обнаружения ручных правок)."""
    try:
        info = file.stat()
    except OSError:
        return None
    return info.st_mtime_ns, info.st_size


def _is_same_path(first: str | Path, second: str | Path) -> bool:
    """Проверяет, указывают ли два пути на один и тот же объект."""
    try:
        if Path(first).exists() and Path(second).exists():
            return os.path.samefile(first, second)
    except OSError:
        pass
    return _norm(first) == _norm(second)


def _rename_path(source: Path, target: Path) -> None:
    """Переименовывает файл или папку, включая смену только регистра букв."""
    if (
        source.parent == target.parent
        and source.name != target.name
        and source.name.casefold() == target.name.casefold()
    ):
        temp = source.with_name(f"{source.name}.{uuid.uuid4().hex}.tmp")
        source.rename(temp)
        temp.rename(target)
    else:
        source.rename(target)


def _rename_stamped_items(folder: Path, old_names: list[str], new_name: str) -> None:
    """Переименовывает папки и архивы бэкапов внутри папки игры под новое название."""
    try:
        items = list(folder.iterdir())
    except OSError:
        return
    for item in items:
        for old_name in old_names:
            if not old_name or old_name == new_name:
                continue
            prefix = f"{old_name} "
            tail = item.name[len(prefix):]
            if item.name.startswith(prefix) and _STAMPED_TAIL_RE.match(tail):
                try:
                    item.rename(item.with_name(f"{new_name} {tail}"))
                except OSError:
                    logger.exception("Не удалось переименовать: %s", item)
                break


def _clean_name(raw: str) -> str:
    """Приводит название к допустимому имени папки не длиннее лимита (пусто — нельзя)."""
    name = sanitize_folder_name(raw)
    if len(name) > MAX_GAME_NAME_LENGTH:
        name = sanitize_folder_name(name[:MAX_GAME_NAME_LENGTH])
    return name


def _fit_name(stem: str, suffix: str) -> str:
    """Склеивает название и суффикс, не превышая лимит длины (суффикс сохраняется)."""
    suffix = suffix[: MAX_GAME_NAME_LENGTH - 1]
    return stem[: MAX_GAME_NAME_LENGTH - len(suffix)].rstrip() + suffix


def _root_label(root: Path) -> str:
    """Название последней папки пути (для переименования при импорте)."""
    label = root.name or root.drive.rstrip(":\\/") or "root"
    forbidden = forbidden_chars()
    label = "".join("_" if ch in forbidden else ch for ch in label)
    return label[:_MAX_ROOT_LABEL_LENGTH]


def _read_config(file: Path) -> GameConfig | None:
    """Читает json-конфигурацию; возвращает None, если файл не подходит."""
    try:
        data = json.loads(file.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return GameConfig.from_dict(data)


def _find_config_in(folder: Path) -> tuple[Path, GameConfig] | None:
    """Ищет в папке игры подходящую json-конфигурацию."""
    preferred = folder / f"{folder.name}.json"
    candidates = [preferred] if preferred.is_file() else []
    try:
        others = sorted(
            item for item in folder.glob("*.json") if item.is_file() and item != preferred
        )
    except OSError:
        others = []
    for file in candidates + others:
        config = _read_config(file)
        if config is not None:
            return file, config
    return None


class ConfigStore(QObject):
    """Список конфигураций в памяти, синхронизированный с json-файлами."""

    # Список конфигураций изменился
    changed = Signal()
    # Название конфигурации изменилось (старое, новое); отправляется до changed
    config_renamed = Signal(str, str)
    # Конфигурация изменена вручную вне программы и перечитана (старое, новое название)
    config_reloaded = Signal(str, str)
    # Конфигурация удалена с диска и убрана из списка (название)
    config_removed = Signal(str)

    def __init__(self, settings: AppSettings, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._settings = settings
        self._items: dict[str, _Entry] = {}

    # ------------------------------------------------------------ Запросы
    def names(self) -> list[str]:
        """Названия всех конфигураций (без сортировки)."""
        return [entry.config.name for entry in self._items.values()]

    def has(self, name: str, ignore: str | None = None) -> bool:
        """Есть ли конфигурация с таким названием (кроме ignore)."""
        key = _key(name)
        if ignore is not None and key == _key(ignore):
            return False
        return key in self._items

    def get(self, name: str) -> GameConfig | None:
        """Возвращает копию конфигурации по названию."""
        entry = self._items.get(_key(name))
        return replace(entry.config) if entry else None

    # ------------------------------------------------------------ Загрузка
    def load_startup(self) -> None:
        """Загружает черновики и выполняет сканирование известных папок бэкапов."""
        for file in sorted(self._settings.drafts_dir.glob("*.json")):
            config = _read_config(file)
            if config is not None and not self.has(config.name):
                config.backup_path = ""
                self._items[_key(config.name)] = _Entry(config, file, _stamp(file))

        events = _ScanEvents()
        for root in self._all_roots():
            self._scan(root, events)
        self.changed.emit()

    def scan_root(self, root: str) -> None:
        """Сканирует папку бэкапов: импорт новых, обновление изменённых, удаление пропавших."""
        events = _ScanEvents()
        self._scan(root, events)
        self._emit(events)

    def sync(self) -> None:
        """Сканирует все известные папки бэкапов (подхват ручных правок вне программы)."""
        events = _ScanEvents()
        for root in self._all_roots():
            self._scan(root, events)
        self._emit(events)

    # ---------------------------------------------------- Создание и запись
    def create(self, config: GameConfig) -> None:
        """Создаёт новую конфигурацию и сохраняет её json-файл."""
        key = _key(config.name)
        if key in self._items:
            raise FileExistsError(config.name)
        file = self._target_file(config)
        if file.exists():
            raise FileExistsError(str(file))
        self._write(file, config)
        self._items[key] = _Entry(replace(config), file, _stamp(file))
        self._settings.add_known_root(config.backup_path)
        self.changed.emit()

    def save(self, original_name: str, config: GameConfig) -> None:
        """Сохраняет изменения конфигурации.

        При смене названия переименовываются конфигурация, json-файл и папка
        хранения сэйвов, при смене пути бэкапа конфигурация переносится в новую папку.
        """
        old_key = _key(original_name)
        entry = self._items.get(old_key)
        if entry is None:
            raise KeyError(original_name)
        new_key = _key(config.name)
        if new_key != old_key and new_key in self._items:
            raise FileExistsError(config.name)

        old_config, old_file = entry.config, entry.file
        new_file = self._target_file(config)
        leftover: Path | None = None
        if str(new_file) != str(old_file):
            if new_file.exists() and not _is_same_path(new_file, old_file):
                raise FileExistsError(str(new_file))
            leftover = self._relocate(old_config, old_file, config, new_file)

        self._write(new_file, config)
        if leftover is not None:
            self._remove_old_file(leftover)

        del self._items[old_key]
        self._items[new_key] = _Entry(replace(config), new_file, _stamp(new_file))
        self._settings.add_known_root(config.backup_path)
        if config.name != old_config.name:
            self.config_renamed.emit(old_config.name, config.name)
            self.changed.emit()

    # ---------------------------------------------------------- Служебное
    def _all_roots(self) -> list[str]:
        """Все известные папки бэкапов, включая последнюю указанную."""
        roots = self._settings.known_roots
        last = self._settings.last_backup_path
        if last and all(_norm(last) != _norm(root) for root in roots):
            roots.append(last)
        return roots

    def _emit(self, events: _ScanEvents) -> None:
        """Отправляет сигналы об изменениях, найденных при сканировании."""
        for old_name, new_name in events.renamed:
            self.config_renamed.emit(old_name, new_name)
        if events.changed:
            self.changed.emit()
        for old_name, new_name in events.reloaded:
            self.config_reloaded.emit(old_name, new_name)
        for name in events.removed:
            self.config_removed.emit(name)

    def _target_file(self, config: GameConfig) -> Path:
        """Путь json-файла конфигурации."""
        if config.backup_path:
            return Path(config.backup_path) / config.name / f"{config.name}.json"
        return self._settings.drafts_dir / f"{config.name}.json"

    @staticmethod
    def _write(file: Path, config: GameConfig) -> None:
        """Атомарно записывает json-файл конфигурации."""
        file.parent.mkdir(parents=True, exist_ok=True)
        temp = file.with_name(file.name + ".tmp")
        temp.write_text(
            json.dumps(config.to_dict(), ensure_ascii=False, indent=4), encoding="utf-8"
        )
        os.replace(temp, file)

    def _relocate(
        self, old: GameConfig, old_file: Path, new: GameConfig, new_file: Path
    ) -> Path | None:
        """Готовит новое место хранения конфигурации.

        Возвращает старый json-файл, который нужно удалить после записи нового.
        """
        same_root = (
            bool(old.backup_path)
            and bool(new.backup_path)
            and _norm(old.backup_path) == _norm(new.backup_path)
        )
        old_dir, new_dir = old_file.parent, new_file.parent
        if same_root and old_dir.exists():
            # Смена названия игры: переименовываем папку, json и бэкапы внутри
            if old_dir.name != new_dir.name:
                if new_dir.exists() and not _is_same_path(new_dir, old_dir):
                    raise FileExistsError(str(new_dir))
                _rename_path(old_dir, new_dir)
            renamed_json = new_dir / old_file.name
            if renamed_json.exists() and renamed_json.name != new_file.name:
                _rename_path(renamed_json, new_file)
            _rename_stamped_items(new_dir, [old.name], new.name)
            return None

        new_dir.mkdir(parents=True, exist_ok=True)
        return old_file

    def _remove_old_file(self, file: Path) -> None:
        """Удаляет старый json-файл и опустевшую папку конфигурации."""
        try:
            file.unlink(missing_ok=True)
            parent = file.parent
            if (
                parent != self._settings.drafts_dir
                and parent.is_dir()
                and not any(parent.iterdir())
            ):
                parent.rmdir()
        except OSError:
            logger.exception("Не удалось удалить старый файл конфигурации: %s", file)

    # ------------------------------------------------------- Сканирование
    def _scan(self, root: str, events: _ScanEvents) -> None:
        """Приводит список конфигураций папки бэкапов в соответствие с диском."""
        root_path = Path(root)
        root_norm = _norm(root)

        def in_root(entry: _Entry) -> bool:
            return bool(entry.config.backup_path) and _norm(entry.config.backup_path) == root_norm

        # 1. Конфигурации, чьи json-файлы были удалены, убираем из списка
        for key, entry in list(self._items.items()):
            if in_root(entry) and not entry.file.exists():
                del self._items[key]
                events.removed.append(entry.config.name)
                events.changed = True

        # 2. Конфигурации, отредактированные вручную, перечитываем
        for key, entry in list(self._items.items()):
            if in_root(entry) and _stamp(entry.file) != entry.stamp:
                self._reload(root_path, key, entry, events)

        # 3. Новые конфигурации: в папках игр и просто в корне папки бэкапов
        if not root_path.is_dir():
            return
        try:
            children = sorted(root_path.iterdir())
        except OSError:
            return
        known_files = {_norm(entry.file) for entry in self._items.values()}
        for child in children:
            found: tuple[Path, GameConfig] | None = None
            if child.is_dir():
                found = _find_config_in(child)
            elif child.is_file() and child.suffix.lower() == ".json":
                config = _read_config(child)
                found = (child, config) if config is not None else None
            if found is None:
                continue
            file, config = found
            if _norm(file) in known_files:
                continue
            entry = self._import(root_path, file, config)
            if entry is not None:
                known_files.add(_norm(entry.file))
                events.changed = True

    def _import(self, root: Path, file: Path, config: GameConfig) -> _Entry | None:
        """Импортирует найденную конфигурацию в список."""
        # Путь бэкапа всегда равен папке, из которой выполнен импорт
        config.backup_path = str(root)
        target = self._adopt(root, file, config, current_key=None)
        if target is None:
            return None
        entry = _Entry(config, target, _stamp(target))
        self._items[_key(config.name)] = entry
        # Папка с импортированными конфигурациями запоминается для следующих синхронизаций
        self._settings.add_known_root(str(root))
        return entry

    def _reload(self, root: Path, key: str, entry: _Entry, events: _ScanEvents) -> None:
        """Перечитывает изменённый вручную json-файл и обновляет конфигурацию."""
        config = _read_config(entry.file)
        if config is None:
            # Файл временно некорректен (например, правка не закончена): оставляем прежнюю
            return
        old_name = entry.config.name
        config.backup_path = entry.config.backup_path

        if config == entry.config:
            entry.stamp = _stamp(entry.file)
            return

        target = self._adopt(root, entry.file, config, current_key=key)
        if target is None:
            return
        del self._items[key]
        self._items[_key(config.name)] = _Entry(config, target, _stamp(target))
        events.changed = True
        events.reloaded.append((old_name, config.name))
        if config.name != old_name:
            events.renamed.append((old_name, config.name))

    def _adopt(
        self, root: Path, file: Path, config: GameConfig, current_key: str | None
    ) -> Path | None:
        """Приводит расположение конфигурации к виду "{root}/{название}/{название}.json".

        - Конфигурация лежит в корне папки бэкапов: создаётся папка с именем
          конфигурации (если её нет) и json перемещается в неё.
        - Конфигурация лежит в папке с другим именем: папка и json переименовываются.
        - Название занято другой конфигурацией: к названию добавляется
          "(Название последней папки пути)".

        Обновляет config.name и возвращает путь к json-файлу (None — не удалось).
        """
        original_name = config.name
        name = _clean_name(original_name)
        if not name:
            return None

        in_root = _norm(file.parent) == _norm(root)
        target_dir = root / name
        target_file = target_dir / f"{name}.json"

        taken = _key(name) in self._items and _key(name) != current_key
        if not taken and in_root and target_file.exists():
            taken = True
        if taken:
            name = self._unique_name(root, name)
            target_dir = root / name
            target_file = target_dir / f"{name}.json"

        try:
            if in_root:
                target_dir.mkdir(parents=True, exist_ok=True)
                os.replace(file, target_file)
            else:
                folder = file.parent
                if folder.name != name:
                    if target_dir.exists() and not _is_same_path(target_dir, folder):
                        return None
                    _rename_path(folder, target_dir)
                    _rename_stamped_items(target_dir, [original_name, folder.name], name)
                current_file = target_dir / file.name
                if current_file.exists() and current_file.name != target_file.name:
                    _rename_path(current_file, target_file)
            if name != original_name:
                config.name = name
                self._write(target_file, config)
        except OSError:
            logger.exception("Не удалось привести расположение конфигурации в порядок: %s", file)
            return None

        config.name = name
        return target_file

    def _unique_name(self, root: Path, stem: str) -> str:
        """Название вида "Название (Последняя папка пути)", не занятое ни в списке, ни на диске."""
        label = _root_label(root)
        counter = 1
        while True:
            suffix = f" ({label})" if counter == 1 else f" ({label}) {counter}"
            candidate = _fit_name(stem, suffix)
            if _key(candidate) not in self._items and not (root / candidate).exists():
                return candidate
            counter += 1
