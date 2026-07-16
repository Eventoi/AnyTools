# === Менеджер бэкапов ===
import os
import shutil
from datetime import datetime
import zipfile

class BackupManager:
    def __init__(self, config):
        self.config = config

    def run(self):
        name = self.config["name"]
        saves = self.config["saves"]
        backup_root = self.config["backup"]
        if not os.path.exists(saves):
            return
        game_dir = os.path.join(backup_root, name)
        os.makedirs(game_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        new_folder = os.path.join(game_dir, f"{name}_{timestamp}")
        os.makedirs(new_folder, exist_ok=True)
        # === Копирование файлов ===
        for item in os.listdir(saves):
            src = os.path.join(saves, item)
            dst = os.path.join(new_folder, item)
            if os.path.isdir(src):
                shutil.copytree(src, dst, dirs_exist_ok=True)
            else:
                shutil.copy2(src, dst)
        self._archive(game_dir)

    def _archive(self, game_dir):
        dirs = sorted([
            d for d in os.listdir(game_dir)
            if os.path.isdir(os.path.join(game_dir, d))
        ])
        if len(dirs) < 2:
            return
        prev = dirs[-2]
        prev_path = os.path.join(game_dir, prev)
        zip_path = prev_path + ".zip"
        with zipfile.ZipFile(zip_path, "w") as z:
            for root, _, files in os.walk(prev_path):
                for f in files:
                    full = os.path.join(root, f)
                    z.write(full, os.path.relpath(full, prev_path))
        shutil.rmtree(prev_path)
        archives = sorted([f for f in os.listdir(game_dir) if f.endswith(".zip")])
        while len(archives) > 10:
            os.remove(os.path.join(game_dir, archives.pop(0)))