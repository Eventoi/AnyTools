"""Работа с именами папок: проверка символов, допустимых в операционной системе."""
import sys

from PySide6.QtGui import QValidator

_IS_WINDOWS = sys.platform == "win32"

_WINDOWS_RESERVED = {
    "CON", "PRN", "AUX", "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}


def forbidden_chars() -> set[str]:
    """Возвращает символы, которые нельзя использовать в имени папки текущей ОС."""
    if _IS_WINDOWS:
        return set('<>:"/\\|?*')
    if sys.platform == "darwin":
        return {"/", ":"}
    return {"/"}


def has_forbidden_chars(text: str) -> bool:
    """Проверяет, есть ли в тексте символы, недопустимые в имени папки."""
    forbidden = forbidden_chars()
    return any(ch in forbidden or ord(ch) < 32 for ch in text)


def sanitize_folder_name(raw: str) -> str:
    """Приводит введённое название к имени папки.

    Возвращает пустую строку, если из названия нельзя создать папку
    (пустое имя, служебные имена ОС, недопустимые символы).
    """
    name = raw.strip()
    if _IS_WINDOWS:
        name = name.rstrip(" .")
    if not name or name in (".", ".."):
        return ""
    if has_forbidden_chars(name):
        return ""
    if _IS_WINDOWS and name.split(".")[0].upper() in _WINDOWS_RESERVED:
        return ""
    return name


class FolderNameValidator(QValidator):
    """Не даёт ввести и вставить символы, запрещённые в имени папки."""

    def validate(self, text: str, pos: int):
        if has_forbidden_chars(text):
            return QValidator.State.Invalid, text, pos
        return QValidator.State.Acceptable, text, pos
