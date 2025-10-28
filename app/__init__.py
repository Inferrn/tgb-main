"""Инициализация приложения и его компонентов"""
import sys
from typing import Optional, Callable, Awaitable, Dict, Any
from pathlib import Path
import os

from aiogram import Bot, Dispatcher
from aiogram.client.bot import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage
import logging

from app.handlers import register_handlers
from app.data.data_loader import load_survey_data
from app.config import Config
from app.services.image_service import ImageService
from app.services.survey_service import SurveyService
from app.ui.keyboards import KeyboardFactory
from app.ui.message_builder import MessageBuilder


logger = logging.getLogger(__name__)


def setup_logging():
    """Настройка логирования"""
    logging.basicConfig(
        level=getattr(logging, Config.LOG_LEVEL),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        stream=sys.stdout
    )


async def setup_bot(token: str):
    """
    Инициализация Bot + Dispatcher, создание общих сервисов
    и middleware для инъекции зависимостей в хэндлеры.
    Возвращает (bot, dp).
    """
    bot = Bot(token=token, default=DefaultBotProperties(parse_mode="HTML"))
    # Убедимся, что нет включённого webhook / других getUpdates
    try:
        await bot.delete_webhook(drop_pending_updates=True)
        logger.info("Webhook cleared (drop_pending_updates=True)")
    except Exception as e:
        logger.warning("Не удалось удалить webhook: %s", e)
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)

    # Создаём общие объекты — один экземпляр на процесс
    # Получаем путь к файлу опроса: сначала из Config, иначе смотрим в app/data/ovz.json
    try:
        survey_file = getattr(Config, "SURVEY_FILE", None)
        if not survey_file:
            survey_file = os.path.join(os.path.dirname(__file__), "data", "ovz.json")
        survey_data = load_survey_data(survey_file)
    except Exception as exc:
        logger.exception("Не удалось загрузить данные опроса: %s", exc)
        raise
    survey_service = SurveyService(survey_data)
    keyboard_factory = KeyboardFactory()
    # Инициализируем сервис работы с изображениями и билдера сообщений
    # Используем Config.IMAGES_DIR если задан, иначе папку app/images по умолчанию
    from pathlib import Path
    images_dir = getattr(Config, "IMAGES_DIR", None)
    if not images_dir:
        images_dir = Path(__file__).parent.joinpath("images")
    image_service = ImageService(str(images_dir))
    message_builder = MessageBuilder(image_service)

    # middleware для инъекции зависимостей в kwargs хэндлеров (message / callback_query)
    async def inject_deps(handler, event, data: dict):
        data.setdefault("survey_service", survey_service)
        data.setdefault("keyboard_factory", keyboard_factory)
        data.setdefault("message_builder", message_builder)
        return await handler(event, data)

    # регистрируем middleware для сообщений и callback_query
    dp.message.middleware(inject_deps)
    dp.callback_query.middleware(inject_deps)

    # регистрируем роутеры/хэндлеры
    register_handlers(dp)

    logger.info("Bot setup complete")
    return bot, dp