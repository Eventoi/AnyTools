import sys
from PySide6.QtWidgets import QApplication
from ui.main_window import QACheatSheet

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    window = QACheatSheet()
    window.show()

    sys.exit(app.exec())