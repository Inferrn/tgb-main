"""Функции для кодирования callback данных"""
from dataclasses import is_dataclass


def get_callback_data(option) -> str:
    """
    Возвращает стабильную строковую идентификацию для опции.
    Поддерживает: str, dict, dataclass, объекты с атрибутами id/value/name.

    Args:
        option: Опция для получения идентификации

    Returns:
        str: Идентификация опции в виде строки
    """
    if option is None:
        return ""
    if isinstance(option, str):
        return option
    if isinstance(option, dict):
        return str(option.get("id") or option.get("value") or option.get("name") or option)
    if is_dataclass(option):
        for attr in ("id", "value", "key", "name"):
            if hasattr(option, attr):
                return str(getattr(option, attr))
        return str(option)
    # generic object
    for attr in ("id", "value", "name"):
        if hasattr(option, attr):
            return str(getattr(option, attr))
    return str(option)


def create_callback(prefix: str, option) -> str:
    """
    Формат callback: "<prefix>:<id>"
    prefix — например: "single", "multi", "level"

    Args:
        prefix: Префикс для callback data
        option: Опция для получения идентификации

    Returns:
        str: Callback data в формате "prefix:id"
    """
    return f"{prefix}:{get_callback_data(option)}"