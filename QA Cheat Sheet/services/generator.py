from templates.templates import (
    EMAIL_TEMPLATE,
    FULL_NAME_TEMPLATE,
    DATE_TIME_TEMPLATE,
    FORM_TEMPLATE,
    BUTTON_TEMPLATE,
    DROPDOWN_TEMPLATE,
    SEARCH_TEMPLATE,
    INPUT_TEMPLATE,
)

FIELD_CONFIG = {
    "Email": EMAIL_TEMPLATE,
    "Выпадающий список": DROPDOWN_TEMPLATE,
    "Дата/Время": DATE_TIME_TEMPLATE,
    "Поиск": SEARCH_TEMPLATE,
    "ФИО": FULL_NAME_TEMPLATE,
}


def generate_checklist(main_type: str, selected_fields: list[str]) -> str:
    title = f"# Чит-лист: {main_type}"

    if main_type == "Поле":
        parts = []

        parts.append(INPUT_TEMPLATE.strip())

        for field in sorted(selected_fields):
            template = FIELD_CONFIG.get(field)
            if template:
                parts.append(template.strip())

        content = "\n\n<hr>\n\n".join(parts).strip()
        return f"{title}\n\n{content}"

    elif main_type == "Форма":
        return f"{title}\n\n{FORM_TEMPLATE.strip()}"

    elif main_type == "Кнопка":
        return f"{title}\n\n{BUTTON_TEMPLATE.strip()}"

    else:
        return f"{title}\n\n## Основное\n\n- Проверки для элемента {main_type}"