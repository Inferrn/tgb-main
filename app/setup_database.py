import os
import psycopg2
from psycopg2 import sql
import getpass

# Настройки подключения
DBNAME = "city_for_all"
USER = os.getenv("PGUSER", "postgres")
# read password from env or fallback to DB_PASSWORD; if missing prompt interactively
PASSWORD = os.getenv("PGPASSWORD") or os.getenv("DB_PASSWORD")
HOST = os.getenv("PGHOST", "localhost")
PORT = os.getenv("PGPORT", "5432")

def setup_database():
    try:
        print("Подключение к базе данных...")
        pw = PASSWORD
        if not pw:
            try:
                pw = getpass.getpass(prompt=f"Postgres password for user '{USER}': ")
            except Exception:
                pw = ''

        conn = psycopg2.connect(dbname=DBNAME, user=USER, password=pw, host=HOST, port=PORT)
        conn.autocommit = True
        cur = conn.cursor()
        print("✅ Подключение успешно!")

        sql_commands = [
            # Удаление таблиц, если существуют
            'DROP TABLE IF EXISTS "Группа_ответов" CASCADE',
            'DROP TABLE IF EXISTS "Вопрос_ответ" CASCADE',
            'DROP TABLE IF EXISTS "Ответ" CASCADE',
            'DROP TABLE IF EXISTS "Вопрос" CASCADE',
            'DROP TABLE IF EXISTS "Модуль" CASCADE',
            'DROP TABLE IF EXISTS "Анкета" CASCADE',
            'DROP TABLE IF EXISTS "Персона" CASCADE',

            # Таблица пользователей
            '''
            CREATE TABLE "Персона" (
                "id" SERIAL PRIMARY KEY,
                "user_id" INTEGER NOT NULL,
                "username" TEXT NOT NULL
            )
            ''',

            # Таблица модулей (модуль 1, модуль 2, модуль 3)
            '''
            CREATE TABLE "Модуль" (
                "id" SERIAL PRIMARY KEY,
                "name" TEXT NOT NULL,
                "description" TEXT
            )
            ''',

            # Таблица вопросов
            '''
            CREATE TABLE "Вопрос" (
                "id" SERIAL PRIMARY KEY,
                "pid" INTEGER,
                "module_id" INTEGER,
                "text" TEXT NOT NULL,
                "type" TEXT NOT NULL,
                "pic" BOOLEAN DEFAULT FALSE,
                "condition" TEXT,
                "image" TEXT,
                CONSTRAINT fk_module FOREIGN KEY ("module_id") REFERENCES "Модуль" ("id"),
                CONSTRAINT fk_parent_question FOREIGN KEY ("pid") REFERENCES "Вопрос" ("id")
            )
            ''',

            # Таблица ответов
            '''
            CREATE TABLE "Ответ" (
                "id" SERIAL PRIMARY KEY,
                "text" TEXT NOT NULL
            )
            ''',

            # Таблица групп ответов
            '''
            CREATE TABLE "Группа_ответов" (
                "id" SERIAL PRIMARY KEY,
                "group_id" INTEGER NOT NULL,
                "answer_id" INTEGER NOT NULL,
                CONSTRAINT fk_answer FOREIGN KEY ("answer_id") REFERENCES "Ответ" ("id")
            )
            ''',

            # Связь между вопросом и группой ответов
            '''
            CREATE TABLE "Вопрос_ответ" (
                "id" SERIAL PRIMARY KEY,
                "question_id" INTEGER NOT NULL,
                "group_id" INTEGER NOT NULL,
                CONSTRAINT fk_question FOREIGN KEY ("question_id") REFERENCES "Вопрос" ("id"),
                CONSTRAINT fk_group FOREIGN KEY ("group_id") REFERENCES "Группа_ответов" ("id")
            )
            ''',

            # Таблица анкет (заполненные пользователями опросы)
            '''
            CREATE TABLE "Анкета" (
                "id" SERIAL PRIMARY KEY,
                "person_id" INTEGER NOT NULL,
                "question_id" INTEGER,
                "group_id" INTEGER,
                CONSTRAINT fk_person FOREIGN KEY ("person_id") REFERENCES "Персона" ("id"),
                CONSTRAINT fk_question_link FOREIGN KEY ("question_id") REFERENCES "Вопрос" ("id")
            )
            ''',

            # Индексы
            'CREATE INDEX idx_question_id ON "Вопрос_ответ" ("question_id")',
            'CREATE INDEX idx_group_id ON "Вопрос_ответ" ("group_id")',
            'CREATE INDEX idx_answer_id ON "Группа_ответов" ("answer_id")'
        ]

        print("Создание структуры базы данных...")
        for i, sql in enumerate(sql_commands, 1):
            try:
                cur.execute(sql)
                print(f"✅ Команда {i} выполнена")
            except Exception as e:
                print(f"⚠️ Ошибка при выполнении команды {i}: {e}")

        cur.close()
        conn.close()
        print("\n🎉 Структура базы данных успешно создана!")

    except Exception as e:
        print(f"❌ Ошибка: {e}")

if __name__ == "__main__":
    setup_database()
