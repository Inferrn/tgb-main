import asyncio
import logging
import sys
from pathlib import Path

# Ensure tg_bot is on sys.path so `import app` works when script is run from repo root
PROJECT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_DIR))

from app.services.db_service import DBService


logging.basicConfig(level=logging.INFO)

# Результаты опроса, скопированные из логов для user=793442943
ANSWERS = {
    'modul_1:1': '18-34',
    'modul_1:2': 'Мужской',
    'modul_1:3': ['Октябрьский', 'Советский'],
    'modul_1:4': ['Проблемы со слухом'],
    'modul_1:5': ['Возможность быстро поделиться местоположением'],
    'modul_1:6': ['Указать местоположение на карте и описать проблему'],
    'modul_1:7': 'Иногда',
    'modul_1:8': ['Готов примкнуть к волонтёрам для массового сбора информации о дорожных объектах города'],
    'modul_2:1': 'Да',
    'modul_2:2': 'Да',
    'modul_2:3:level_0': '4 - сложно',
    'modul_2:3:level_1': '4 - сложно',
    'modul_2:3:level_2': '4 - сложно',
    'modul_2:3:level_3': '4 - сложно',
    'modul_2:4': 'Да',
    'modul_2:5': 'Да',
    'modul_2:6': 'Да',
    'modul_2:7:level_0': '4 - сложно',
    'modul_2:7:level_1': '4 - сложно',
    'modul_2:7:level_2': '4 - сложно',
    'modul_2:7:level_3': '4 - сложно',
    'modul_2:7:level_4': '4 - сложно',
    'modul_2:7:level_5': '4 - сложно',
    'modul_2:8': 'Да',
    'modul_2:9': 'Да',
    'modul_2:10': '7-10 секунд',
    'modul_2:11': 'Да',
    'modul_2:12': 'Да',
    'modul_2:13': 'Да',
    'modul_2:14': 'Да',
    'modul_2:15': 'Нет',
    'modul_2:16': 'Да',
    'modul_2:17': 'Да',
    'modul_2:18': 'Да',
    'modul_2:19': 'Да',
    'modul_2:20': 'Да',
    'modul_2:21:level_0': '4 - сложно',
    'modul_2:21:level_1': '4 - сложно',
    'modul_2:21:level_2': '4 - сложно',
    'modul_2:21:level_3': '4 - сложно',
    'modul_2:22': 'Да',
    'modul_2:23': 'Да',
    'modul_2:24': 'Да',
    'modul_2:25': 'Да, если есть тротуар',
    'modul_2:26': 'Да',
    'modul_2:27:level_0': '4 - сложно',
    'modul_2:27:level_1': '4 - сложно',
    'modul_2:27:level_2': '4 - сложно',
    'modul_2:27:level_3': '4 - сложно',
    'modul_2:27:level_4': '4 - сложно',
    'modul_2:27:level_5': '4 - сложно',
    'modul_2:28:level_0': '4 - сложно',
    'modul_2:28:level_1': '4 - сложно',
    'modul_2:28:level_2': '4 - сложно',
    'modul_2:28:level_3': '4 - сложно',
    'modul_2:28:level_4': '4 - сложно',
    'modul_2:28:level_5': '4 - сложно',
    'modul_2:28:level_6': '4 - сложно',
    'modul_2:28:level_7': '4 - сложно',
    'modul_3:1': 'Единоразовый платеж за безграничный доступ (например, 3000 ₽)'
}


async def main():
    # Normalize keys like 'modul_2:3:level_0' -> 'modul_2:3' and group multiple entries per question
    import re

    normalized = {}
    for k, v in ANSWERS.items():
        m = re.match(r'^(.*?):(\d+)(?:[:].*)?$', k)
        if m:
            base = f"{m.group(1)}:{m.group(2)}"
        else:
            base = k

        # merge values: if multiple entries for same base question, collect into list
        if base in normalized:
            existing = normalized[base]
            if isinstance(existing, list):
                if isinstance(v, list):
                    existing.extend(v)
                else:
                    existing.append(v)
            else:
                # convert to list
                normalized[base] = [existing] + (v if isinstance(v, list) else [v])
        else:
            normalized[base] = v

    svc = DBService()
    tg_id = 793442943
    logging.info("Resave: starting save_to_anketa_schema for tg_id=%s", tg_id)
    try:
        ank = await svc.save_to_anketa_schema(tg_id, normalized, username='restored_by_script')
        logging.info("Resave: finished. anketa id=%s", getattr(ank, 'id', None))
        print('OK', getattr(ank, 'id', None))
    except Exception as e:
        logging.exception("Resave: failed to save: %s", e)
        print('ERROR', e)


if __name__ == '__main__':
    asyncio.run(main())
