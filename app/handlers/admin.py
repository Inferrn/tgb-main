from aiogram import Router
from aiogram.types import Message, FSInputFile
from aiogram.filters import Command
import json
import tempfile
from pathlib import Path
import os
import html

from app.database.models import async_session, Persona, Anketa, AnketaAnswer
from sqlalchemy import select, text

router = Router()


def _get_admin_ids():
    """Read ADMIN_IDS from env (comma-separated). Returns set of ints."""
    raw = os.getenv('ADMIN_IDS', '')
    ids = set()
    for part in [p.strip() for p in raw.split(',') if p.strip()]:
        try:
            ids.add(int(part))
        except Exception:
            continue
    return ids


@router.message(Command('export_data'))
async def cmd_export_data(message: Message):
    admin_ids = _get_admin_ids()
    if not admin_ids:
        await message.reply("Export disabled: ADMIN_IDS not configured.")
        return

    if message.from_user is None or message.from_user.id not in admin_ids:
        await message.reply("У вас нет прав для этой команды.")
        return

    await message.reply("Готовлю экспорт данных — подождите...")

    dump = {}
    async with async_session() as session:
        try:
            res = await session.execute(select(Persona))
            dump['persona'] = [{"id": p.id, "user_id": p.user_id, "username": p.username} for p in res.scalars().all()]
        except Exception as e:
            dump['persona_error'] = repr(e)

        try:
            res = await session.execute(text('SELECT * FROM "Анкета"'))
            dump['anketa'] = [dict(r._mapping) for r in res.fetchall()]
        except Exception as e:
            dump['anketa_error'] = repr(e)

        try:
            res = await session.execute(text('SELECT * FROM "Анкета_ответ"'))
            dump['anketa_answers'] = [dict(r._mapping) for r in res.fetchall()]
        except Exception as e:
            dump['anketa_answers_error'] = repr(e)

    # Write to temp file and send
    tmp_dir = Path(tempfile.gettempdir())
    from datetime import datetime
    # human-readable timestamp; colons are not allowed in Windows filenames, replace with hyphens
    ts_display = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
    ts_file = datetime.utcnow().strftime('%Y-%m-%d %H-%M-%S')
    # Use timestamp-only filename (colons replaced by hyphens for filesystem safety)
    tmp_path = tmp_dir / f"{ts_file}.json"
    # include exported_at in JSON using human-readable timestamp
    dump['exported_at'] = ts_display
    # Use default=str to ensure datetime and other non-JSON types are serialized
    tmp_path.write_text(json.dumps(dump, ensure_ascii=False, indent=2, default=str), encoding='utf-8')

    try:
        await message.answer_document(FSInputFile(str(tmp_path)), caption='Экспорт данных (json)')
    finally:
        try:
            tmp_path.unlink(missing_ok=True)
        except Exception:
            pass


@router.message(Command('check_user'))
async def cmd_check_user(message: Message):
    """Admin helper: /check_user <tg_id> — show Persona and Anketa rows for the tg_id"""
    admin_ids = _get_admin_ids()
    if not admin_ids or message.from_user is None or message.from_user.id not in admin_ids:
        await message.reply("Нет прав")
        return

    parts = (message.text or '').split()
    if len(parts) < 2:
        await message.reply("Использование: /check_user <tg_id>")
        return

    try:
        tg_id = int(parts[1])
    except Exception:
        await message.reply("tg_id должен быть целым числом")
        return

    async with async_session() as session:
        try:
            res = await session.execute(select(Persona).where(Persona.user_id == tg_id))
            persona = res.scalar_one_or_none()
        except Exception as e:
            await message.reply(f"Ошибка при поиске Персона: {html.escape(str(e))}")
            return

        if not persona:
            await message.reply(f"Персона с tg_id={tg_id} не найдена в таблице Персона")
            return

        # find анкеты for this persona id ( Анкета.id may match persona.id in legacy schema )
        try:
            pid = getattr(persona, 'id', None)
            anketas = []
            # always try by id
            try:
                res = await session.execute(text('SELECT * FROM "Анкета" WHERE "id" = :pid'), {'pid': pid})
                anketas.extend([dict(r._mapping) for r in res.fetchall()])
            except Exception:
                # ignore errors for id-based query (shouldn't normally happen)
                pass

            # try by person_id if that column exists (may raise if column missing) — ignore if not present
            try:
                res = await session.execute(text('SELECT * FROM "Анкета" WHERE "person_id" = :pid'), {'pid': pid})
                anketas.extend([dict(r._mapping) for r in res.fetchall()])
            except Exception:
                # column may not exist in legacy schema; that's fine — we already have id-based results
                pass

            # dedupe by anketa id (in case both queries returned same row)
            seen = set()
            deduped = []
            for a in anketas:
                aid = a.get('id')
                if aid in seen:
                    continue
                seen.add(aid)
                deduped.append(a)
            anketas = deduped
        except Exception as e:
            await message.reply(f"Ошибка при чтении Анкета: {html.escape(str(e))}")
            return

        reply_lines = [f"Персона id={persona.id} user_id={persona.user_id} username={persona.username}", f"Анкета найдено: {len(anketas)}"]
        for a in anketas:
            reply_lines.append(str(a))

        await message.reply('\n'.join(reply_lines[:50]))
