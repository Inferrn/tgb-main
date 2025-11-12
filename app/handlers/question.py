"""Обработчики вопросов опроса"""
from aiogram import F, Router
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
import asyncio
from asyncio import Lock
import logging

from app.states.survey_states import SurveyStates
from app.data.encoder import get_callback_data
from app.services.survey_service import SurveyService
from app.services.db_service import DBService
from app.ui.keyboards import KeyboardFactory
from app.ui.message_builder import MessageBuilder

logger = logging.getLogger(__name__)

router = Router()
question_lock = Lock()
# Temporary diagnostic flag: when True, perform synchronous DB save at survey finish
# so exceptions surface in the main handler and appear in logs. Turn off after debugging.
TEMP_SYNC_SAVE = True


async def ask_question(
    message: Message,
    state: FSMContext,
    survey_service: SurveyService = None,
    keyboard_factory: KeyboardFactory = None,
    message_builder: MessageBuilder = None
):
    """Отправляет текущий вопрос пользователю."""
    logger.debug("ask_question: start; user=%s", message.from_user.id if message.from_user else None)
    # Очистим возможный залипший флаг processing_answer перед показом вопроса
    try:
        prev = (await state.get_data()).get("processing_answer")
        if prev:
            logger.debug("ask_question: clearing stale processing_answer flag for user=%s", message.from_user.id if message.from_user else None)
        await state.update_data(processing_answer=False)
    except Exception:
        logger.debug("ask_question: could not clear processing_answer flag")

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
                last_ids_prev = (await state.get_data()).get('last_message_ids', []) or []
                await state.update_data(last_message_ids=last_ids_prev + sent_ids)
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
    message_builder: MessageBuilder = None,
    db_service: DBService = None
):
    """Вычисляет и отправляет следующий вопрос."""
    logger.info("handle_next_question: invoked for user (callback?=%s)", isinstance(message_or_callback, CallbackQuery))
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
            # Попробуем сохранить результаты в БД в фоне (если инжектирован db_service).
            # Сохранение в фоне предотвращает блокировку обработчика и лаг в клиенте.
            try:
                user_info = None
                if isinstance(message_or_callback, CallbackQuery):
                    user_info = getattr(message_or_callback.from_user, 'id', None)
                else:
                    user_info = getattr(message_or_callback.from_user, 'id', None)
                # Diagnostic: log db_service value to help debug missing saves
                try:
                    logger.info("handle_next_question: db_service=%s for user=%s", repr(db_service), user_info)
                except Exception:
                    logger.debug("handle_next_question: could not repr db_service for user=%s", user_info)

                # If db_service is missing, notify admins (if configured) so we can detect injection issues;
                # otherwise, schedule background save as before.
                if db_service is None:
                    try:
                        raw = os.getenv('ADMIN_IDS', '')
                        admin_ids = [int(p.strip()) for p in raw.split(',') if p.strip().isdigit()]
                    except Exception:
                        admin_ids = []
                    try:
                        bot_obj = None
                        try:
                            bot_obj = message_or_callback.bot
                        except Exception:
                            bot_obj = None
                        if bot_obj and admin_ids:
                            for aid in admin_ids:
                                try:
                                    await bot_obj.send_message(aid, f"Diagnostic: db_service is None when saving survey for user {user_info}")
                                except Exception:
                                    logger.exception("handle_next_question: failed to notify admin %s", aid)
                        else:
                            logger.info("handle_next_question: cannot notify admins (no bot or no ADMIN_IDS configured)")
                    except Exception:
                        logger.exception("handle_next_question: admin notification failed")
                elif user_info is not None:
                    try:
                        # schedule background save to the project's Russian schema; don't await to avoid blocking
                        username = None
                        try:
                            username = getattr(message_or_callback.from_user, 'username', None)
                        except Exception:
                            username = None

                        # Provide additional diagnostic logs about db_service and results
                        try:
                            logger.info("handle_next_question: db_service_id=%s db_service_type=%s for user=%s",
                                        id(db_service) if db_service is not None else None,
                                        type(db_service).__name__ if db_service is not None else None,
                                        user_info)
                        except Exception:
                            logger.debug("handle_next_question: could not log db_service id/type for user=%s", user_info)

                        # show a compact dump of results for debugging (truncated)
                        try:
                            sample = dict(list(results.items())[:10])
                            logger.debug("handle_next_question: results sample for user=%s: %s", user_info, repr(sample)[:1000])
                        except Exception:
                            logger.debug("handle_next_question: could not produce results sample for user=%s", user_info)

                        if TEMP_SYNC_SAVE:
                            # Synchronous save for diagnostics: await the save so exceptions are visible
                            logger.info("handle_next_question: TEMP_SYNC_SAVE enabled - performing synchronous save for user=%s", user_info)
                            try:
                                ank = await db_service.save_to_anketa_schema(user_info, results, username=(username or ''))
                                logger.info("handle_next_question: sync save succeeded for user=%s anketa_id=%s rows_saved=%s",
                                            user_info, getattr(ank, 'id', None), getattr(ank, 'rows_saved', 'unknown'))
                            except Exception:
                                logger.exception("handle_next_question: sync save failed for user=%s", user_info)
                        else:
                            async def _bg_save():
                                logger.info("handle_next_question: background save started for user=%s", user_info)
                                try:
                                    ank = await db_service.save_to_anketa_schema(user_info, results, username=(username or ''))
                                    logger.info("handle_next_question: background save succeeded for user=%s anketa_id=%s", user_info, getattr(ank, 'id', None))
                                except Exception:
                                    logger.exception("handle_next_question: background save failed for user=%s", user_info)

                            logger.info("handle_next_question: scheduling background save task for user=%s", user_info)
                            task = asyncio.create_task(_bg_save())
                            logger.info("handle_next_question: scheduled background save task=%s for user=%s", repr(task), user_info)
                            # attach a done callback to log unhandled exceptions explicitly
                            def _on_done(t):
                                try:
                                    exc = t.exception()
                                    if exc:
                                        logger.exception("handle_next_question: background save task raised", exc_info=exc)
                                except asyncio.CancelledError:
                                    logger.info("handle_next_question: background save task cancelled for user=%s", user_info)
                                except Exception:
                                    # exception already logged in task, ignore
                                    pass

                            try:
                                task.add_done_callback(_on_done)
                            except Exception:
                                logger.debug("handle_next_question: could not add done callback to save task for user=%s", user_info)
                    except Exception:
                        logger.exception("handle_next_question: failed to schedule DB save for user=%s", user_info)
            except Exception:
                logger.exception("handle_next_question: error while attempting to schedule save to DB")

            # Очищаем state (и логируем возможные ошибки)
            try:
                await state.clear()
                logger.info("handle_next_question: state cleared for user")
            except Exception as e:
                logger.exception("handle_next_question: failed to clear state: %s", e)
            # Не показываем пользователю детализированный дамп ответов (в виде ключей modul:qid).
            # Вместо этого отправляем краткое подтверждение. Полные результаты логируем для администратора/отладки.
            try:
                logger.info("handle_next_question: survey results for user=%s: %s", user_info, results)
            except Exception:
                logger.info("handle_next_question: survey results: %s", results)
            text = "Благодарим за участие в проекте «Город для всех»! 🌆\n" \
            "Ваш вклад поможет нам создавать решения, которые улучшат жизнь людей с ОВЗ.\n" \
            "Следите за обновлениями — вместе мы сделаем город доступнее!\n" \
            "Если у вас есть дополнительные комментарии или предложения, вы всегда можете связаться с нами. Группа в VK: https://vk.com/city_for_everyone?from=groups"
            if isinstance(message_or_callback, CallbackQuery):
                # Не удаляем предыдущие сообщения (по требованию пользователя) — просто ответим
                try:
                    # Убедимся, что callback-ack отправлен прежде чем делать тяжёлые операции
                    try:
                        await message_or_callback.answer()
                    except Exception:
                        pass
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

        # Гарантируем очистку флага обработки перед отправкой следующего вопроса
        try:
            await state.update_data(processing_answer=False)
        except Exception:
            logger.debug("handle_next_question: could not clear processing_answer flag before next question")

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
    message_builder: MessageBuilder = None,
    db_service: DBService = None
):
    """Обработка single-option"""
    logger.debug("handle_single_option: enter user=%s data=%s", callback.from_user.id if callback.from_user else None, callback.data)

    # Fast check to avoid unnecessary locking for obvious concurrent cases
    data = await state.get_data()
    if data.get("processing_answer"):
        try:
            await callback.answer("Подождите, предыдущий ответ обрабатывается...")
        except Exception:
            pass
        logger.debug("handle_single_option: already processing answer (fast path)")
        return

    should_advance = False
    # Ensure only one handler runs the critical section at a time
    async with question_lock:
        # Re-read state inside the lock to avoid races
        state_data = await state.get_data()
        if state_data.get("processing_answer"):
            try:
                await callback.answer("Подождите, предыдущий ответ обрабатывается...")
            except Exception:
                pass
            logger.debug("handle_single_option: already processing answer (inside lock)")
            return

        # Mark as processing
        await state.update_data(processing_answer=True)
        try:
            parts = callback.data.split(":")
            # format: single:<question_id>:<option_index>
            if len(parts) < 3:
                try:
                    await callback.answer("Неправильные данные кнопки")
                except Exception:
                    pass
                return
            _, qid_cb, idx_cb = parts
            try:
                opt_index = int(idx_cb)
            except ValueError:
                try:
                    await callback.answer("Неправильный индекс опции")
                except Exception:
                    pass
                return

            data = await state.get_data()
            module = data.get("current_module")
            qid = data.get("current_question_id")

            question = survey_service.get_question(module, qid)
            if not question:
                try:
                    await callback.answer("Вопрос не найден")
                except Exception:
                    pass
                logger.error("handle_single_option: question not found %s:%s", module, qid)
                return

            opts = getattr(question, "options", []) or []
            if opt_index < 0 or opt_index >= len(opts):
                try:
                    await callback.answer("Неправильный вариант")
                except Exception:
                    pass
                return

            chosen_value = opts[opt_index]

            # Save the answer into FSM state
            answers = data.get("answers", {})
            answers_key = f"{module}:{qid}"
            answers[answers_key] = chosen_value
            await state.update_data(answers=answers)

            # ACK the callback immediately so the client UI updates
            try:
                await callback.answer()
            except Exception:
                pass

            logger.info("handle_single_option: saved %s -> %s", answers_key, chosen_value)

            # For debugging: see what the survey service computes as next
            try:
                next_mod, next_q = survey_service.get_next_question(module, qid, chosen_value)
                logger.info("handle_single_option: next -> %s:%s", next_mod, next_q)
            except Exception:
                logger.exception("handle_single_option: get_next_question failed")

            # Indicate that we should advance the survey after releasing lock
            should_advance = True
        except Exception as e:
            logger.exception("handle_single_option error: %s", e)
            try:
                await callback.answer("Ошибка обработки ответа")
            except Exception:
                pass
        finally:
            # Ensure processing flag is cleared
            try:
                await state.update_data(processing_answer=False)
            except Exception:
                logger.debug("handle_single_option: could not clear processing_answer flag in finally")
    # Outside the lock — advance the survey if needed
    if should_advance:
        # pass through db_service when calling internal helper so it doesn't rely on middleware
        try:
            # db_service may be injected into this handler by middleware if we add it to signature;
            # if not present in this scope, attempt to fetch from state data as fallback
            db_service = locals().get('db_service', None)
        except Exception:
            db_service = None
        try:
            logger.info("handle_single_option: advancing -> calling handle_next_question with db_service=%s id=%s type=%s for user=%s",
                        repr(db_service), id(db_service) if db_service is not None else None,
                        type(db_service).__name__ if db_service is not None else None,
                        callback.from_user.id if callback.from_user else None)
        except Exception:
            logger.debug("handle_single_option: could not log db_service before advancing")
        await handle_next_question(callback, state, survey_service, keyboard_factory, message_builder, db_service)


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
            try:
                await callback.answer("Неправильные данные кнопки")
            except Exception:
                pass
            return
        _, qid_cb, idx_cb = parts
        try:
            opt_index = int(idx_cb)
        except ValueError:
            try:
                await callback.answer("Неправильный индекс опции")
            except Exception:
                pass
            return
        data = await state.get_data()
        module = data.get("current_module")
        qid = data.get("current_question_id")

        question = survey_service.get_question(module, qid)
        if not question:
            try:
                await callback.answer("Вопрос не найден")
            except Exception:
                pass
            return

        opts = getattr(question, "options", []) or []
        if opt_index < 0 or opt_index >= len(opts):
            try:
                await callback.answer("Вариант не найден")
            except Exception:
                pass
            return

        selected = data.get("selected_options", []) or []
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

        try:
            await callback.answer()
        except Exception:
            pass
        logger.debug("handle_multi_toggle: toggled %s selected=%s", opt_index, selected)
    except Exception as e:
        logger.exception("handle_multi_toggle error: %s", e)
        try:
            await callback.answer("Ошибка")
        except Exception:
            pass
