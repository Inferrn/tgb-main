import os
from sqlalchemy import String, ForeignKey, DateTime, Text, func, Integer
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
import datetime
from sqlalchemy.ext.asyncio import AsyncAttrs, async_sessionmaker, create_async_engine

# Поддержка нескольких бэкендов: если в окружении задана переменная DATABASE_URL —
# используем её (например, postgresql+asyncpg://user:pass@host:port/dbname),
# иначе падаем на sqlite локально (sqlite+aiosqlite:///db.sqlite3).
DATABASE_URL = os.getenv('DATABASE_URL')
if DATABASE_URL:
    engine = create_async_engine(DATABASE_URL, future=True)
else:
    engine = create_async_engine('sqlite+aiosqlite:///db.sqlite3', future=True)

async_session = async_sessionmaker(engine, expire_on_commit=False)


class Base(AsyncAttrs, DeclarativeBase):
    pass




# --- Модели для существующей русской схемы (setup_database.py) ---
class Persona(Base):
    __tablename__ = 'Персона'
    # В SQL-скрипте столбцы созданы с кавычками и смешанным регистром: "User_id", "Username".
    # PostgreSQL рассматривает такие имена как case-sensitive, поэтому здесь явно указываем
    # имена колонок, соответствующие существующей структуре БД.
    id: Mapped[int] = mapped_column(primary_key=True)
    # в setup_database.py поля называются 'user_id' и 'username' (lowercase)
    user_id: Mapped[int] = mapped_column("user_id", Integer)
    username: Mapped[str] = mapped_column("username", Text)


class Anketa(Base):
    __tablename__ = 'Анкета'

    id: Mapped[int] = mapped_column(primary_key=True)
    # legacy schemas vary: some have person_id FK, some map Анкета.id == Персона.id
    # map person_id if present
    person_id: Mapped[int] = mapped_column("person_id", ForeignKey('Персона.id'), nullable=True)
    # required by legacy layout: id_q column (first question id for the anketa)
    id_q: Mapped[int] = mapped_column("id_q", Integer, nullable=False, default=0)
    # group id (may be named group_id)
    group_id: Mapped[int] = mapped_column("group_id", Integer, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, server_default=func.now())


class AnketaAnswer(Base):
    __tablename__ = 'Анкета_ответ'

    id: Mapped[int] = mapped_column(primary_key=True)
    anketa_id: Mapped[int] = mapped_column(ForeignKey('Анкета.id'))
    question_id: Mapped[int] = mapped_column(Integer)
    answer_id: Mapped[int] = mapped_column(Integer, nullable=True)
    answer_text: Mapped[str] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, server_default=func.now())


class Vopros(Base):
    __tablename__ = 'Вопрос'
    id: Mapped[int] = mapped_column(primary_key=True)
    # pid corresponds to parent question id column 'pid'
    pid: Mapped[int] = mapped_column("pid", Integer, nullable=True)
    # module_id is FK to Модуль.id (created by setup_database.py)
    module_id: Mapped[int] = mapped_column("module_id", Integer, nullable=True)
    text: Mapped[str] = mapped_column("text", Text)
    type: Mapped[str] = mapped_column("type", String(50))
    pic: Mapped[bool] = mapped_column("pic", default=False)
    condition: Mapped[str] = mapped_column("condition", Text, nullable=True)
    image: Mapped[str] = mapped_column("image", String(255), nullable=True)


class Otvet(Base):
    __tablename__ = 'Ответ'

    id: Mapped[int] = mapped_column(primary_key=True)
    text: Mapped[str] = mapped_column(Text)


class VoprosOtvet(Base):
    __tablename__ = 'Вопрос_ответ'

    id: Mapped[int] = mapped_column(primary_key=True)
    question_id: Mapped[int] = mapped_column(Integer)
    group_id: Mapped[int] = mapped_column(Integer)


class GroupAnswers(Base):
    __tablename__ = 'Группа_ответов'

    id: Mapped[int] = mapped_column(primary_key=True)
    group_id: Mapped[int] = mapped_column(Integer)
    answer_id: Mapped[int] = mapped_column(Integer)
