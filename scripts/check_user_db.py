import os
import psycopg2

def main():
    pw = os.getenv('PGPASSWORD') or os.getenv('DB_PASSWORD')
    if not pw:
        pw = input("Postgres password for user 'postgres': ")
    conn = psycopg2.connect(dbname='city_for_all', user='postgres', password=pw, host='localhost')
    cur = conn.cursor()
    userid = 793442943
    cur.execute('SELECT id, user_id, username FROM "Персона" WHERE user_id=%s', (userid,))
    person = cur.fetchone()
    print('person row:', person)
    if person:
        pid = person[0]
        cur.execute('SELECT count(*) FROM "Анкета" WHERE person_id=%s', (pid,))
        print('anketa rows for person id', pid, ':', cur.fetchone()[0])
        cur.execute('SELECT id, question_id, group_id FROM "Анкета" WHERE person_id=%s ORDER BY id', (pid,))
        rows = cur.fetchall()
        for r in rows:
            print('anketa:', r)
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
