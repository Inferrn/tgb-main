import asyncio
import json
import os
import random
from pathlib import Path
import sys

# Ensure project root is importable
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.services.db_service import DBService
from app.database.models import async_session, Persona
from sqlalchemy import select, text

OUT_DIR = Path(__file__).resolve().parent / 'out'

async def run_collection(runs: int = 5, outdir: Path = OUT_DIR):
    outdir.mkdir(parents=True, exist_ok=True)
    db = DBService()
    results = []

    for i in range(runs):
        # use safe 32-bit signed integer for tg_id
        tg_id = random.randint(10**8, 2_000_000_000)
        answers = {
            "modul_1:1": f"age_group_{i}",
            "modul_1:3": ["A", "B"],
            "modul_3:1": "opt"
        }
        try:
            ank = await db.save_to_anketa_schema(tg_id, answers, username=f"test_user_{i}")
            results.append({"index": i, "tg_id": tg_id, "anketa_id": getattr(ank, 'id', None), "status": "ok"})
            print(f"Saved {i+1}/{runs}: tg_id={tg_id} anketa_id={getattr(ank,'id',None)}")
        except Exception as e:
            results.append({"index": i, "tg_id": tg_id, "anketa_id": None, "status": "error", "error": repr(e)})
            print(f"Save failed for tg_id={tg_id}: {e}")

    # Dump tables
    dump = {"runs": results}
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

    out_file = outdir / 'dump.json'
    with open(out_file, 'w', encoding='utf-8') as f:
        json.dump(dump, f, ensure_ascii=False, indent=2, default=str)

    print('\nDump written to', out_file)
    return out_file

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--runs', '-n', type=int, default=5, help='Number of test inserts to perform')
    args = parser.parse_args()
    asyncio.run(run_collection(runs=args.runs))
