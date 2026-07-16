from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QCheckBox, QPushButton, QTextEdit,
    QGroupBox, QScrollArea, QComboBox, QGridLayout
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont

import markdown

from services.generator import generate_checklist, FIELD_CONFIG
from templates.templates import DEFAULT_TEXT


class QACheatSheet(QMainWindow):

    def __init__(self):
        super().__init__()

        self.setWindowTitle("QA Cheat Sheet Generator (30.06.2026)")
        self.resize(1100, 750)

        self.init_ui()
        QTimer.singleShot(0, self.center_window)

    def center_window(self):
        screen = self.screen().geometry()
        window = self.frameGeometry()
        window.moveCenter(screen.center())
        self.move(window.topLeft())

    def render_markdown(self, text: str):
        html = markdown.markdown(
            text,
            extensions=['tables', 'fenced_code', 'nl2br', 'attr_list', 'def_list']
        )

        styled_html = f"""
        <style>
        body {{
            font-family: Calibri;
            font-size: 14px;
        }}
        h1, h2, h3 {{
            margin-top: 12px;
        }}
        ul {{
            margin-left: 15px;
        }}
        </style>
        {html}
        """

        self.result.setHtml(styled_html)

    def init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)

        # Левая панель
        left_panel = QScrollArea()
        left_panel.setMinimumWidth(280)
        left_panel.setMaximumWidth(420)
        left_panel.setWidgetResizable(True)

        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)

        # Выбор типа
        main_type_group = QGroupBox("Выбор элемента")
        main_type_layout = QHBoxLayout()

        self.main_type_combo = QComboBox()
        self.main_type_combo.addItems(["", "Кнопка", "Поле", "Форма"])
        self.main_type_combo.currentTextChanged.connect(self.update_subtypes_ui)
        self.main_type_combo.currentTextChanged.connect(self.on_generate)

        main_type_layout.addWidget(self.main_type_combo)
        main_type_group.setLayout(main_type_layout)
        left_layout.addWidget(main_type_group)

        # Подтипы
        self.subtypes_group = QGroupBox("Подтипы")
        self.subtypes_layout = QGridLayout()
        self.subtypes_group.setLayout(self.subtypes_layout)
        self.subtypes_group.setVisible(False)
        left_layout.addWidget(self.subtypes_group)

        # Кнопки
        self.btn_layout = QHBoxLayout()
        self.select_all_btn = QPushButton("Выбрать все")
        self.clear_all_btn = QPushButton("Снять выделение")

        self.select_all_btn.clicked.connect(self.select_all_fields)
        self.clear_all_btn.clicked.connect(self.clear_all_fields)

        self.btn_layout.addWidget(self.select_all_btn)
        self.btn_layout.addWidget(self.clear_all_btn)
        left_layout.addLayout(self.btn_layout)

        self.select_all_btn.setVisible(False)
        self.clear_all_btn.setVisible(False)

        left_layout.addStretch()
        left_panel.setWidget(left_widget)

        # Правая панель
        self.result = QTextEdit()
        self.result.setFont(QFont("Calibri", 12))
        self.result.setReadOnly(True)
        self.render_markdown(DEFAULT_TEXT)

        main_layout.addWidget(left_panel, 1)
        main_layout.addWidget(self.result, 3)

        self.update_subtypes_ui()

    def update_subtypes_ui(self):
        # очистка
        for i in reversed(range(self.subtypes_layout.count())):
            widget = self.subtypes_layout.itemAt(i).widget()
            if widget:
                widget.deleteLater()

        self.subtype_checkboxes = {}

        main_type = self.main_type_combo.currentText()

        self.subtypes_group.setVisible(False)
        self.select_all_btn.setVisible(False)
        self.clear_all_btn.setVisible(False)

        if main_type == "":
            self.render_markdown(DEFAULT_TEXT)
            return

        if main_type == "Поле":
            self.subtypes_group.setVisible(True)
            self.select_all_btn.setVisible(True)
            self.clear_all_btn.setVisible(True)

            subtypes = sorted(FIELD_CONFIG.keys())

            mid = (len(subtypes) + 1) // 2
            columns = [subtypes[:mid], subtypes[mid:]]

            for col, group in enumerate(columns):
                for row, subtype in enumerate(group):
                    cb = QCheckBox(subtype)
                    cb.stateChanged.connect(self.on_checkbox_change)
                    self.subtype_checkboxes[subtype] = cb
                    self.subtypes_layout.addWidget(cb, row, col)

        self.update_buttons_state()
        self.on_generate()

    def on_checkbox_change(self):
        self.update_buttons_state()
        self.on_generate()

    def update_buttons_state(self):
        if not self.subtype_checkboxes:
            self.select_all_btn.setEnabled(False)
            self.clear_all_btn.setEnabled(False)
            return

        all_checked = all(cb.isChecked() for cb in self.subtype_checkboxes.values())
        any_checked = any(cb.isChecked() for cb in self.subtype_checkboxes.values())

        self.select_all_btn.setEnabled(not all_checked)
        self.clear_all_btn.setEnabled(any_checked)

    def get_selected_fields(self):
        return [
            name for name, cb in self.subtype_checkboxes.items() if cb.isChecked()
        ]

    def on_generate(self):
        main_type = self.main_type_combo.currentText()

        if main_type == "":
            self.render_markdown(DEFAULT_TEXT)
            return

        selected_fields = []
        if main_type == "Поле":
            selected_fields = self.get_selected_fields()

        # 🔥 ВСЕГДА вызываем генератор
        text = generate_checklist(main_type, selected_fields)

        self.render_markdown(text)

    def select_all_fields(self):
        for cb in self.subtype_checkboxes.values():
            cb.setChecked(True)

    def clear_all_fields(self):
        for cb in self.subtype_checkboxes.values():
            cb.setChecked(False)