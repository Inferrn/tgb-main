"""Обработчики для уровней вопросов"""
from aiogram import F, Router
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from asyncio import Lock
import logging

from app.states.survey_states import SurveyStates
from app.data.encoder import get_callback_data
from app.services.survey_service import SurveyService
from app.ui.keyboards import KeyboardFactory
from app.ui.message_builder import MessageBuilder
from app.handlers.question import handle_next_question, ask_question

logger = logging.getLogger(__name__)

router = Router()
level_lock = Lock()


@router.callback_query(SurveyStates.in_progress, F.data.startswith("level:"))
async def handle_level_option_select(
    callback: CallbackQuery, 
    state: FSMContext, 
    survey_service: SurveyService = None,
    keyboard_factory: KeyboardFactory = None,
    message_builder: MessageBuilder = None
):
    """
    Обработчик выбора варианта для уровня вопроса
    """
    if level_lock.locked():
        await callback.answer("Подождите, обрабатывается предыдущий ответ")
        return

    async with level_lock:
        try:
            # формат callback: level:<question_id>:<level_index>:<option_index>
            parts = callback.data.split(":")
            if len(parts) < 4:
                await callback.answer("Неправильные данные кнопки уровня")
                return
            _, qid_cb, level_idx_cb, opt_idx_cb = parts
            try:
                level_index = int(level_idx_cb)
                opt_index = int(opt_idx_cb)
            except ValueError:
                await callback.answer("Неправильный индекс кнопки")
                return

            data = await state.get_data()
            module = data.get('current_module')
            qid = data.get('current_question_id')
            current_level = data.get('current_level', 0)
            logger.debug("handle_level_option_select: parts=%s module=%s qid=%s level_index=%s opt_index=%s", parts, module, qid, level_index, opt_index)

            # защита: qid в callback должен совпадать с текущим
            try:
                if int(qid_cb) != int(qid):
                    logger.warning("handle_level_option_select: qid mismatch callback=%s state=%s", qid_cb, qid)
            except Exception:
                pass

            level = survey_service.get_level(module, qid, level_index)
            if not level:
                await callback.answer("Уровень не найден")
                return

            options = survey_service.get_options_for_level(level)
            logger.debug("handle_level_option_select: options_len=%s options_sample=%s", len(options), options[:3] if isinstance(options, list) else options)
            if opt_index < 0 or opt_index >= len(options):
                await callback.answer("Вариант не найден")
                return

            # Получаем текст опции
            chosen = options[opt_index]
            chosen_text = getattr(chosen, 'text', None) or getattr(chosen, 'label', None) or str(chosen)

            # Сохраняем ответ уровня в state под ключом module:qid:level_N
            answers = data.get("answers", {})
            answers_key = f"{module}:{qid}:level_{level_index}"
            answers[answers_key] = chosen_text
            await state.update_data(answers=answers)

            # Переходим на следующий уровень или к следующему вопросу
            next_level = level_index + 1
            next_level_obj = survey_service.get_level(module, qid, next_level)
            if next_level_obj:
                await state.update_data(current_level=next_level)
                await ask_question(callback.message, state, survey_service, keyboard_factory, message_builder)
                await callback.answer()
                return
            else:
                await state.update_data(current_level=0)
                await callback.answer()
                await handle_next_question(callback, state, survey_service, keyboard_factory, message_builder)
        except Exception as e:
            logger.exception("handle_level_option_select error: %s", e)
            await callback.answer("Ошибка обработки ответа")