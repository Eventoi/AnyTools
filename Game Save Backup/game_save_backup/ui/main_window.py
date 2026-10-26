"""Основное окно: слева список конфигураций, справа создание/редактирование."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QHBoxLayout, QMainWindow, QWidget

from .. import constants as c
from ..app_storage import AppSettings
from ..config_store import ConfigStore
from ..game_session import GameSession
from ..models import GameConfig
from .config_form_module import ConfigFormModule
from .config_list_module import ConfigListModule


class MainWindow(QMainWindow):
    """Основное окно приложения."""

    def __init__(self, settings: AppSettings) -> None:
        super().__init__()
        self.setWindowTitle(c.WINDOW_TITLE)
        self.resize(960, 600)
        self.setMinimumSize(820, 560)

        self._session: GameSession | None = None

        self._store = ConfigStore(settings, self)
        self._store.load_startup()

        self._list_module = ConfigListModule(self._store)
        self._form_module = ConfigFormModule(self._store, settings)

        central = QWidget()
        layout = QHBoxLayout(central)
        layout.addWidget(self._list_module, 1)
        layout.addWidget(self._form_module, 1)
        self.setCentralWidget(central)

        self._list_module.config_selected.connect(self._form_module.show_edit)
        self._list_module.create_requested.connect(self._form_module.show_create)
        self._form_module.config_created.connect(self._list_module.select_name)
        self._form_module.launch_requested.connect(self._start_session)

        # При возврате в окно подхватываем конфигурации, измененные вручную вне программы
        app = QApplication.instance()
        if app is not None:
            app.applicationStateChanged.connect(self._on_application_state_changed)

    def _on_application_state_changed(self, state: Qt.ApplicationState) -> None:
        """Синхронизирует конфигурации с диском, когда пользователь возвращается в приложение."""
        if state == Qt.ApplicationState.ApplicationActive:
            self._store.sync()

    # ------------------------------------------------------ Запуск игры
    def _start_session(self, config: GameConfig) -> None:
        """Запускает выбранную конфигурацию в фоновом потоке."""
        if self._session is not None:
            return

        session = GameSession(config, self)
        session.log_line.connect(self._list_module.append_log_line)
        session.log_replace_last.connect(self._list_module.replace_last_log_line)
        session.finished.connect(self._on_session_finished)
        self._session = session

        self._form_module.set_running({config.name})
        self._list_module.show_log()
        session.start()

    def _on_session_finished(self) -> None:
        """Игра закрыта и бэкап завершён: возвращаем список конфигураций."""
        session, self._session = self._session, None
        if session is not None:
            session.deleteLater()
        self._form_module.set_running(set())
        self._list_module.show_list()

    # --------------------------------------------------------- Закрытие
    def closeEvent(self, event) -> None:
        if self._session is not None:
            self._session.request_stop()
            self._session.wait(60_000)
        super().closeEvent(event)
