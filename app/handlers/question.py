"""Обработчики вопросов опроса"""
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

logger = logging.getLogger(__name__)

router = Router()
question_lock = Lock()


async def ask_question(
    message: Message,
    state: FSMContext,
    survey_service: SurveyService = None,
    keyboard_factory: KeyboardFactory = None,
    message_builder: MessageBuilder = None
):
    """Отправляет текущий вопрос пользователю."""
    logger.debug("ask_question: start; user=%s", message.from_user.id if message.from_user else None)
    data = await state.get_data()
    module = data.get("current_module")
    qid = data.get("current_question_id")
    current_level = data.get("current_level", 0)

    question = survey_service.get_question(module, qid)
    if not question:
        await message.answer("Вопрос не найден.")
        logger.error("ask_question: question not found: %s %s", module, qid)
        return

    # Уровни внутри вопроса
    if getattr(question, "levels", None):
        level = survey_service.get_level(module, qid, current_level)
        if not level:
            await message.answer("Ошибка уровня.")
            logger.error("ask_question: level not found: %s %s level=%s", module, qid, current_level)
            return
        # Построим клавиатуру и отправим сообщение через MessageBuilder,
        # чтобы при наличии изображения оно отправлялось корректно
        kb = keyboard_factory.level_keyboard(question, level, current_level)
        try:
            has_img = False
            if getattr(message_builder, 'image_service', None) and getattr(message_builder.image_service, 'has_image', None):
                try:
                    has_img = message_builder.image_service.has_image(getattr(question, 'image', '') or '')
                except Exception:
                    has_img = False
            logger.debug("ask_question: level send; question.image=%s has_image=%s", getattr(question, 'image', None), has_img)
        except Exception:
            logger.exception("ask_question: error checking image")
        try:
            sent_list = await message_builder.send_question_message(message, question, kb, current_level, message_builder.build_level_text(question, level, current_level))
            # запомним id(ы) отправленных сообщений, чтобы можно было удалить их по окончании
            try:
                sent_ids = [getattr(m, 'message_id', None) for m in (sent_list or [])]
                sent_ids = [i for i in sent_ids if i]
                prev = (await state.get_data()).get('last_message_ids', []) or []
                await state.update_data(last_message_ids=prev + sent_ids)
            except Exception:
                logger.debug("ask_question: could not save last_message_ids to state")
            # сообщение для уровня отправлено — не выполнять общий path, вернёмся
            return
        except Exception as e:
            logger.exception("ask_question: send_question_message failed, falling back to text send: %s", e)
            # падаем обратно в общий path — сформируем текст и клавиатуру для отправки ниже
            text = message_builder.build_level_text(question, level, current_level)
            # kb уже определена
    else:
        text = message_builder.build_question_text(question)
        qtype = str(getattr(question, "type", "")).lower()
        if qtype.startswith("multiple"):
            kb = keyboard_factory.multi_keyboard(question, selected=data.get("selected_options", []))
        elif getattr(question, "expects_text", False):
            kb = None
        else:
            kb = keyboard_factory.single_keyboard(question)

        # Если у вопроса есть изображение — используем MessageBuilder, чтобы прикрепить фото
        try:
            if getattr(message_builder, 'image_service', None) and getattr(question, 'image', None):
                if message_builder.image_service.has_image(question.image):
                        sent_list = await message_builder.send_question_message(message, question, kb)
                        try:
                            sent_ids = [getattr(m, 'message_id', None) for m in (sent_list or [])]
                            sent_ids = [i for i in sent_ids if i]
                            prev = (await state.get_data()).get('last_message_ids', []) or []
                            await state.update_data(last_message_ids=prev + sent_ids)
                        except Exception:
                            logger.debug("ask_question: could not save last_message_ids to state")
                        logger.debug("ask_question: sent question with image %s:%s image=%s", module, qid, question.image)
                        return
        except Exception:
            logger.exception("ask_question: error while sending image, falling back to text")

    # Защита: если по какой-то причине text/kb не были определены в ветках выше,
    # сформируем их здесь по умолчанию.
    if 'text' not in locals() or text is None:
        text = message_builder.build_question_text(question)
    if 'kb' not in locals() or kb is None:
        qtype = str(getattr(question, "type", "")).lower()
        if qtype.startswith("multiple"):
            kb = keyboard_factory.multi_keyboard(question, selected=data.get("selected_options", []))
        elif getattr(question, "expects_text", False):
            kb = None
        else:
            kb = keyboard_factory.single_keyboard(question)

    sent = await message.answer(text, reply_markup=kb)
    try:
        sent_ids = [getattr(sent, 'message_id', None)]
        sent_ids = [i for i in sent_ids if i]
        prev = (await state.get_data()).get('last_message_ids', []) or []
        await state.update_data(last_message_ids=prev + sent_ids)
    except Exception:
        logger.debug("ask_question: could not save last_message_ids to state")
    logger.debug("ask_question: sent question %s:%s", module, qid)


