# === Правая панель (создание/редактирование) ===
from PySide6.QtWidgets import *
from PySide6.QtCore import Qt
from core.config_manager import ConfigManager

class ConfigPanel(QWidget):
    def __init__(self, parent):
        super().__init__()
        self.parent = parent
        self.manager = ConfigManager()
        self.edit_mode = False
        self.original_name = ""
        self.setFixedWidth(340)
        layout = QVBoxLayout(self)
        # Название игры
        layout.addWidget(QLabel("Название игры"))
        self.name = QLineEdit()
        self.name.setPlaceholderText("Введите название игры")
        layout.addWidget(self.name)
        self.name_error = QLabel("")
        self.name_error.setStyleSheet("color: red;")
        layout.addWidget(self.name_error)
        # Чекбокс + ?
        row = QHBoxLayout()
        self.client_checkbox = QCheckBox("Запуск через игровой клиент (Steam/GOG и т.д.)")
        self.info = QLabel("?")
        self.info.setFixedWidth(20)
        self.info.setAlignment(Qt.AlignCenter)
        self.info.setToolTip(
            "Как получить URL?\n"
            "1. Создать ярлык игры на рабочем столе через игровой клиент\n"
            "2. Открыть Свойства этого ярлыка\n"
            "3. На вкладке Веб-документ скопировать URL-адрес"
        )
        self.info.setStyleSheet("""
            QLabel {
                border: 1px solid gray;
                border-radius: 10px;
                font-weight: bold;
                background-color: #f0f0f0;
            }
            QLabel:hover {
                background-color: #d0d0d0;
            }
        """)
        row.addWidget(self.client_checkbox)
        row.addWidget(self.info)
        layout.addLayout(row)
        # URL
        layout.addWidget(QLabel("URL"))
        self.url = QLineEdit()
        self.url.setPlaceholderText("Введите URL игры")
        self.url.setDisabled(True)
        layout.addWidget(self.url)
        self.url_error = QLabel("")
        self.url_error.setStyleSheet("color: red;")
        layout.addWidget(self.url_error)
        # EXE-файл + кнопка
        layout.addWidget(QLabel("EXE-файл"))
        self.exe = QLineEdit()
        self.exe.setPlaceholderText("Введите путь к exe-файлу игры")
        layout.addWidget(self.exe)
        self.exe_error = QLabel("")
        self.exe_error.setStyleSheet("color: red;")
        layout.addWidget(self.exe_error)
        self.choose_exe_btn = QPushButton("Выбрать exe-файл игры")
        layout.addWidget(self.choose_exe_btn)
        self.choose_exe_btn.clicked.connect(self.choose_exe)
        # Сэйвы + кнопка
        layout.addWidget(QLabel("Сэйвы игры"))
        self.saves = QLineEdit()
        self.saves.setPlaceholderText("Введите путь к сэйвам игры (откуда)")
        layout.addWidget(self.saves)
        self.saves_error = QLabel("")
        self.saves_error.setStyleSheet("color: red;")
        layout.addWidget(self.saves_error)
        self.choose_saves_btn = QPushButton("Выбрать папку с сэйвами игры")
        layout.addWidget(self.choose_saves_btn)
        self.choose_saves_btn.clicked.connect(self.choose_saves)
        # Бэкап + кнопка
        layout.addWidget(QLabel("Бэкап сэйвов"))
        self.backup = QLineEdit()
        self.backup.setPlaceholderText("Введите путь бэкапа сэйвов игры (куда)")
        layout.addWidget(self.backup)
        self.backup_error = QLabel("")
        self.backup_error.setStyleSheet("color: red;")
        layout.addWidget(self.backup_error)
        self.choose_backup_btn = QPushButton("Выбрать куда сохранить сэйвы")
        layout.addWidget(self.choose_backup_btn)
        self.choose_backup_btn.clicked.connect(self.choose_backup)
        # Кнопка Сохранить
        self.save_btn = QPushButton("Сохранить")
        layout.addWidget(self.save_btn)
        self.client_checkbox.stateChanged.connect(self.toggle_url)
        self.save_btn.clicked.connect(self.save)

    def choose_exe(self):
        file, _ = QFileDialog.getOpenFileName(self, "Выбрать exe-файл игры", "", "Executable files (*.exe);;All files (*)")
        if file:
            self.exe.setText(file)

    def choose_saves(self):
        dir_path = QFileDialog.getExistingDirectory(self, "Выбрать папку с сэйвами игры", "")
        if dir_path:
            self.saves.setText(dir_path)

    def choose_backup(self):
        dir_path = QFileDialog.getExistingDirectory(self, "Выбрать куда сохранить сэйвы", "")
        if dir_path:
            self.backup.setText(dir_path)

    def toggle_url(self):
        checked = self.client_checkbox.isChecked()
        self.url.setDisabled(not checked)
        if not checked:
            self.url_error.setText("")
            self.url.setStyleSheet("")

    def load_config(self, config):
        self.edit_mode = True
        self.original_name = config["name"]
        self.name.setText(config["name"])
        self.exe.setText(config["exe"])
        self.saves.setText(config["saves"])
        self.backup.setText(config["backup"])
        self.url.setText(config.get("url", ""))
        self.client_checkbox.setChecked(config.get("use_client", False))
        self.clear_errors()

    def clear_form(self):
        self.edit_mode = False
        self.original_name = ""
        self.name.clear()
        self.exe.clear()
        self.saves.clear()
        self.backup.clear()
        self.url.clear()
        self.client_checkbox.setChecked(False)
        self.clear_errors()

    def clear_errors(self):
        for err in [self.name_error, self.url_error, self.exe_error, self.saves_error, self.backup_error]:
            err.setText("")
        for f in [self.name, self.url, self.exe, self.saves, self.backup]:
            f.setStyleSheet("")

    def validate(self):
        ok = True
        required = [
            (self.name, self.name_error),
            (self.exe, self.exe_error),
            (self.saves, self.saves_error),
            (self.backup, self.backup_error)
        ]
        if self.client_checkbox.isChecked():
            required.append((self.url, self.url_error))
        else:
            self.url_error.setText("")
            self.url.setStyleSheet("")
        for field, err_label in required:
            if not field.text().strip():
                field.setStyleSheet("border:1px solid red")
                err_label.setText("Заполните указанное поле")
                ok = False
            else:
                field.setStyleSheet("")
                err_label.setText("")
        return ok

    def save(self, check_duplicate=True):
        if not self.validate():
            return

        config = {
            "name": self.name.text().strip(),
            "exe": self.exe.text().strip(),
            "saves": self.saves.text().strip(),
            "backup": self.backup.text().strip(),
            "url": self.url.text().strip(),
            "use_client": self.client_checkbox.isChecked()
        }

        if not self.edit_mode:
            if check_duplicate:
                if not self.manager.add(config):
                    QMessageBox.warning(self, "", "Указанная конфигурация уже существует!")
                    return
            else:
                self.manager.add(config)          # автосохранение
        else:
            self.manager.update(self.original_name, config)

        # Принудительно обновляем список сразу после сохранения
        self.parent.run_panel.reload_list()