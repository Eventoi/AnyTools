"""МОДУЛЬ "Создание конфигурации" / "Редактирование конфигурации" (правая часть окна)."""
import logging
import os
from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .. import constants as c
from ..app_storage import AppSettings
from ..config_store import ConfigStore
from ..fs_utils import FolderNameValidator, sanitize_folder_name
from ..models import GameConfig
from .widgets import FieldHeader, InfoIcon

logger = logging.getLogger(__name__)


def _create_path_edit(placeholder: str) -> QLineEdit:
    """Заблокированное поле пути: значение задаётся только кнопкой троеточия."""
    edit = QLineEdit()
    edit.setPlaceholderText(placeholder)
    edit.setEnabled(False)
    return edit


def _create_browse_button() -> QPushButton:
    """Кнопка троеточия справа от поля ввода."""
    button = QPushButton(c.BUTTON_BROWSE_TEXT)
    button.setFixedWidth(36)
    return button


class ConfigFormModule(QGroupBox):
    """Форма создания и редактирования конфигурации.

    Пока конфигурация не создана, значения хранятся в форме. Конфигурация
    создаётся при расфокусировке поля «Название игры», после этого все
    изменения полей автоматически сохраняются в ней.
    """

    # Пользователь нажал «Запустить» (передаётся копия конфигурации)
    launch_requested = Signal(object)
    # Конфигурация создана и появилась в списке (передаётся название)
    config_created = Signal(str)

    def __init__(self, store: ConfigStore, settings: AppSettings, parent: QWidget | None = None) -> None:
        super().__init__(c.TITLE_CONFIG_CREATE, parent)
        self._store = store
        self._settings = settings
        # Название конфигурации, с которой связана форма (None — ещё не создана)
        self._bound_name: str | None = None
        # Идёт программное заполнение формы: сохранение не требуется
        self._loading = False
        # Названия запущенных игр (в нижнем регистре)
        self._running: set[str] = set()

        self._build_ui()
        self._connect_signals()
        self.show_create(rescan=False)

    # ----------------------------------------------------------- Интерфейс
    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(4)

        # Название игры
        self._name_header = FieldHeader(c.LABEL_GAME_NAME)
        self._name_edit = QLineEdit()
        self._name_edit.setPlaceholderText(c.PLACEHOLDER_GAME_NAME)
        self._name_edit.setValidator(FolderNameValidator(self._name_edit))
        self._name_edit.setMaxLength(c.MAX_GAME_NAME_LENGTH)
        layout.addWidget(self._name_header)
        layout.addWidget(self._name_edit)
        layout.addSpacing(8)

        # Запуск через игровой клиент
        self._client_check = QCheckBox(c.LABEL_USE_CLIENT)
        client_row = QHBoxLayout()
        client_row.addWidget(self._client_check)
        client_row.addWidget(InfoIcon(c.TOOLTIP_CLIENT_URL))
        client_row.addStretch(1)
        layout.addLayout(client_row)
        layout.addSpacing(4)

        # URL
        self._url_header = FieldHeader(c.LABEL_URL)
        self._url_edit = QLineEdit()
        self._url_edit.setPlaceholderText(c.PLACEHOLDER_URL)
        self._url_edit.setEnabled(False)
        layout.addWidget(self._url_header)
        layout.addWidget(self._url_edit)
        layout.addSpacing(8)

        # EXE-файл
        self._exe_header = FieldHeader(c.LABEL_EXE)
        self._exe_edit = _create_path_edit(c.PLACEHOLDER_EXE)
        self._exe_button = _create_browse_button()
        layout.addWidget(self._exe_header)
        layout.addLayout(self._path_row(self._exe_edit, self._exe_button))
        layout.addSpacing(8)

        # Сэйвы
        self._saves_header = FieldHeader(c.LABEL_SAVES)
        self._saves_edit = _create_path_edit(c.PLACEHOLDER_SAVES)
        self._saves_button = _create_browse_button()
        layout.addWidget(self._saves_header)
        layout.addLayout(self._path_row(self._saves_edit, self._saves_button))
        layout.addSpacing(8)

        # Бэкап сэйвов
        self._backup_header = FieldHeader(c.LABEL_BACKUP)
        self._backup_edit = _create_path_edit(c.PLACEHOLDER_BACKUP)
        self._backup_button = _create_browse_button()
        layout.addWidget(self._backup_header)
        layout.addLayout(self._path_row(self._backup_edit, self._backup_button))
        layout.addSpacing(8)

        # Режим Dark Souls
        self._ds_check = QCheckBox(c.LABEL_DARK_SOULS)
        ds_row = QHBoxLayout()
        ds_row.addWidget(self._ds_check)
        ds_row.addWidget(InfoIcon(c.TOOLTIP_DARK_SOULS))
        ds_row.addStretch(1)
        layout.addLayout(ds_row)

        layout.addStretch(1)

        # Запустить
        self._launch_button = QPushButton(c.LABEL_LAUNCH)
        self._launch_button.setMinimumHeight(36)
        layout.addWidget(self._launch_button)

    @staticmethod
    def _path_row(edit: QLineEdit, button: QPushButton) -> QHBoxLayout:
        """Строка: поле пути и кнопка троеточия справа от него."""
        row = QHBoxLayout()
        row.addWidget(edit, 1)
        row.addWidget(button)
        return row

    def _connect_signals(self) -> None:
        self._name_edit.textChanged.connect(self._on_name_text_changed)
        self._name_edit.editingFinished.connect(self._on_name_committed)
        self._client_check.toggled.connect(self._on_client_toggled)
        self._url_edit.textChanged.connect(self._apply_states)
        self._url_edit.editingFinished.connect(self._autosave)
        self._exe_button.clicked.connect(self._choose_exe)
        self._saves_button.clicked.connect(self._choose_saves)
        self._backup_button.clicked.connect(self._choose_backup)
        self._ds_check.toggled.connect(self._on_ds_toggled)
        self._launch_button.clicked.connect(self._on_launch_clicked)
        self._store.config_reloaded.connect(self._on_config_reloaded)
        self._store.config_removed.connect(self._on_config_removed)

    # ------------------------------------------------------ Режимы модуля
    def show_create(self, rescan: bool = True) -> None:
        """Переключает модуль в режим создания новой конфигурации."""
        last_path = self._settings.last_backup_path
        self._loading = True
        try:
            self._bound_name = None
            self._name_edit.clear()
            self._client_check.setChecked(False)
            self._url_edit.clear()
            self._set_path(self._exe_edit, "")
            self._set_path(self._saves_edit, "")
            # Последний указанный путь бэкапа подставляется всегда
            self._set_path(self._backup_edit, last_path)
            self._ds_check.setChecked(False)
            self._name_header.set_error(None)
            self._saves_header.set_error(None)
        finally:
            self._loading = False
        self.setTitle(c.TITLE_CONFIG_CREATE)

        # Одноразовое сканирование подставленной папки бэкапов
        if rescan and last_path:
            self._store.scan_root(last_path)
        self._apply_states()

    def show_edit(self, name: str) -> None:
        """Переключает модуль в режим редактирования созданной конфигурации."""
        config = self._store.get(name)
        if config is None:
            self.show_create()
            return
        self._fill_from_config(config)
        self.setTitle(c.TITLE_CONFIG_EDIT)

    def _fill_from_config(self, config: GameConfig) -> None:
        """Заполняет все поля формы из конфигурации (заголовок модуля не меняется)."""
        self._loading = True
        try:
            self._name_edit.setText(config.name)
            self._client_check.setChecked(config.use_client)
            self._url_edit.setText(config.url)
            self._set_path(self._exe_edit, config.exe_path)
            self._set_path(self._saves_edit, config.saves_path)
            self._set_path(self._backup_edit, config.backup_path)
            self._ds_check.setChecked(config.dark_souls_mode)
            self._name_header.set_error(None)
            self._saves_header.set_error(None)
            self._bound_name = config.name
        finally:
            self._loading = False
        self._refresh_saves_error()
        self._apply_states()

    def _on_config_reloaded(self, old_name: str, new_name: str) -> None:
        """Конфигурация отредактирована вручную вне программы: подхватываем изменения."""
        if self._bound_name is None or self._bound_name.casefold() != old_name.casefold():
            return
        config = self._store.get(new_name)
        if config is not None:
            self._fill_from_config(config)

    def _on_config_removed(self, name: str) -> None:
        """Конфигурация удалена с диска: форма возвращается к созданию новой."""
        if self._bound_name is not None and self._bound_name.casefold() == name.casefold():
            self.show_create(rescan=False)

    def set_running(self, names: set[str]) -> None:
        """Сообщает форме, какие игры запущены (их редактирование блокируется)."""
        self._running = {name.casefold() for name in names}
        self._apply_states()

    # ------------------------------------------------------------ Название
    def _on_name_text_changed(self) -> None:
        self._refresh_name_error()

    def _refresh_name_error(self) -> None:
        """Показывает ошибку, если введённое название уже есть в списке."""
        name = sanitize_folder_name(self._name_edit.text())
        exists = bool(name) and self._store.has(name, ignore=self._bound_name)
        self._set_field_error(self._name_header, c.ERROR_CONFIG_EXISTS if exists else None)

    def _on_name_committed(self) -> None:
        """Расфокусировка поля названия: создание конфигурации или переименование."""
        if self._loading or self._is_locked():
            return

        raw = self._name_edit.text()
        name = sanitize_folder_name(raw)

        if self._bound_name is None:
            if not name or self._store.has(name):
                self._refresh_name_error()
                return
            if raw != name:
                self._name_edit.setText(name)
            try:
                self._store.create(self._collect(name))
            except FileExistsError:
                self._set_field_error(self._name_header, c.ERROR_CONFIG_EXISTS)
                return
            except OSError:
                logger.exception("Не удалось создать конфигурацию")
                return
            self._bound_name = name
            self.config_created.emit(name)
        else:
            if not name:
                self._name_edit.setText(self._bound_name)
                return
            if name == self._bound_name:
                if raw != name:
                    self._name_edit.setText(name)
                return
            if self._store.has(name, ignore=self._bound_name):
                self._refresh_name_error()
                return
            try:
                self._store.save(self._bound_name, self._collect(name))
            except FileExistsError:
                self._set_field_error(self._name_header, c.ERROR_CONFIG_EXISTS)
                return
            except OSError:
                logger.exception("Не удалось переименовать конфигурацию")
                self._name_edit.setText(self._bound_name)
                return
            if raw != name:
                self._name_edit.setText(name)
            self._bound_name = name
        self._apply_states()

    # ------------------------------------------------------ Остальные поля
    def _on_client_toggled(self, _checked: bool) -> None:
        self._apply_states()
        self._autosave()

    def _on_ds_toggled(self, _checked: bool) -> None:
        self._refresh_saves_error()
        self._autosave()

    def _refresh_saves_error(self) -> None:
        """Проверяет, соответствует ли выбранный в поле «Сэйвы» путь режиму Dark Souls.

        - Режим включен, а выбрана папка: «Выберите файл сохранения».
        - Режим выключен, а выбран файл: «Выберите папку сохранений».
        Ошибка исчезает, когда режим и тип пути снова совпадают: переключением
        чекбокса обратно или выбором файла (папки) в поле «Сэйвы».
        """
        path = self._saves_edit.text()
        error: str | None = None
        if path:
            if self._ds_check.isChecked() and os.path.isdir(path):
                error = c.ERROR_SELECT_SAVE_FILE
            elif not self._ds_check.isChecked() and os.path.isfile(path):
                error = c.ERROR_SELECT_SAVES_FOLDER
        self._set_field_error(self._saves_header, error)

    def _choose_exe(self) -> None:
        """Кнопка троеточия: добавление exe-файла."""
        path, _ = QFileDialog.getOpenFileName(
            self,
            c.DIALOG_SELECT_EXE,
            self._start_dir(self._exe_edit.text()),
            c.DIALOG_FILTER_EXE,
        )
        if path:
            self._set_path(self._exe_edit, path)
            self._after_path_changed()

    def _choose_saves(self) -> None:
        """Кнопка троеточия поля «Сэйвы»: файл при включенном режиме Dark Souls, иначе папка."""
        start = self._start_dir(self._saves_edit.text())
        if self._ds_check.isChecked():
            path, _ = QFileDialog.getOpenFileName(self, c.DIALOG_SELECT_FILE, start)
        else:
            path = QFileDialog.getExistingDirectory(self, c.DIALOG_SELECT_FOLDER, start)
        if path:
            self._set_path(self._saves_edit, path)
            self._refresh_saves_error()
            self._after_path_changed()

    def _choose_backup(self) -> None:
        """Кнопка троеточия поля «Бэкап сэйвов»: добавление папки."""
        path = QFileDialog.getExistingDirectory(
            self, c.DIALOG_SELECT_FOLDER, self._start_dir(self._backup_edit.text())
        )
        if not path:
            return
        path = os.path.normpath(path)
        self._settings.set_last_backup_path(path)
        # Одноразовое сканирование: импорт найденных json-конфигураций
        self._store.scan_root(path)
        self._set_path(self._backup_edit, path)
        self._after_path_changed()

    def _after_path_changed(self) -> None:
        self._autosave()
        self._apply_states()

    # --------------------------------------------------------- Сохранение
    def _collect(self, name: str) -> GameConfig:
        """Собирает конфигурацию из значений формы."""
        return GameConfig(
            name=name,
            use_client=self._client_check.isChecked(),
            url=self._url_edit.text().strip(),
            exe_path=self._exe_edit.text(),
            saves_path=self._saves_edit.text(),
            backup_path=self._backup_edit.text(),
            dark_souls_mode=self._ds_check.isChecked(),
        )

    def _autosave(self) -> None:
        """Автоматически сохраняет изменения в созданной конфигурации."""
        if self._loading or self._bound_name is None or self._is_locked():
            return
        if not self._store.has(self._bound_name):
            # Конфигурация была удалена с диска
            self._bound_name = None
            return
        try:
            self._store.save(self._bound_name, self._collect(self._bound_name))
        except OSError:
            logger.exception("Не удалось сохранить конфигурацию")

    # ------------------------------------------------------------- Запуск
    def _has_field_errors(self) -> bool:
        """Выдало ли любое из полей ввода ошибку."""
        headers = (
            self._name_header,
            self._url_header,
            self._exe_header,
            self._saves_header,
            self._backup_header,
        )
        return any(header.has_error() for header in headers)

    def _can_launch(self) -> bool:
        """Можно ли запускать: нет ошибок в полях и заполнены все обязательные поля."""
        if self._has_field_errors():
            return False
        if not sanitize_folder_name(self._name_edit.text()):
            return False
        if not (self._exe_edit.text() and self._saves_edit.text() and self._backup_edit.text()):
            return False
        if self._client_check.isChecked() and not self._url_edit.text().strip():
            return False
        return True

    def _on_launch_clicked(self) -> None:
        # Фиксируем несохранённые изменения полей перед запуском
        self._on_name_committed()
        if self._bound_name is None or not self._can_launch():
            return
        self._autosave()
        self.launch_requested.emit(self._collect(self._bound_name))

    # ------------------------------------------------------------ Состояние
    def _is_locked(self) -> bool:
        """Запущена ли игра, конфигурацию которой сейчас показывает форма."""
        return self._bound_name is not None and self._bound_name.casefold() in self._running

    def _apply_states(self, *_args) -> None:
        """Обновляет доступность элементов формы."""
        locked = self._is_locked()
        self._name_edit.setEnabled(not locked)
        self._client_check.setEnabled(not locked)
        self._url_edit.setEnabled(self._client_check.isChecked() and not locked)
        self._exe_button.setEnabled(not locked)
        self._saves_button.setEnabled(not locked)
        self._backup_button.setEnabled(not locked)
        self._ds_check.setEnabled(not locked)
        self._launch_button.setEnabled(self._can_launch() and not locked)

    # ----------------------------------------------------------- Помощники
    def _set_field_error(self, header: FieldHeader, text: str | None) -> None:
        """Показывает или скрывает ошибку поля и обновляет доступность кнопки «Запустить»."""
        header.set_error(text)
        self._apply_states()

    @staticmethod
    def _set_path(edit: QLineEdit, path: str) -> None:
        """Записывает путь в поле и показывает полный путь во всплывающей подсказке."""
        native = os.path.normpath(path) if path else ""
        edit.setText(native)
        edit.setToolTip(native)

    @staticmethod
    def _start_dir(current: str) -> str:
        """Папка, с которой открывается проводник."""
        if current:
            path = Path(current)
            folder = path if path.is_dir() else path.parent
            if folder.exists():
                return str(folder)
        return str(Path.home())
