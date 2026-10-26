"""МОДУЛЬ "Список конфигураций" (левая часть окна)."""
from functools import cmp_to_key

from PySide6.QtCore import QCollator, QLocale, Qt, Signal
from PySide6.QtWidgets import QGroupBox, QStackedWidget, QVBoxLayout, QWidget

from .. import constants as c
from ..config_store import ConfigStore
from .widgets import ConfigListWidget, InfoLogWidget


class ConfigListModule(QGroupBox):
    """Список конфигураций в алфавитном порядке.

    Во время запуска игры вместо списка показывается окно информации.
    """

    # Пользователь кликнул по созданной конфигурации
    config_selected = Signal(str)
    # Пользователь кликнул по пустому месту списка
    create_requested = Signal()

    def __init__(self, store: ConfigStore, parent: QWidget | None = None) -> None:
        super().__init__(c.TITLE_CONFIG_LIST, parent)
        self._store = store
        # Название выделенной конфигурации (сохраняется при обновлении списка)
        self._current_name: str | None = None

        self._collator = QCollator(QLocale(QLocale.Language.Russian))
        self._collator.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)

        self._list = ConfigListWidget()
        self._log = InfoLogWidget()
        self._stack = QStackedWidget()
        self._stack.addWidget(self._list)
        self._stack.addWidget(self._log)

        layout = QVBoxLayout(self)
        layout.addWidget(self._stack)

        self._list.config_clicked.connect(self._on_config_clicked)
        self._list.empty_clicked.connect(self._on_empty_clicked)
        self._store.config_renamed.connect(self._on_config_renamed)
        self._store.changed.connect(self.refresh)
        self.refresh()

    # ------------------------------------------------------------- Список
    def _on_config_clicked(self, name: str) -> None:
        self._current_name = name
        self.config_selected.emit(name)

    def _on_empty_clicked(self) -> None:
        self._current_name = None
        self.create_requested.emit()

    def _on_config_renamed(self, old_name: str, new_name: str) -> None:
        """Выделенная конфигурация переименована: выделение переходит на новое название."""
        if self._current_name and self._current_name.casefold() == old_name.casefold():
            self._current_name = new_name

    def refresh(self) -> None:
        """Перестраивает список в алфавитном порядке, сохраняя выделение."""
        names = sorted(self._store.names(), key=cmp_to_key(self._collator.compare))
        self._list.clear()
        self._list.addItems(names)
        if self._current_name is not None:
            if self._current_name in names:
                self._highlight(self._current_name)
            else:
                self._current_name = None

    def selected_name(self) -> str | None:
        """Название выделенной конфигурации."""
        items = self._list.selectedItems()
        return items[0].text() if items else None

    def select_name(self, name: str) -> None:
        """Выделяет конфигурацию без открытия модуля редактирования."""
        self._current_name = name
        self._highlight(name)

    def _highlight(self, name: str) -> None:
        """Подсвечивает конфигурацию в списке."""
        self._list.blockSignals(True)
        try:
            self._list.clearSelection()
            for row in range(self._list.count()):
                item = self._list.item(row)
                if item.text() == name:
                    self._list.setCurrentItem(item)
                    item.setSelected(True)
                    break
        finally:
            self._list.blockSignals(False)

    # ------------------------------------------------- Окно информации
    def show_log(self) -> None:
        """Показывает окно информации вместо списка конфигураций."""
        self._log.reset()
        self._stack.setCurrentWidget(self._log)

    def show_list(self) -> None:
        """Возвращает список конфигураций."""
        self._stack.setCurrentWidget(self._list)

    def append_log_line(self, text: str) -> None:
        self._log.append_line(text)

    def replace_last_log_line(self, text: str) -> None:
        self._log.replace_last_line(text)

    def is_log_shown(self) -> bool:
        return self._stack.currentWidget() is self._log
