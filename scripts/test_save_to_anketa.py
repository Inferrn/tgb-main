import asyncio
import sys
from pathlib import Path

# Ensure project root (tg_bot) is on sys.path so this script can be run as a file
# and still import the `app` package. When running as a module (python -m ...) this
# is not necessary, but it's convenient for direct execution in PowerShell.
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.services.db_service import DBService
from app.database.models import async_session, Persona, Anketa, AnketaAnswer
from sqlalchemy import select

async def main():
    db = DBService()
    answers = {
        "modul_1:1": "25-34",
        "modul_1:3": ["A", "B"],
        "modul_3:1": "Ежемесячная подписка"
    }
    import time, random
    # Use tg_id within signed 32-bit range to avoid DB integer overflow
    tg_id = random.randint(10**8, 2_000_000_000)
    print('Using tg_id for test:', tg_id)
    try:
        ank = await db.save_to_anketa_schema(tg_id, answers, username="test_user")
        print('Saved anketa id:', getattr(ank, 'id', None))
    except Exception as e:
        print('Save failed:', repr(e))

    # --- Вывод содержимого таблиц Персона, Анкета, Анкета_ответ для подтверждения ---
    from sqlalchemy import text
    async with async_session() as session:
        # Personas (ORM mapping exists)
        try:
            res = await session.execute(select(Persona))
            personas = res.scalars().all()
            print('\n--- Персона ---')
            for p in personas:
                print('id=', getattr(p, 'id', None), 'User_id=', getattr(p, 'user_id', None), 'Username=', getattr(p, 'username', None))
        except Exception as e:
            print('Could not read Персона via ORM:', repr(e))

        # Анкета — в старой схеме может не быть столбца person_id, поэтому используем сырой SQL
        try:
            res = await session.execute(text('SELECT * FROM "Анкета"'))
            rows = res.fetchall()
            print('\n--- Анкета (raw) ---')
            for r in rows:
                print(dict(r._mapping))
        except Exception as e:
            print('Could not read Анкета via raw SQL:', repr(e))

        # Анкета_ответ — тоже безопасно читать как сырой SQL
        try:
            res = await session.execute(text('SELECT * FROM "Анкета_ответ"'))
            rows = res.fetchall()
            print('\n--- Анкета_ответ (raw) ---')
            for r in rows:
                print(dict(r._mapping))
        except Exception as e:
            print('Could not read Анкета_ответ via raw SQL:', repr(e))

if __name__ == '__main__':
    asyncio.run(main())
