from app.database.models import async_session, Persona
from sqlalchemy import select


async def set_user(tg_id: int, username: str = ''):
    """Ensure a Persona row exists for given tg_id (creates if missing).

    This replaces the old `users` table usage and maps Telegram user id -> Persona.User_id.
    """
    async with async_session() as session:
        person = await session.scalar(select(Persona).where(Persona.user_id == tg_id))
        if not person:
            session.add(Persona(user_id=tg_id, username=(username or '')))
            await session.commit()
            return True
    return False