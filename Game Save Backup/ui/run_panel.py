# === Левая панель (лог запуска) ===
from PySide6.QtWidgets import *
from PySide6.QtCore import QThread, Signal, QEvent
from PySide6.QtGui import QTextCursor
from core.game_runner import GameRunner
from core.backup_manager import BackupManager

class Worker(QThread):
    log_signal = Signal(str)
    finished_signal = Signal()

    def __init__(self, config):
        super().__init__()
        self.config = config

    def run(self):
        runner = GameRunner(self.config, self.log_signal.emit)
        runner.run()
        self.log_signal.emit("Запустить Бэкап сэйвов")
        backup = BackupManager(self.config)
        backup.run()
        for i in range(10, 0, -1):
            self.log_signal.emit(f"Закрытие через {i} сек...")
            self.sleep(1)
        self.finished_signal.emit()

class RunPanel(QWidget):
    def __init__(self, manager, main_window):
        super().__init__()
        self.manager = manager
        self.main_window = main_window
        layout = QVBoxLayout(self)
        self.stack = QStackedWidget()
        self.list_widget = QListWidget()
        self.log_widget = QTextEdit()
        self.log_widget.setReadOnly(True)
        self.stack.addWidget(self.list_widget)
        self.stack.addWidget(self.log_widget)
        layout.addWidget(self.stack)
        self.run_btn = QPushButton("Запустить")
        layout.addWidget(self.run_btn)
        self.run_btn.clicked.connect(self.run_game)
        self.list_widget.itemClicked.connect(self.on_select)
        self.list_widget.viewport().installEventFilter(self)
        self.reload_list()

    def eventFilter(self, obj, event):
        if obj == self.list_widget.viewport():
            if event.type() == QEvent.MouseButtonPress:
                if not self.list_widget.itemAt(event.pos()):
                    self.main_window.config_panel.save(check_duplicate=False)
                    self.main_window.config_panel.clear_form()
                    self.list_widget.clearSelection()
        return super().eventFilter(obj, event)

    def reload_list(self):
        self.list_widget.clear()
        configs = self.manager.get_configs()
        for c in configs:
            self.list_widget.addItem(c["name"])
        if not configs:
            self.run_btn.setEnabled(False)
            return
        self.run_btn.setEnabled(True)
        if len(configs) == 1:
            self.list_widget.setCurrentRow(0)
        else:
            last = self.manager.get_last_used()
            if last:
                for i in range(self.list_widget.count()):
                    if self.list_widget.item(i).text() == last:
                        self.list_widget.setCurrentRow(i)
                        break

    def on_select(self, item):
        config = self.manager.get_by_name(item.text())
        if config:
            self.main_window.config_panel.load_config(config)

    def run_game(self):
        configs = self.manager.get_configs()
        if not configs:
            return
        selected = self.list_widget.currentItem()
        name = selected.text() if selected else (self.manager.get_last_used() or configs[0]["name"])
        config = self.manager.get_by_name(name)
        if not config:
            return
        self.manager.set_last_used(config["name"])
        self.stack.setCurrentWidget(self.log_widget)
        self.log_widget.clear()
        self.worker = Worker(config)
        self.worker.log_signal.connect(self.append_log)
        self.worker.finished_signal.connect(self.restore)
        self.worker.start()

    def append_log(self, text):
        # Одна строка для таймера
        if "Закрытие через" in text:
            cursor = self.log_widget.textCursor()
            cursor.movePosition(QTextCursor.End)
            cursor.movePosition(QTextCursor.StartOfLine, QTextCursor.KeepAnchor)
            if "Закрытие через" in cursor.selectedText():
                cursor.removeSelectedText()
            cursor.insertText(text)
            self.log_widget.setTextCursor(cursor)
            return
        self.log_widget.append(text)

    def restore(self):
        self.stack.setCurrentWidget(self.list_widget)
        self.reload_list()