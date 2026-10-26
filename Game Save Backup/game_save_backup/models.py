"""Модель конфигурации игры и её (де)сериализация в json."""
from dataclasses import dataclass

from .constants import APP_NAME

CONFIG_VERSION = 1

# Поля json-конфигурации (кроме названия игры)
_TEXT_KEYS = ("url", "exe_path", "saves_path", "backup_path")
_FLAG_KEYS = ("use_client", "dark_souls_mode")
_CONFIG_KEYS = _TEXT_KEYS + _FLAG_KEYS


@dataclass
class GameConfig:
    """Конфигурация одной игры (все поля формы)."""

    name: str = ""
    use_client: bool = False
    url: str = ""
    exe_path: str = ""
    saves_path: str = ""
    backup_path: str = ""
    dark_souls_mode: bool = False

    def to_dict(self) -> dict:
        """Преобразует конфигурацию в словарь для записи в json."""
        return {
            "app": APP_NAME,
            "version": CONFIG_VERSION,
            "game_name": self.name,
            "use_client": self.use_client,
            "url": self.url,
            "exe_path": self.exe_path,
            "saves_path": self.saves_path,
            "backup_path": self.backup_path,
            "dark_souls_mode": self.dark_souls_mode,
        }

    @classmethod
    def from_dict(cls, data: object) -> "GameConfig | None":
        """Создаёт конфигурацию из словаря.

        Принимаются и конфигурации, созданные или отредактированные вручную:
        обязательно только название игры, отсутствующие поля получают значения
        по умолчанию. Файл должен либо содержать отметку приложения, либо хотя бы
        одно из известных полей конфигурации, чтобы посторонние json-файлы
        не принимались за конфигурации.

        Возвращает None, если данные не подходят.
        """
        if not isinstance(data, dict):
            return None
        if "app" in data and data["app"] != APP_NAME:
            return None

        name = data.get("game_name")
        if not isinstance(name, str) or not name.strip():
            return None
        if "app" not in data and not any(key in data for key in _CONFIG_KEYS):
            return None

        texts: dict[str, str] = {}
        for key in _TEXT_KEYS:
            value = data.get(key, "")
            if not isinstance(value, str):
                return None
            texts[key] = value

        flags: dict[str, bool] = {}
        for key in _FLAG_KEYS:
            value = data.get(key, False)
            if not isinstance(value, bool):
                return None
            flags[key] = value

        return cls(
            name=name.strip(),
            use_client=flags["use_client"],
            url=texts["url"],
            exe_path=texts["exe_path"],
            saves_path=texts["saves_path"],
            backup_path=texts["backup_path"],
            dark_souls_mode=flags["dark_souls_mode"],
        )
