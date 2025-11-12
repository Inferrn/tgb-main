import json
import logging
from sqlalchemy import select
from app.database.models import (
    async_session,
    Persona,
    Anketa,
    AnketaAnswer,
)

logger = logging.getLogger(__name__)


class DBService:
    """Сервис для сохранения результатов опроса в БД (sqlite/postgres через SQLAlchemy async)."""

    def __init__(self, session_maker=async_session):
        self.session_maker = session_maker


    async def save_to_anketa_schema(self, tg_id: int, answers: dict, username: str = None):
        """Сохранить ответы в схему `Анкета`/`Анкета_ответ` (русские таблицы).

        Логика:
        - Найти или создать Persona по tg_id (User_id)
        - Создать запись в Анкета (проход)
        - Для каждой пары вопрос-ответ создать запись в Анкета_ответ
        """
        try:
            # ensure person — persist separately so later rollbacks won't remove it
            person = None
            if 'Persona' in globals():
                async with self.session_maker() as session:
                    person = await session.scalar(select(Persona).where(Persona.user_id == tg_id))
                    if not person:
                        person = Persona(user_id=tg_id, username=(username or ''))
                        session.add(person)
                        await session.commit()
                        # reload to obtain assigned id
                        person = await session.scalar(select(Persona).where(Persona.user_id == tg_id))

            # create anketa and answers in a separate session
            async with self.session_maker() as session:
                from sqlalchemy import text
                from types import SimpleNamespace

                ank = None
                try:
                    # If this person already has an Анкета, reuse it and delete previous answers
                    pid_local = getattr(person, 'id', None) if person is not None else None
                    existing_ank = None
                    if pid_local is not None:
                        try:
                            # use execute + scalars() to reliably get ORM object (works in async session)
                            # Order by id desc — some legacy schemas don't have created_at
                            res = await session.execute(
                                select(Anketa).where(Anketa.person_id == pid_local).order_by(Anketa.id.desc()).limit(1)
                            )
                            existing_ank = res.scalars().first()
                            logger.debug("DBService: existing_ank lookup for person_id=%s -> %s", pid_local, getattr(existing_ank, 'id', None))
                        except Exception:
                            # If select fails for some legacy schema, ignore and proceed to create
                            logger.debug("DBService: existing_ank lookup failed for person_id=%s", pid_local, exc_info=True)
                            existing_ank = None

                        # Fallback: some very old layouts may not have person_id column and use Анкета.id == Персона.id
                        if existing_ank is None:
                            try:
                                res2 = await session.execute(
                                    select(Anketa).where(Anketa.id == pid_local).order_by(Anketa.id.desc()).limit(1)
                                )
                                existing_ank = res2.scalars().first()
                                logger.debug("DBService: fallback existing_ank lookup by id for person_id=%s -> %s", pid_local, getattr(existing_ank, 'id', None))
                            except Exception:
                                logger.debug("DBService: fallback existing_ank lookup by id failed for person_id=%s", pid_local, exc_info=True)
                                existing_ank = None

                    if existing_ank is not None:
                        # delete previous answers for this anketa so we can overwrite
                        logger.info("DBService: reusing existing anketa id=%s for person_id=%s - deleting previous answers", existing_ank.id, pid_local)
                        try:
                            await session.execute(text('DELETE FROM "Анкета_ответ" WHERE "anketa_id" = :aid'), {'aid': existing_ank.id})
                        except Exception:
                            # fallback to ORM delete
                            from sqlalchemy import delete as _del
                            await session.execute(_del(AnketaAnswer).where(AnketaAnswer.anketa_id == existing_ank.id))
                        ank = existing_ank
                    else:
                        ank = Anketa(person_id=pid_local)
                        session.add(ank)
                        await session.flush()
                        logger.info("DBService: created new Анкета id=%s for person_id=%s", getattr(ank, 'id', None), pid_local)
                except Exception as e:
                    msg = str(e).lower() + ' ' + repr(e).lower()
                    if 'person_id' in msg or 'undefinedcolumnerror' in msg:
                        await session.rollback()

                        pid = getattr(person, 'id', None) if person is not None else None
                        if pid is None:
                            raise RuntimeError('Persona id is None; cannot create legacy Анкета')

                        # Try several fallback INSERT variants to support different legacy schemas.
                        # 1) Preferred: table has column person_id -> INSERT person_id
                        # 2) Older: table has columns id + id_q -> INSERT id,id_q (original fallback)
                        # 3) Very old: Анкета.id == Персона.id -> INSERT id only

                        # determine a reasonable id_q value from answers (first numeric qid found)
                        id_q_value = 0
                        for k in (answers or {}):
                            try:
                                _mod, qid_s = str(k).split(":", 1)
                                qid_token = str(qid_s).split(":", 1)[0]
                                if qid_token.isdigit():
                                    id_q_value = int(qid_token)
                                    break
                            except Exception:
                                continue

                        inserted = None
                        # attempt 1: insert with person_id
                        try:
                            logger.info("DBService: fallback attempt INSERT person_id for Анкета (person_id=%s)", pid)
                            res = await session.execute(
                                text('INSERT INTO "Анкета" ("person_id") VALUES (:person_id) RETURNING "id"'),
                                {'person_id': pid}
                            )
                            inserted = res.scalar_one()
                            ank = SimpleNamespace(id=inserted)
                            logger.info("DBService: fallback person_id insert succeeded, anketa_id=%s", inserted)
                        except Exception as e1:
                            logger.info("DBService: fallback insert with person_id failed: %s", e1)
                            await session.rollback()
                            # attempt 2: insert id + id_q (legacy layout)
                            try:
                                logger.info("DBService: fallback attempt INSERT id+id_q for Анкета (id=%s, id_q=%s)", pid, id_q_value)
                                res = await session.execute(
                                    text('INSERT INTO "Анкета" ("id", "id_q") VALUES (:id, :id_q) RETURNING "id"'),
                                    {'id': pid, 'id_q': id_q_value}
                                )
                                inserted = res.scalar_one()
                                ank = SimpleNamespace(id=inserted)
                                logger.info("DBService: fallback id+id_q insert succeeded, anketa_id=%s", inserted)
                            except Exception as e2:
                                logger.info("DBService: fallback insert with id+id_q failed: %s", e2)
                                await session.rollback()
                                # attempt 3: insert id only (anketa.id == persona.id)
                                try:
                                    logger.info("DBService: fallback attempt INSERT id only for Анкета (id=%s)", pid)
                                    res = await session.execute(
                                        text('INSERT INTO "Анкета" ("id") VALUES (:id) RETURNING "id"'),
                                        {'id': pid}
                                    )
                                    inserted = res.scalar_one()
                                    ank = SimpleNamespace(id=inserted)
                                    logger.info("DBService: fallback id-only insert succeeded, anketa_id=%s", inserted)
                                except Exception as e3:
                                    logger.info("DBService: fallback insert with id only failed: %s", e3)
                                    await session.rollback()
                                    # re-raise original to be handled by outer except
                                    raise
                    else:
                        raise

                # Precompute mapping from answer_text -> Ответ.id to populate answer_id when possible
                try:
                    from app.database.models import Otvet
                    # collect distinct texts that will be stored in answer_text
                    texts = set()
                    for key, val in (answers or {}).items():
                        try:
                            _, qid_s = str(key).split(":", 1)
                            qid_token = str(qid_s).split(":", 1)[0]
                        except Exception:
                            qid_token = None

                        if isinstance(val, list):
                            for v in val:
                                txt = json.dumps(v, ensure_ascii=False) if not isinstance(v, str) else v
                                if txt is not None:
                                    texts.add(txt)
                        else:
                            txt = json.dumps(val, ensure_ascii=False) if not isinstance(val, str) else val
                            if txt is not None:
                                texts.add(txt)

                    text_to_id = {}
                    if texts:
                        res = await session.execute(select(Otvet.id, Otvet.text).where(Otvet.text.in_(list(texts))))
                        for rid, rtext in res.fetchall():
                            text_to_id[rtext] = rid
                except Exception:
                    # If anything goes wrong with lookup, continue without mappings
                    logger.debug("DBService: could not build answer_text->id map", exc_info=True)
                    text_to_id = {}

                count = 0
                for key, val in (answers or {}).items():
                    module = None
                    qid = None
                    try:
                        module, qid_s = str(key).split(":", 1)
                        # qid_s may include extra parts (e.g. '27:level_0') — take first token
                        qid_token = str(qid_s).split(":", 1)[0]
                        qid = int(qid_token) if qid_token.isdigit() else None
                    except Exception:
                        module = str(key)

                    # Если значение — список (multi-select), создаём запись на каждый элемент
                    if isinstance(val, list):
                        for v in val:
                            atxt = json.dumps(v, ensure_ascii=False) if not isinstance(v, str) else v
                            aid = text_to_id.get(atxt)
                            ai = AnketaAnswer(
                                anketa_id=getattr(ank, 'id', None),
                                question_id=qid,
                                answer_id=aid,
                                answer_text=atxt
                            )
                            session.add(ai)
                            count += 1
                    else:
                        atxt = json.dumps(val, ensure_ascii=False) if not isinstance(val, str) else val
                        aid = text_to_id.get(atxt)
                        ai = AnketaAnswer(
                            anketa_id=getattr(ank, 'id', None),
                            question_id=qid,
                            answer_id=aid,
                            answer_text=atxt
                        )
                        session.add(ai)
                        count += 1

                await session.commit()
                logger.info("DBService: saved to anketa schema for tg_id=%s anketa_id=%s rows=%s", tg_id, getattr(ank, 'id', None), count)
                return ank
        except Exception:
            logger.exception("DBService: failed to save_to_anketa_schema for tg_id=%s", tg_id)
            raise
