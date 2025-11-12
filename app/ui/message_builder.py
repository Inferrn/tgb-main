"""Построитель сообщений для опроса"""
from typing import Optional, List
from aiogram.types import Message, InlineKeyboardMarkup

from app.data.data_models import Level, Question
from app.services.image_service import ImageService

import logging

logger = logging.getLogger(__name__)


class MessageBuilder:
    """Класс для построения и отправки сообщений с вопросами"""

    def __init__(self, image_service: ImageService):
        """
        Инициализирует построитель сообщений

        Args:
            image_service: Сервис для работы с изображениями
        """
        self.image_service = image_service

    async def send_level_message(
        self,
        message: Message,
        level: Level,
        level_text: str,
        markup: InlineKeyboardMarkup,
    ) -> List[Message]:
        """
        Отправляет один уровень (возможно с изображением) и возвращает список отправленных Message.
        """
        sent = None
        if getattr(level, "image", None) and self.image_service.has_image(level.image):
            sent = await message.answer_photo(
                photo=self.image_service.get_image(level.image),
                caption=level_text,
                reply_markup=markup,
            )
        else:
            sent = await message.answer(text=level_text, reply_markup=markup)
        return [sent] if sent is not None else []

    async def send_question_message(
        self,
        message: Message,
        question: Question,
        markup: InlineKeyboardMarkup,
        current_level: Optional[int] = None,
        level_text: Optional[str] = None,
    ) -> List[Message]:
        """
        Отправляет сообщение (возможно несколько сообщений: фото уровней + текст) и возвращает список отправленных Message.

        Поведение:
        - Если это вопрос с уровнями и current_level указан — отправляет уровень (или общее фото + подпись)
        - Если это обычный вопрос с image — отправляет фото с подписью (options)
        - Если вопрос содержит уровни (и current_level не задан) — отправляет изображения всех уровней (unique)
        - В конце отправляет текстовый вариант вопроса (если не были отправлены фото+caption с клавиатурой)
        """
        sent_messages: List[Message] = []

        # Вопрос с уровнями и текущим уровнем
        if getattr(question, "levels", None) and current_level is not None and 0 <= current_level < len(question.levels):
            level = question.levels[current_level]

            if not level_text:
                level_text = (f"{question.text}\n\n" if current_level == 0 else "")
                if getattr(level, "height", None):
                    level_text += f"• {level.height}"
                elif getattr(level, "angle", None):
                    level_text += f"• {level.angle}"
                elif getattr(level, "surface", None):
                    level_text += f"• {level.surface}"

            # Если на первом уровне есть общее изображение — присылаем его с подписью
            if current_level == 0 and getattr(question, "image", None) and self.image_service.has_image(question.image):
                m = await message.answer_photo(
                    photo=self.image_service.get_image(question.image),
                    caption=level_text,
                    reply_markup=markup,
                )
                sent_messages.append(m)
                return sent_messages

            # Иначе отправляем конкретный уровень
            sent = await self.send_level_message(message, level, level_text, markup)
            sent_messages.extend(sent)
            return sent_messages

        # Обычный вопрос без текущего уровня — построим подпись с опциями
        opts = getattr(question, "options", None) or []
        options_lines: List[str] = []
        if opts:
            for i, opt in enumerate(opts, start=1):
                label = getattr(opt, "text", None) or getattr(opt, "label", None) or str(opt)
                # Если label уже начинается с цифры, не префиксируем
                if isinstance(label, str) and label.strip() and label.strip()[0].isdigit():
                    options_lines.append(label)
                else:
                    options_lines.append(f"{i}. {label}")

        # Показываем варианты ответов в тексте сообщения ТОЛЬКО для специального вопроса
        # (по текущей задаче — вопрос с id == 5). Это убирает дублирование ответов
        # в окне с вопросом для остальных вопросов.
        include_options = getattr(question, "id", None) == 5

        # Если у вопроса есть изображение — отправляем фото с подписью, включающей опции
        if getattr(question, "image", None) and self.image_service.has_image(question.image):
            caption = question.text
            if options_lines and include_options:
                caption += "\n\n" + "\n".join(options_lines)
            m = await message.answer_photo(
                photo=self.image_service.get_image(question.image),
                caption=caption,
                reply_markup=markup,
            )
            sent_messages.append(m)
            return sent_messages
        else:
            if getattr(question, "image", None):
                logger.debug(f"Изображение не найдено в кеше: {question.image}")

        # Обработка уровней (без current_level) — возможно нужно показать изображения уровней
        level_texts: List[str] = []
        level_images: List[str] = []
        if getattr(question, "levels", None):
            for lvl in question.levels:
                if getattr(lvl, "height", None):
                    level_texts.append(f"• {lvl.height}")
                elif getattr(lvl, "angle", None):
                    level_texts.append(f"• {lvl.angle}")
                elif getattr(lvl, "surface", None):
                    level_texts.append(f"• {lvl.surface}")
                if getattr(lvl, "image", None):
                    level_images.append(lvl.image)

            # Удаляем дубликаты, сохраняем порядок
            unique_images = list(dict.fromkeys(level_images))
            for img in unique_images:
                if self.image_service.has_image(img):
                    m = await message.answer_photo(photo=self.image_service.get_image(img))
                    sent_messages.append(m)
                else:
                    logger.debug(f"Уровневое изображение не найдено в кеше: {img}")

        # Отправляем текст вопроса с вариантами (включая уровни в описании)
        full_text = question.text
        if level_texts:
            full_text += "\n\n" + "\n".join(level_texts)
        if options_lines and include_options:
            full_text += "\n\n" + "\n".join(options_lines)

        m = await message.answer(full_text, reply_markup=markup)
        sent_messages.append(m)
        return sent_messages

    def build_question_text(self, question) -> str:
        """
        Универсальный рендер текста вопроса. Фоллбек — собрать текст и опции.
        """
        for alt in ("format_question_text", "render_question", "question_text"):
            if hasattr(self, alt):
                return getattr(self, alt)(question)

        text = getattr(question, "text", "Вопрос")
        opts = getattr(question, "options", None) or []
        include_options = getattr(question, "id", None) == 5
        if opts and include_options:
            lines = [text, ""]
            for i, opt in enumerate(opts, start=1):
                label = getattr(opt, "text", None) or getattr(opt, "label", None) or str(opt)
                lines.append(f"{i}. {label}")
            return "\n".join(lines)
        return text

    def build_level_text(self, question, level, level_index: int = 0) -> str:
        """
        Рендер уровня (подвопроса) внутри вопроса.
        """
        for alt in ("format_level_text", "render_level"):
            if hasattr(self, alt):
                return getattr(self, alt)(question, level, level_index)

        title = getattr(question, "text", "Вопрос")
        if getattr(level, "height", None):
            level_title = level.height
        elif getattr(level, "angle", None):
            level_title = level.angle
        elif getattr(level, "surface", None):
            level_title = level.surface
        else:
            level_title = getattr(level, "text", f"Уровень {level_index + 1}")

        opts = getattr(level, "options", None) or []
        include_options = getattr(question, "id", None) == 5
        lines = [f"{title} — {level_title}", ""]
        if opts and include_options:
            for i, opt in enumerate(opts, start=1):
                label = getattr(opt, "text", None) or getattr(opt, "label", None) or str(opt)
                if isinstance(label, str) and label.strip() and label.strip()[0].isdigit():
                    lines.append(label)
                else:
                    lines.append(f"{i}. {label}")
        return "\n".join(lines)

    def build_finish_text(self, results: dict) -> str:
        """
        Рендер результата опроса (сгруппировать уровни под базовыми ключами).
        """
        for alt in ("format_finish_text", "render_finish"):
            if hasattr(self, alt):
                return getattr(self, alt)(results)

        if not results:
            return "Опрос завершён. Спасибо!"

        lines = ["Опрос завершён. Результаты:"]

        if isinstance(results, dict):
            # Соберём базовые ответы и уровни под ключами вида '<module>:<qid>'
            grouped = {}
            for k, v in results.items():
                # Формат уровня: '<module>:<qid>:level_<n>'
                if isinstance(k, str) and k.count(":") >= 2 and ":level_" in k:
                    base, level_part = k.rsplit(":", 1)
                    try:
                        lvl_idx = int(level_part.replace("level_", ""))
                    except Exception:
                        lvl_idx = None
                    entry = grouped.setdefault(base, {"value": None, "levels": {}})
                    entry["levels"][lvl_idx] = v
                else:
                    entry = grouped.setdefault(k, {"value": None, "levels": {}})
                    entry["value"] = v

            # Вывод в детерминированном порядке
            for base_key in sorted(grouped.keys()):
                entry = grouped[base_key]
                if entry.get("value") is not None:
                    val = entry["value"]
                    if isinstance(val, (list, tuple)):
                        val = ", ".join(map(str, val))
                    lines.append(f"{base_key}: {val}")
                if entry.get("levels"):
                    for idx in sorted([i for i in entry["levels"].keys() if i is not None]):
                        val = entry["levels"].get(idx)
                        if isinstance(val, (list, tuple)):
                            val = ", ".join(map(str, val))
                        lines.append(f"{base_key}: level {idx + 1}: {val}")
        else:
            lines.append(str(results))

        return "\n".join(lines)