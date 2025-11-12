import os
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine


async def main():
    # Try to get full DATABASE_URL first
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
            if url.startswith('sqlite'):
                res = await conn.exec_driver_sql("SELECT name FROM sqlite_master WHERE type='table';")
                rows = await res.fetchall()
                print('sqlite tables:', rows)
            else:
                res = await conn.exec_driver_sql("SELECT tablename FROM pg_catalog.pg_tables WHERE schemaname='public';")
                rows = res.all()  # просто вызываем .all(), без await
                print('postgres tables:', rows)
    except Exception as e:
        print('Error connecting or querying:', repr(e))
    finally:
        await engine.dispose()


if __name__ == '__main__':
    asyncio.run(main())
