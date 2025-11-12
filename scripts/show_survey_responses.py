import os
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine


async def main():
    url = os.getenv('DATABASE_URL')
    if not url:
        user = os.getenv('PGUSER', 'postgres')
        pwd = 'PGPASSWORD'
        host = os.getenv('PGHOST', 'localhost')
        port = os.getenv('PGPORT', '5432')
        db = os.getenv('DBNAME', 'city_for_all')
        if pwd:
            url = f'postgresql+asyncpg://{user}:{pwd}@{host}:{port}/{db}'
        else:
            url = f'postgresql+asyncpg://{user}@{host}:{port}/{db}'

    print('Using DATABASE_URL:', url)
    engine = create_async_engine(url, future=True)
    try:
        async with engine.connect() as conn:
            # Show recent Анкета runs from the Russian schema and count answers per anketa
            sql = '''
            SELECT a."id", a."id_q", a."group_id",
                   (SELECT count(*) FROM "Анкета_ответ" ar WHERE ar."anketa_id" = a."id") as answers_count
            FROM "Анкета" a
            ORDER BY a."id" DESC
            LIMIT 20
            '''
            res = await conn.exec_driver_sql(sql)
            rows = res.fetchall()
            if not rows:
                print('No Анкета rows found')
            else:
                for r in rows:
                    print(r)
    except Exception as e:
        print('Error querying Анкета:', repr(e))
    finally:
        await engine.dispose()

if __name__ == '__main__':
    asyncio.run(main())