async def handle_next_question(
    message_or_callback,
    state: FSMContext,
    survey_service: SurveyService = None,
    keyboard_factory: KeyboardFactory = None,
    message_builder: MessageBuilder = None
):
    """Вычисляет и отправляет следующий вопрос."""
    async with question_lock:
        data = await state.get_data()
        module = data.get("current_module")
        qid = data.get("current_question_id")
        answers = data.get("answers", {})

        logger.debug("handle_next_question: current %s:%s answers=%s", module, qid, answers)

        # Получаем ответ на текущий вопрос (сохраняется под ключом "{module}:{qid}")
        last_answer = answers.get(f"{module}:{qid}")
        # Передаём в сервис значение ответа (не весь словарь)
        next_module, next_qid = survey_service.get_next_question(module, qid, last_answer)

        if next_module is None and next_qid is None:
            # конец опроса
            results = answers
            await state.clear()
            # Не показываем пользователю детализированный дамп ответов (в виде ключей modul:qid).
            # Вместо этого отправляем краткое подтверждение. Полные результаты логируем для администратора/отладки.
            try:
                user_info = None
                if isinstance(message_or_callback, CallbackQuery):
                    user_info = getattr(message_or_callback.from_user, 'id', None)
                else:
                    user_info = getattr(message_or_callback.from_user, 'id', None)
                logger.info("handle_next_question: survey results for user=%s: %s", user_info, results)
            except Exception:
                logger.info("handle_next_question: survey results: %s", results)
            text = "Благодарим за участие в проекте «Город для всех»! 🌆\n" \
            "Ваш вклад поможет нам создавать решения, которые улучшат жизнь людей с ОВЗ.\n" \
            "Следите за обновлениями — вместе мы сделаем город доступнее!\n" \
            "Если у вас есть дополнительные комментарии или предложения, вы всегда можете связаться с нами. Группа в VK: https://vk.com/city_for_everyone?from=groups"
            if isinstance(message_or_callback, CallbackQuery):
                # Попытаемся удалить последнее отправленное ботом сообщение (вопрос), если оно записано в state
                try:
                    last_msg_ids = data.get('last_message_ids') or []
                    if last_msg_ids and isinstance(message_or_callback, CallbackQuery):
                        for mid in last_msg_ids:
                            try:
                                await message_or_callback.message.bot.delete_message(chat_id=message_or_callback.message.chat.id, message_id=mid)
                                logger.info("handle_next_question: deleted last_message_id=%s", mid)
                            except Exception as e:
                                logger.debug("handle_next_question: could not delete last_message_id=%s: %s", mid, e)

                    # Также попробуем удалить сам callback.message на всякий случай
                    if isinstance(message_or_callback, CallbackQuery):
                        try:
                            await message_or_callback.message.delete()
                            logger.info("handle_next_question: deleted callback.message id=%s", getattr(message_or_callback.message, 'message_id', None))
                        except Exception as e:
                            logger.debug("handle_next_question: could not delete callback.message: %s", e)

                    # Наконец, отправим итог как новое сообщение
                    await message_or_callback.message.answer(text)
                except Exception:
                    try:
                        await message_or_callback.answer(text)
                    except Exception:
                        logger.exception("handle_next_question: failed to deliver finish text for callback")
            else:
                # message_or_callback — Message: используем обычный answer
                await message_or_callback.answer(text)
            logger.info("handle_next_question: survey finished for user")
            return

        # обновляем state
        await state.update_data({
            "current_module": next_module,
            "current_question_id": next_qid,
            "current_level": 0,
            "selected_options": []
        })

        # отправляем следующий вопрос
        target_msg = message_or_callback.message if isinstance(message_or_callback, CallbackQuery) else message_or_callback
        await ask_question(target_msg, state, survey_service, keyboard_factory, message_builder)
        logger.debug("handle_next_question: moved to %s:%s", next_module, next_qid)


