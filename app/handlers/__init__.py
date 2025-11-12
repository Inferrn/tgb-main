"""Инициализация роутеров и обработчиков"""
from aiogram import Router, Dispatcher

from app.handlers import base, question, level, admin

# Регистрация обработчиков в главном роутере
router = Router()
# Question handlers should be registered before base greetings to ensure
# survey-specific message handlers run first.
router.include_router(question.router)
router.include_router(base.router)
router.include_router(level.router)
router.include_router(admin.router)

def register_handlers(dp: Dispatcher):
    dp.include_router(router)