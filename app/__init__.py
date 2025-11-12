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
from app.services.db_service import DBService
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
    # DB: ensure tables and provide db_service
    try:
        from app.database.models import engine, Base
        db_service = DBService()
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Database tables ensured")
    except Exception as e:
        logger.exception("Failed to init database: %s", e)
        db_service = DBService()

    # middleware для инъекции зависимостей в kwargs хэндлеров (message / callback_query)
    async def inject_deps(handler, event, data: dict):
        # Diagnostic logging: record whether db_service is available when middleware runs
        try:
            evt_name = type(event).__name__ if event is not None else 'None'
            handler_name = getattr(handler, '__name__', repr(handler))
            # use INFO level so diagnostic appears in default logs and helps debugging in production
            logger.info("inject_deps: handler=%s event=%s db_service_present=%s", handler_name, evt_name, db_service is not None)
            try:
                # extra debug info: what keys are already present in data before assignment
                logger.debug("inject_deps.debug: preassign data keys=%s", list(data.keys()))
            except Exception:
                logger.debug("inject_deps.debug: could not list preassign data keys")
        except Exception:
            logger.info("inject_deps: could not log dependency injection info")

        # force-assign dependencies into handler data. Use explicit assignment to avoid
        # existing user/state keys silently shadowing injected services (was using setdefault).
        data["survey_service"] = survey_service
        data["keyboard_factory"] = keyboard_factory
        data["message_builder"] = message_builder
        data["db_service"] = db_service
        try:
            # log id/type and final keys after assignment at DEBUG level (non-sensitive)
            logger.debug(
                "inject_deps.debug: assigned services db_service_id=%s db_service_type=%s data_keys=%s",
                id(db_service) if db_service is not None else None,
                type(db_service).__name__ if db_service is not None else None,
                list(data.keys())
            )
        except Exception:
            logger.debug("inject_deps.debug: could not log assigned services info")
        return await handler(event, data)

    # регистрируем middleware для сообщений и callback_query
    dp.message.middleware(inject_deps)
    dp.callback_query.middleware(inject_deps)

    # регистрируем роутеры/хэндлеры
    register_handlers(dp)

    logger.info("Bot setup complete")
    return bot, dp