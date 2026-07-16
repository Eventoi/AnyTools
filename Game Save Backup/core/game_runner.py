# === Запуск и отслеживание игры ===
import subprocess
import psutil
import webbrowser
import time
import os

class GameRunner:
    def __init__(self, config, log):
        self.config = config
        self.log = log

    def run(self):
        name = self.config["name"]
        exe_path = self.config["exe"]
        exe_name = os.path.basename(exe_path)
        self.log(f"Ожидание запуска {name}")
        if self.config.get("use_client"):
            webbrowser.open(self.config["url"])
        else:
            subprocess.Popen(exe_path)
        self._wait_process_start(exe_name)
        self.log(f"{name} запущена")
        self.log("====== ИНФОРМАЦИЯ ======")
        self.log(f"Игра: {name}")
        self.log(f"Процесс: {exe_name}")
        self.log(f"Сейвы: {self.config['saves']}")
        self.log(f"Бэкап: {self.config['backup']}")
        self.log("==============================")
        self.log(f"Ожидание закрытия {name}")
        self._wait_process_end(exe_name)
        self.log(f"{name} закрыта")

    def _wait_process_start(self, exe_name):
        while True:
            for p in psutil.process_iter(['name']):
                if p.info['name'] == exe_name:
                    return
            time.sleep(1)

    def _wait_process_end(self, exe_name):
        while True:
            found = False
            for p in psutil.process_iter(['name']):
                if p.info['name'] == exe_name:
                    found = True
                    break
            if not found:
                return
            time.sleep(1)