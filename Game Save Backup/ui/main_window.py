# === Главное окно ===
from PySide6.QtWidgets import *
from PySide6.QtCore import QEvent
from core.config_manager import ConfigManager
from ui.config_panel import ConfigPanel
from ui.run_panel import RunPanel

class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.manager = ConfigManager()
        self.setWindowTitle("Game Save Backup (2026-04-15)")
        layout = QHBoxLayout(self)
        self.run_panel = RunPanel(self.manager, self)
        self.config_panel = ConfigPanel(self)
        layout.addWidget(self.run_panel)
        layout.addWidget(self.config_panel)