@router.callback_query(SurveyStates.in_progress, F.data == "multi_submit")
async def handle_multi_submit(
    callback: CallbackQuery,
    state: FSMContext,
    survey_service: SurveyService = None,
    keyboard_factory: KeyboardFactory = None,
    message_builder: MessageBuilder = None,
    db_service: DBService = None
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

        # Если в вариантах есть точная опция "Не готов", убедимся, что она не выбрана одновременно с другими
        try:
            exclusive_idx = None
            for i_opt, opt_val in enumerate(opts):
                opt_text = opt_val if isinstance(opt_val, str) else getattr(opt_val, 'text', str(opt_val))
                if isinstance(opt_text, str) and opt_text.strip().lower() == "не готов":
                    exclusive_idx = i_opt
                    break
            if exclusive_idx is not None and exclusive_idx in selected and len(selected) > 1:
                # Покажем предупреждение и не будем сохранять ответ
                try:
                    await callback.answer("Вы выбрали взаимоисключающие варианты. Пожалуйста, оставьте только один из них.", show_alert=True)
                except Exception:
                    await callback.answer("Вы выбрали взаимоисключающие варианты. Пожалуйста, оставьте только один из них.")
                return

            # Конвертируем индексы в тексты опций
            chosen_texts = [opts[i] for i in selected]
        except Exception as e:
            logger.exception("handle_multi_submit: invalid selected indices %s", selected)
            await callback.answer("Ошибка обработки выбора")
            return

        answers = data.get("answers", {})
        answers_key = f"{module}:{qid}"
        # Сохраняем выбранные опции как список (чтобы совместимость с логикой осталась)
        answers[answers_key] = chosen_texts

        # Проверим, выбран ли вариант "Другой..." — если да, запросим текст у пользователя
        other_selected = False
        try:
            for t in chosen_texts:
                if isinstance(t, str) and "друг" in t.lower():
                    other_selected = True
                    break
        except Exception:
            other_selected = False

        if other_selected:
            # Сохраним answers, но не очищаем selected_options — пользователь может добавить/убрать варианты
            await state.update_data(answers=answers)
            # Отметим, что ожидаем ввод пользовательского варианта для данного вопроса
            await state.update_data(awaiting_custom_for=answers_key)

            # На всякий случай подтвердим, что выбор сохранён и попросим ввести текст
            try:
                await callback.message.answer("Пожалуйста, введите свой вариант.\n(Вы можете также выбрать другие варианты ответа)")
            except Exception:
                try:
                    await callback.answer("Пожалуйста, введите свой вариант. (Вы можете также выбрать другие варианты ответа)")
                except Exception:
                    pass

            await callback.answer()
            logger.info("handle_multi_submit: saved %s -> %s (awaiting custom)", answers_key, chosen_texts)
            # Не продвигаем опрос дальше — ждём текст от пользователя
            return

        # Обычный путь: нет варианта 'Другой' — сохраняем и идём дальше
        await state.update_data(answers=answers, selected_options=[])

        await callback.answer()
        logger.info("handle_multi_submit: saved %s -> %s", answers_key, chosen_texts)
        try:
            await handle_next_question(callback, state, survey_service, keyboard_factory, message_builder, db_service)
        except Exception as e:
            logger.exception("handle_multi_submit error: %s", e)
            await callback.answer("Ошибка обработки")
    except Exception as e:
        # Outer catch-all for the multi_submit handler to ensure any unexpected
        # errors are logged and the user receives a generic message.
        logger.exception("handle_multi_submit outer error: %s", e)
        try:
            await callback.answer("Ошибка обработки")
        except Exception:
            pass

# NOTE: debug_all_callbacks removed — use structured logs instead


@router.message(SurveyStates.in_progress, F.text)
async def handle_text_during_survey(
    message: Message,
    state: FSMContext,
    survey_service: SurveyService = None,
    keyboard_factory: KeyboardFactory = None,
    message_builder: MessageBuilder = None,
    db_service: DBService = None
):
    """Обработка текстового ввода во время опроса — используется для варианта "Другой вариант" в мультивыборе"""
    data = await state.get_data()
    awaiting = data.get("awaiting_custom_for")
    logger.debug("handle_text_during_survey: enter user=%s awaiting=%s text=%s", message.from_user.id if message.from_user else None, awaiting, (message.text or '')[:200])
    if not awaiting:
        # Текст не ожидается — игнорируем (другие текстовые вопросы пока не обрабатываем здесь)
        logger.debug("handle_text_during_survey: no awaiting flag, ignoring message")
        return

    # Ожидаем формат awaiting = '<module>:<qid>'
    answers = data.get("answers", {})
    selected = data.get("selected_options", []) or []

    text = (message.text or "").strip()
    if not text:
        await message.answer("Пожалуйста, введите непустой текст для варианта 'Другой'.")
        return

    # Сохраняем пользовательский ответ в отдельном ключе рядом с основным
    try:
        answers[f"{awaiting}:custom_answer"] = text
        # Обновим основной ключ с актуальными выбранными опциями (в случае, если пользователь менял выбор)
        module, qid = awaiting.split(":", 1)
        qid = int(qid) if qid.isdigit() else qid
        question = survey_service.get_question(module, qid)
        opts = getattr(question, "options", []) or []
        # rebuild chosen_texts from selected indices if possible
        try:
            chosen_texts = [opts[i] for i in (selected or [])]
        except Exception:
            chosen_texts = answers.get(awaiting, [])
        answers[awaiting] = chosen_texts
        await state.update_data(answers=answers, awaiting_custom_for=None, selected_options=[])
        logger.info("handle_text_during_survey: saved custom for %s -> %s", awaiting, text)
    except Exception as e:
        logger.exception("handle_text_during_survey: failed to save custom answer: %s", e)
        await message.answer("Не удалось сохранить ваш вариант — попробуйте ещё раз.")
        return

    # Подтверждение и продвижение опроса
    try:
        await message.answer("Спасибо — ваш вариант сохранён.")
    except Exception:
        pass

    # Продвигаем опрос дальше
    try:
        # try to pass db_service through if it was injected into this handler
        try:
            db_service = locals().get('db_service', None)
        except Exception:
            db_service = None
        await handle_next_question(message, state, survey_service, keyboard_factory, message_builder, db_service)
    except Exception as e:
        logger.exception("handle_text_during_survey: failed to advance survey: %s", e)