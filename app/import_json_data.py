import json
import psycopg2
import os
import getpass

# Настройки подключения
DBNAME = os.getenv("DBNAME", "city_for_all")
USER = os.getenv("PGUSER", "postgres")
PASSWORD = os.getenv("PGPASSWORD") or os.getenv("DB_PASSWORD")
HOST = os.getenv("PGHOST", "localhost")
PORT = os.getenv("PGPORT", "5432")


def import_json_data(json_file: str = None):
    """Импортирует JSON опроса в базу, создавая модули, вопросы и ответы.

    Если json_file не указан, используется `app/data/ovz.json`.
    """
    if json_file is None:
        json_file = os.path.join(os.path.dirname(__file__), 'data', 'ovz.json')

    try:
        # Подключение
        print("Подключение к базе данных...")
        pw = PASSWORD
        if not pw:
            try:
                pw = getpass.getpass(prompt=f"Postgres password for user '{USER}': ")
            except Exception:
                pw = ''

        conn = psycopg2.connect(dbname=DBNAME, user=USER, password=pw, host=HOST, port=PORT)
        cur = conn.cursor()
        print("✅ Подключение успешно!")

        # Чтение JSON файла
        print(f"Чтение {json_file}...")
        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        print("✅ JSON файл прочитан")

        # Очистка таблиц перед импортом
        print("Очистка таблиц...")
        for table in ["Группа_ответов", "Вопрос_ответ", "Ответ", "Вопрос", "Модуль"]:
            cur.execute(f'TRUNCATE TABLE "{table}" RESTART IDENTITY CASCADE')

        # Счетчики для статистики
        question_count = 0
        answer_count = 0
        question_answer_count = 0
        group_answers_count = 0

        # Подготовка мэппинга старых id -> новых (мы будем явно задавать id для вопросов)
        question_id_mapping = {}
        all_questions = []
        for module_name, questions in data.items():
            if module_name == 'options_scale':
                continue
            for q in questions:
                all_questions.append((module_name, q))

        new_question_id = 1
        for module_name, q in all_questions:
            question_id_mapping[(module_name, q['id'])] = new_question_id
            new_question_id += 1

        # Импорт шкалы оценок (если есть)
        options_scale = data.get('options_scale', [])
        scale_answer_ids = {}
        if options_scale:
            print("📊 Импорт шкалы оценок...")
            for opt in options_scale:
                cur.execute('INSERT INTO "Ответ" (text) VALUES (%s) RETURNING id', (opt,))
                scale_answer_ids[opt] = cur.fetchone()[0]
                answer_count += 1

        # Вставляем модули и вопросы
        for module_name, questions in data.items():
            if module_name == 'options_scale':
                continue

            # создаём модуль
            cur.execute('INSERT INTO "Модуль" (name) VALUES (%s) RETURNING id', (module_name,))
            module_id = cur.fetchone()[0]
            print(f"\n📋 Импорт вопросов для модуля: {module_name}")

            for q in questions:
                old_id = q['id']
                new_id = question_id_mapping[(module_name, old_id)]
                question_text = q.get('text')
                question_type = q.get('type')
                image = q.get('image')

                # Обработка условий (переводим ссылки на новые id)
                condition_text = None
                if 'if' in q:
                    parts = []
                    for key, value in q['if'].items():
                        target_old_id = value.get('id')
                        target_new_id = next((nid for (mod, oid), nid in question_id_mapping.items() if oid == target_old_id), None)
                        if target_new_id:
                            parts.append(f"{key}:{target_new_id}")
                    condition_text = ";".join(parts) if parts else None

                # Вставляем вопрос с явным id, чтобы сохранить соответствие с JSON
                cur.execute("""
                    INSERT INTO "Вопрос" (id, pid, module_id, text, type, pic, condition, image)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """, (new_id, q.get('pid'), module_id, question_text, question_type, bool(image), condition_text, image))
                question_count += 1
                print(f"   ✅ Вопрос {new_id} (старый {old_id}): {str(question_text)[:40]}...")

                # Вставка вариантов ответов: сначала создаём ответы и записи в Группа_ответов
                # затем создаём запись Вопрос_ответ, которая ссылается на одну из строк группы (представитель)
                if 'options' in q:
                    representative_group_row_id = None
                    for option_text in q['options']:
                        cur.execute('INSERT INTO "Ответ" (text) VALUES (%s) RETURNING id', (option_text,))
                        answer_id = cur.fetchone()[0]
                        answer_count += 1
                        # group_id column stores logical group identifier (use question id)
                        cur.execute('INSERT INTO "Группа_ответов" (group_id, answer_id) VALUES (%s, %s) RETURNING id', (new_id, answer_id))
                        grp_row_id = cur.fetchone()[0]
                        group_answers_count += 1
                        if representative_group_row_id is None:
                            representative_group_row_id = grp_row_id
                    # Теперь создаём связь Вопрос_ответ, указывая representative_group_row_id
                    if representative_group_row_id is not None:
                        cur.execute('INSERT INTO "Вопрос_ответ" (question_id, group_id) VALUES (%s, %s) RETURNING id', (new_id, representative_group_row_id))
                        _ = cur.fetchone()[0]
                        question_answer_count += 1

                # Уровни (scale-style)
                if 'levels' in q:
                    representative_levels_group_row_id = None
                    for level in q['levels']:
                        level_text_parts = [f"{k}: {v}" for k, v in level.items() if k != 'options']
                        level_text = " | ".join(level_text_parts)
                        for scale_option in options_scale:
                            full_level_text = f"{level_text} - {scale_option}"
                            cur.execute('INSERT INTO "Ответ" (text) VALUES (%s) RETURNING id', (full_level_text,))
                            answer_id = cur.fetchone()[0]
                            answer_count += 1
                            # group_id for levels use new_id + 1000 as logical group identifier
                            cur.execute('INSERT INTO "Группа_ответов" (group_id, answer_id) VALUES (%s, %s) RETURNING id', (new_id + 1000, answer_id))
                            grp_row_id = cur.fetchone()[0]
                            group_answers_count += 1
                            if representative_levels_group_row_id is None:
                                representative_levels_group_row_id = grp_row_id
                    if representative_levels_group_row_id is not None:
                        cur.execute('INSERT INTO "Вопрос_ответ" (question_id, group_id) VALUES (%s, %s) RETURNING id', (new_id, representative_levels_group_row_id))
                        _ = cur.fetchone()[0]
                        question_answer_count += 1

        conn.commit()

        # Статистика
        print(f"\n🎉 ИМПОРТ ЗАВЕРШЕН!")
        print(f"📊 Вопросов: {question_count}")
        print(f"📊 Ответов: {answer_count}")
        print(f"📊 Связей вопрос-ответ: {question_answer_count}")
        print(f"📊 Связей группа-ответов: {group_answers_count}")

        cur.close()
        conn.close()

    except Exception as e:
        print(f"❌ Ошибка импорта: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    import_json_data()
