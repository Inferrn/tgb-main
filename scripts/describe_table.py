import os
import psycopg2

def main():
    pw = os.getenv('PGPASSWORD') or os.getenv('DB_PASSWORD')
    if not pw:
        pw = input("Postgres password for user 'postgres': ")
    conn = psycopg2.connect(dbname='city_for_all', user='postgres', password=pw, host='localhost')
    cur = conn.cursor()
    cur.execute("SELECT column_name, data_type, is_nullable FROM information_schema.columns WHERE table_name=%s ORDER BY ordinal_position", ('Анкета',))
    rows = cur.fetchall()
    print('columns for table Анкета:')
    for r in rows:
        print(r)
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
