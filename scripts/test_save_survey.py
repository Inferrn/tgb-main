import asyncio
from pathlib import Path
import sys

# Ensure project root on sys.path for direct execution
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.services.db_service import DBService


async def main():
    db = DBService()
    data = {"mod1:1": "Да", "mod1:2": ["Вариант A", "Вариант B"], "mod2:5": "Комментарий"}
    ank = await db.save_to_anketa_schema(123456789, data, username='test_user')
    print('Saved anketa id:', getattr(ank, 'id', None))


if __name__ == '__main__':
    asyncio.run(main())
