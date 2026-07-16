# === Менеджер конфигураций (упрощённая версия без configs_index.json) ===
import json
import os
from PySide6.QtCore import QSettings


class ConfigManager:
    def __init__(self):
        self.settings = QSettings("GameSaveBackup", "Config")
        roots = self.settings.value("backup_roots", [])
        if isinstance(roots, str):
            self.backup_roots = [roots] if roots else []
        else:
            self.backup_roots = list(roots) if isinstance(roots, (list, tuple)) else []

    def _get_all_config_paths(self):
        """Сканирует все backup_roots и собирает пути к {game_name}.json"""
        config_paths = []
        for root in self.backup_roots:
            if not isinstance(root, str) or not os.path.exists(root):
                continue
            try:
                for item in os.listdir(root):
                    game_dir = os.path.join(root, item)
                    if not os.path.isdir(game_dir):
                        continue
                    json_path = os.path.join(game_dir, f"{item}.json")
                    if os.path.exists(json_path):
                        config_paths.append(json_path)
            except Exception:
                continue
        return config_paths

    def get_configs(self):
        """Возвращает список всех конфигураций"""
        configs = []
        for path in self._get_all_config_paths():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    config = json.load(f)
                    if isinstance(config, dict) and "name" in config:
                        configs.append(config)
            except Exception:
                continue
        return sorted(configs, key=lambda x: x.get("name", "").lower())

    def add(self, config):
        """Добавляет новую конфигурацию"""
        name = config.get("name")
        backup_root = config.get("backup")
        if not name or not backup_root:
            return False

        # Добавляем backup_root в список
        if backup_root not in self.backup_roots:
            self.backup_roots.append(backup_root)
            self.settings.setValue("backup_roots", self.backup_roots)
            self.settings.sync()                     # ← Важно!

        game_dir = os.path.join(backup_root, name)
        os.makedirs(game_dir, exist_ok=True)

        config_path = os.path.join(game_dir, f"{name}.json")

        if os.path.exists(config_path):
            return False

        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=4)

        self.settings.sync()                         # ← Принудительная запись
        return True

    def update(self, original_name, config):
        """Обновляет конфигурацию"""
        new_name = config.get("name")
        new_backup = config.get("backup")
        if not new_name or not new_backup:
            return

        old_config = self.get_by_name(original_name)
        if not old_config:
            return

        old_backup = old_config.get("backup", "")
        old_game_dir = os.path.join(old_backup, original_name)
        new_game_dir = os.path.join(new_backup, new_name)

        if old_game_dir != new_game_dir and os.path.exists(old_game_dir):
            os.makedirs(os.path.dirname(new_game_dir), exist_ok=True)
            if not os.path.exists(new_game_dir):
                try:
                    os.rename(old_game_dir, new_game_dir)
                except Exception:
                    pass

        elif not os.path.exists(new_game_dir):
            os.makedirs(new_game_dir, exist_ok=True)

        if original_name != new_name:
            old_json = os.path.join(new_game_dir, f"{original_name}.json")
            if os.path.exists(old_json):
                try:
                    os.remove(old_json)
                except Exception:
                    pass

        new_config_path = os.path.join(new_game_dir, f"{new_name}.json")
        with open(new_config_path, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=4)

        if new_backup not in self.backup_roots:
            self.backup_roots.append(new_backup)
            self.settings.setValue("backup_roots", self.backup_roots)

        self.settings.sync()                         # ← Принудительная запись

    def set_last_used(self, name):
        if name:
            self.settings.setValue("last_used", name)
            self.settings.sync()

    def get_last_used(self):
        return self.settings.value("last_used")

    def get_by_name(self, name):
        if not name:
            return None
        for path in self._get_all_config_paths():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    config = json.load(f)
                    if config.get("name") == name:
                        return config
            except Exception:
                continue
        return None