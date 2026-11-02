"""Вспомогательные виджеты интерфейса."""
import html

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFontDatabase
from PySide6.QtWidgets import QHBoxLayout, QLabel, QListWidget, QPlainTextEdit, QWidget

from .. import constants as c


def make_tooltip(text: str) -> str:
    return "<html><body>" + html.escape(text).replace("\n", "<br>") + "</body></html>"


class InfoIcon(QLabel):
    def __init__(self, tooltip_text: str, parent: QWidget | None = None) -> None:
        super().__init__(c.INFO_ICON_TEXT, parent)
        self.setFixedSize(20, 20)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setToolTip(make_tooltip(tooltip_text))
        self.setCursor(Qt.CursorShape.WhatsThisCursor)
        self.setStyleSheet(
            "QLabel { border: 1px solid palette(mid); border-radius: 10px; font-weight: bold; }"
        )


class FieldHeader(QWidget):
    def __init__(self, title: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._has_error = False

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self._title = QLabel(title)
        self._error = QLabel()
        self._error.setStyleSheet("color: #d32f2f;")
        self._error.hide()

        layout.addWidget(self._title)
        layout.addWidget(self._error)
        layout.addStretch(1)

    def set_error(self, text: str | None) -> None:
        self._has_error = bool(text)
        self._error.setText(text or "")
        self._error.setVisible(self._has_error)

    def has_error(self) -> bool:
        return self._has_error


class ConfigListWidget(QListWidget):
    config_clicked = Signal(str)
    empty_clicked = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        self.itemClicked.connect(lambda item: self.config_clicked.emit(item.text()))

    def mousePressEvent(self, event) -> None:
        if self.itemAt(event.position().toPoint()) is None:
            self.clearSelection()
            self.setCurrentRow(-1)
            event.accept()
            self.empty_clicked.emit()
            return
        super().mousePressEvent(event)


class InfoLogWidget(QPlainTextEdit):

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setReadOnly(True)
        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.setFont(QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont))
        self._lines: list[str] = []

    def reset(self) -> None:
        self._lines.clear()
        self._render()

    def append_line(self, text: str) -> None:
        self._lines.append(text)
        self._render()

    def replace_last_line(self, text: str) -> None:
        if self._lines:
            self._lines[-1] = text
        else:
            self._lines.append(text)
        self._render()

    def lines(self) -> list[str]:
        return list(self._lines)

    def _render(self) -> None:
        self.setPlainText("\n".join(self._lines))
        scrollbar = self.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
        