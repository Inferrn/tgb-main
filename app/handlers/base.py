"""Базовые обработчики команд"""
from aiogram import Router
from aiogram.types import Message
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
import logging

from app.states.survey_states import SurveyStates
from app.config import Config
from app.services.survey_service import SurveyService
from app.ui.keyboards import KeyboardFactory
from app.ui.message_builder import MessageBuilder
from app.handlers.question import ask_question
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
from aiogram import F

logger = logging.getLogger(__name__)

router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext,
                    survey_service: SurveyService = None,
                    keyboard_factory: KeyboardFactory = None,
                    message_builder: MessageBuilder = None):
    """
    /start — показываем приветственное сообщение с кнопкой 'Начать опрос'
    """
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="Начать опрос", callback_data="start_survey")
    ]])
    await message.answer("Привет! Готовы пройти короткий опрос о доступности городской среды?",
                         reply_markup=kb)


@router.callback_query(F.data == "start_survey")
async def cb_start_survey(callback: CallbackQuery, state: FSMContext,
                          survey_service: SurveyService = None,
                          keyboard_factory: KeyboardFactory = None,
                          message_builder: MessageBuilder = None):
    """Callback для запуска опроса из приветственного сообщения"""
    # Инициализируем состояние опроса и отправляем первый вопрос
    # Сначала очистим предыдущее состояние, чтобы не осталось флагов вроде processing_answer
    try:
        await state.clear()
    except Exception:
        pass

    await state.set_state(SurveyStates.in_progress)
    await state.update_data({
        "current_module": getattr(Config, "DEFAULT_MODULE", None),
        "current_question_id": getattr(Config, "DEFAULT_QUESTION_ID", None),
        "current_level": 0,
        "answers": {},
        "selected_options": [],
        "last_message_ids": []
    })
    # Ответим пользователю и удалим приветственное сообщение
    try:
        await callback.message.delete()
    except Exception:
        pass
    await ask_question(callback.message, state, survey_service, keyboard_factory, message_builder)



@router.message(~F.text.startswith('/'))
async def greet_user(message: Message, state: FSMContext,
                     survey_service: SurveyService = None,
                     keyboard_factory: KeyboardFactory = None,
                     message_builder: MessageBuilder = None):
    """Показать приветствие и кнопку 'Начать опрос' при любом входящем сообщении, если опрос ещё не в процессе"""
    # Если опрос уже идёт — ничего не делаем
    current = await state.get_state()
    try:
        # current can be a State object or its string name; cover common cases
        if current == SurveyStates.in_progress or (isinstance(current, str) and current.endswith(":in_progress")):
            return
    except Exception:
        pass

    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="Начать опрос", callback_data="start_survey")
    ]])
    await message.answer("Привет! Хотите пройти короткий опрос о доступности городской среды? Нажмите кнопку ниже, чтобы начать.",
                         reply_markup=kb)


@router.message(Command(commands=["survey"]))
async def cmd_survey(message: Message, state: FSMContext,
                     survey_service: SurveyService = None,
                     keyboard_factory: KeyboardFactory = None,
                     message_builder: MessageBuilder = None):
    """
    Альтернатива: команда /survey — поведение такое же как /start
    """
    await cmd_start(message, state, survey_service, keyboard_factory, message_builder)


@router.message(Command(commands=["newtry"]))
async def cmd_newtry(message: Message, state: FSMContext,
                     survey_service: SurveyService = None,
                     keyboard_factory: KeyboardFactory = None,
                     message_builder: MessageBuilder = None):
    """
    /newtry — начать новый проход опроса: удалить предыдущие вопросы (если были) и сбросить ответы.
    """
    # Сообщим пользователю, что начинаем новую попытку
    try:
        await message.answer("Начинаю новую попытку прохождения опроса...")
    except Exception:
        pass

    # Получим список ранее отправленных ботом сообщений (если есть)
    last_msg_ids = []
    try:
        data = await state.get_data()
        last_msg_ids = data.get('last_message_ids') or []
    except Exception:
        last_msg_ids = []

    # Сбросим состояние и данные перед началом новой попытки
    try:
        await state.clear()
    except Exception:
        pass

    # Пытаемся удалить предыдущие сообщения бота (тихо игнорируем ошибки)
    logger.debug("cmd_newtry: last_message_ids=%s", last_msg_ids)
    for mid in last_msg_ids:
        try:
            await message.bot.delete_message(chat_id=message.chat.id, message_id=mid)
        except Exception:
            # Игнорируем ошибки удаления (возможно сообщение уже удалено)
            pass

    # Инициируем новый проход
    await state.set_state(SurveyStates.in_progress)
    await state.update_data({
        "current_module": getattr(Config, "DEFAULT_MODULE", None),
        "current_question_id": getattr(Config, "DEFAULT_QUESTION_ID", None),
        "current_level": 0,
        "answers": {},
        "selected_options": [],
        "last_message_ids": []
    })

    # Отправляем первый вопрос нового прохождения и уведомляем пользователя при ошибке
    try:
        await ask_question(message, state, survey_service, keyboard_factory, message_builder)
    except Exception:
        try:
            await message.answer("Не удалось начать новую попытку — попробуйте ещё раз или напишите /start")
        except Exception:
            pass