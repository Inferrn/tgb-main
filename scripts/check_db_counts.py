import os
import psycopg2

def main():
    pw = os.getenv('PGPASSWORD') or os.getenv('DB_PASSWORD')
    if not pw:
        pw = input("Postgres password for user 'postgres': ")
    conn = psycopg2.connect(dbname='city_for_all', user='postgres', password=pw, host='localhost')
    cur = conn.cursor()

    queries = [
        ('questions', 'SELECT count(*) FROM "Вопрос"'),
        ('answers', 'SELECT count(*) FROM "Ответ"'),
        ('vopros_otvet', 'SELECT count(*) FROM "Вопрос_ответ"'),
        ('group_answers', 'SELECT count(*) FROM "Группа_ответов"'),
        ('modules', 'SELECT count(*) FROM "Модуль"'),
    ]

    for name, q in queries:
        cur.execute(q)
        print(f"{name}:", cur.fetchone()[0])

    print('\nFirst 12 questions:')
    cur.execute('SELECT id, text FROM "Вопрос" ORDER BY id LIMIT 12')
    for r in cur.fetchall():
        txt = r[1] or ''
        if len(txt) > 120:
            txt = txt[:117] + '...'
        print(r[0], ':', txt)

    print('\nSample answers (first 12):')
    cur.execute('SELECT id, text FROM "Ответ" ORDER BY id LIMIT 12')
    for r in cur.fetchall():
        print(r)

    print('\nSample group->answer (first 12):')
    cur.execute('SELECT id, group_id, answer_id FROM "Группа_ответов" ORDER BY id LIMIT 12')
    for r in cur.fetchall():
        print(r)

    print('\nSample question->group (first 12):')
    cur.execute('SELECT id, question_id, group_id FROM "Вопрос_ответ" ORDER BY id LIMIT 12')
    for r in cur.fetchall():
        print(r)

    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
