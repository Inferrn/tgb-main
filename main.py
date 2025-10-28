"""Основной файл для запуска бота"""
import asyncio
import logging
import os
from pathlib import Path
from aiogram import Bot
from dotenv import load_dotenv, find_dotenv

from app import setup_bot, setup_logging


async def main():
    """Основная функция запуска бота"""
    # Загружаем переменные окружения из .env (пытаемся найти файл явно)
    dotenv_path = find_dotenv()
    if dotenv_path:
        load_dotenv(dotenv_path)
    else:
        # пробуем взять .env рядом с main.py
        env_file = Path(__file__).resolve().parent / ".env"
        if env_file.exists():
            load_dotenv(env_file)
            dotenv_path = str(env_file)
        else:
            # fallback — попытка загрузить по умолчанию (может читать из cwd)
            load_dotenv()

    # Настроим логирование (читает Config.LOG_LEVEL)
    setup_logging()
    logging.getLogger(__name__).info("Logging initialized")
    
    # Получаем токен бота из переменных окружения
    # Попробуем явно прочитать токен из файла .env (если найден), иначе из переменных окружения
    token = None
    if dotenv_path:
        try:
            with open(dotenv_path, 'r', encoding='utf-8') as f:
                for line in f:
                    if line.strip().startswith('BOT_TOKEN='):
                        token = line.strip().split('=', 1)[1]
                        break
        except Exception:
            # если не удалось прочитать файл — будем полагаться на os.getenv
            token = None

    if not token:
        token = os.getenv("BOT_TOKEN")
    # Простая проверка на placeholder-значения
    if not token or token.strip() == "" or token.strip().lower().startswith("ваш_") or token.strip().upper().startswith("REPLACE"):
        raise ValueError(
            "BOT_TOKEN не установлен или содержит placeholder. Пожалуйста, укажите реальный токен в .env или в переменной окружения BOT_TOKEN."
        )
    
    # Настраиваем бота
    bot, dp = await setup_bot(token)
    
    # Запускаем опрос событий в режиме long polling
    await dp.start_polling(bot)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Бот остановлен")
    except Exception as e:
        logging.error(f"Критическая ошибка: {e}", exc_info=True)