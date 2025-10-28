"""Фабрика клавиатур для бота"""
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from typing import Iterable, Optional

from app.data.encoder import create_callback, get_callback_data


class KeyboardFactory:
    """
    Фабрика inline-клавиатур для вопросов.
    Методы возвращают InlineKeyboardMarkup.
    """

    def _label(self, opt) -> str:
        return getattr(opt, "text", None) or getattr(opt, "label", None) or str(opt)

    def single_keyboard(self, question) -> InlineKeyboardMarkup:
        builder = InlineKeyboardBuilder()
        for i, opt in enumerate(getattr(question, "options", []) or []):
            # callback format: single:<question_id>:<option_index>
            cb = f"single:{getattr(question, 'id', '')}:{i}"
            builder.button(text=self._label(opt), callback_data=cb)
        builder.adjust(1)
        return builder.as_markup()

    def multi_keyboard(self, question, selected: Optional[Iterable[str]] = None) -> InlineKeyboardMarkup:
        selected = set(selected or [])
        builder = InlineKeyboardBuilder()
        for i, opt in enumerate(getattr(question, "options", []) or []):
            opt_id = str(i)
            label = self._label(opt)
            if int(opt_id) in selected:
                label = "✅ " + label
            cb = f"multi:{getattr(question, 'id', '')}:{i}"
            builder.button(text=label, callback_data=cb)
        builder.adjust(1)
        # кнопка подтверждения
        builder.button(text="Подтвердить", callback_data="multi_submit")
        return builder.as_markup()

    def level_keyboard(self, question, level, level_index: int = 0) -> InlineKeyboardMarkup:
        """
        Генерирует клавиатуру для уровня вопроса.
        level.options может быть списком строк или объектов.
        """
        builder = InlineKeyboardBuilder()
        for i, opt in enumerate(getattr(level, "options", []) or []):
            cb = f"level:{getattr(question, 'id', '')}:{level_index}:{i}"
            builder.button(text=self._label(opt), callback_data=cb)
        builder.adjust(1)
        return builder.as_markup()