@router.callback_query(SurveyStates.in_progress, F.data.startswith("single:"))
async def handle_single_option(
    callback: CallbackQuery,
    state: FSMContext,
    survey_service: SurveyService = None,
    keyboard_factory: KeyboardFactory = None,
    message_builder: MessageBuilder = None
):
    """Обработка single-option"""
    logger.debug("handle_single_option: enter user=%s data=%s", callback.from_user.id if callback.from_user else None, callback.data)
    if question_lock.locked():
        await callback.answer("Подождите, предыдущий ответ обрабатывается...")
        logger.debug("handle_single_option: lock is locked")
        return

    should_advance = False
    async with question_lock:
        try:
            parts = callback.data.split(":")
            # format: single:<question_id>:<option_index>
            if len(parts) < 3:
                await callback.answer("Неправильные данные кнопки")
                return
            _, qid_cb, idx_cb = parts
            try:
                opt_index = int(idx_cb)
            except ValueError:
                await callback.answer("Неправильный индекс опции")
                return
            data = await state.get_data()
            module = data.get("current_module")
            qid = data.get("current_question_id")

            question = survey_service.get_question(module, qid)
            if not question:
                await callback.answer("Вопрос не найден")
                logger.error("handle_single_option: question not found %s:%s", module, qid)
                return

            opts = getattr(question, "options", []) or []
            if opt_index < 0 or opt_index >= len(opts):
                await callback.answer("Неправильный вариант")
                return
            chosen_value = opts[opt_index]

            # Сохраняем ответ (текст опции)
            answers = data.get("answers", {})
            answers_key = f"{module}:{qid}"
            answers[answers_key] = chosen_value
            await state.update_data(answers=answers)

            await callback.answer()  # ack
            logger.info("handle_single_option: saved %s -> %s", answers_key, chosen_value)

            # Для отладки: узнали ли мы следующий вопрос
            try:
                next_mod, next_q = survey_service.get_next_question(module, qid, chosen_value)
                logger.info("handle_single_option: next -> %s:%s", next_mod, next_q)
            except Exception:
                logger.exception("handle_single_option: get_next_question failed")

            # помечаем, что нужно продвинуть опрос — вызов сделаем после выхода из блока lock
            should_advance = True
        except Exception as e:
            logger.exception("handle_single_option error: %s", e)
            await callback.answer("Ошибка обработки ответа")
    # Вне lock — продвигаем опрос (чтобы избежать повторного захвата того же lock)
    if should_advance:
        await handle_next_question(callback, state, survey_service, keyboard_factory, message_builder)

@router.callback_query(SurveyStates.in_progress, F.data.startswith("multi:"))
async def handle_multi_toggle(
    callback: CallbackQuery,
    state: FSMContext,
    survey_service: SurveyService = None,
    keyboard_factory: KeyboardFactory = None,
    message_builder: MessageBuilder = None
):
    """Toggle для multi-select"""
    logger.debug("handle_multi_toggle: enter user=%s data=%s", callback.from_user.id if callback.from_user else None, callback.data)
    try:
        parts = callback.data.split(":")
        # format: multi:<question_id>:<option_index>
        if len(parts) < 3:
            await callback.answer("Неправильные данные кнопки")
            return
        _, qid_cb, idx_cb = parts
        try:
            opt_index = int(idx_cb)
        except ValueError:
            await callback.answer("Неправильный индекс опции")
            return
        data = await state.get_data()
        module = data.get("current_module")
        qid = data.get("current_question_id")

        question = survey_service.get_question(module, qid)
        if not question:
            await callback.answer("Вопрос не найден")
            return

        opts = getattr(question, "options", []) or []
        if opt_index < 0 or opt_index >= len(opts):
            await callback.answer("Вариант не найден")
            return

        selected = data.get("selected_options", [])
        # хранить индексы
        if opt_index in selected:
            selected.remove(opt_index)
        else:
            selected.append(opt_index)

        await state.update_data(selected_options=selected)

        # обновим клавиатуру
        kb = keyboard_factory.multi_keyboard(question, selected=selected)
        try:
            await callback.message.edit_reply_markup(reply_markup=kb)
        except Exception:
            logger.debug("handle_multi_toggle: edit_reply_markup failed")

        await callback.answer()
        logger.debug("handle_multi_toggle: toggled %s selected=%s", opt_index, selected)
    except Exception as e:
        logger.exception("handle_multi_toggle error: %s", e)
        await callback.answer("Ошибка")


@router.callback_query(SurveyStates.in_progress, F.data == "multi_submit")
async def handle_multi_submit(
    callback: CallbackQuery,
    state: FSMContext,
    survey_service: SurveyService = None,
    keyboard_factory: KeyboardFactory = None,
    message_builder: MessageBuilder = None
):
    """Подтверждение multi-select"""
    logger.debug("handle_multi_submit: enter user=%s", callback.from_user.id if callback.from_user else None)
    try:
        data = await state.get_data()
        module = data.get("current_module")
        qid = data.get("current_question_id")
        selected = data.get("selected_options", [])

        question = survey_service.get_question(module, qid)
        if not question:
            await callback.answer("Вопрос не найден")
            return

        opts = getattr(question, "options", []) or []
        # Нельзя подтвердить пустой выбор
        if not selected:
            await callback.answer("Выберите хотя бы один вариант")
            return

        # Конвертируем индексы в тексты опций
        try:
            chosen_texts = [opts[i] for i in selected]
        except Exception as e:
            logger.exception("handle_multi_submit: invalid selected indices %s", selected)
            await callback.answer("Ошибка обработки выбора")
            return

        answers = data.get("answers", {})
        answers_key = f"{module}:{qid}"
        answers[answers_key] = chosen_texts
        await state.update_data(answers=answers, selected_options=[])

        await callback.answer()
        logger.info("handle_multi_submit: saved %s -> %s", answers_key, chosen_texts)
        await handle_next_question(callback, state, survey_service, keyboard_factory, message_builder)
    except Exception as e:
        logger.exception("handle_multi_submit error: %s", e)
        await callback.answer("Ошибка обработки")

# NOTE: debug_all_callbacks removed — use structured logs instead