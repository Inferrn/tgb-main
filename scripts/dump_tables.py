import os
import psycopg2
import psycopg2.extras

TABLES = [
    'Персона',
    'Анкета',
    'Анкета_ответ',
    'Вопрос',
    'Ответ',
    'Вопрос_ответ',
    'Группа_ответов'
]


def describe_table(cur, table):
    cur.execute("SELECT column_name, data_type, is_nullable FROM information_schema.columns WHERE table_name=%s ORDER BY ordinal_position", (table,))
    cols = cur.fetchall()
    return cols


def count_rows(cur, table):
    cur.execute(f'SELECT count(*) FROM "{table}"')
    return cur.fetchone()[0]


def null_counts(cur, table, cols):
    results = {}
    for col in cols:
        cname = col[0]
        try:
            cur.execute(f'SELECT count(*) FROM "{table}" WHERE "{cname}" IS NULL')
            results[cname] = cur.fetchone()[0]
        except Exception as e:
            results[cname] = f'ERR: {e}'
    return results


def sample_rows(cur, table, cols, limit=20):
    col_names = ', '.join([f'"{c[0]}"' for c in cols]) if cols else '*'
    try:
        cur.execute(f'SELECT {col_names} FROM "{table}" ORDER BY 1 LIMIT %s', (limit,))
        rows = cur.fetchall()
        return rows
    except Exception as e:
        return f'ERR: {e}'


def main():
    pw = os.getenv('PGPASSWORD') or os.getenv('DB_PASSWORD')
    if not pw:
        pw = input("Postgres password for user 'postgres': ")
    conn = psycopg2.connect(dbname='city_for_all', user='postgres', password=pw, host='localhost')
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

    for t in TABLES:
        print('\n' + '='*80)
        print(f'TABLE: {t}')
        try:
            cols = describe_table(cur, t)
        except Exception as e:
            print('  ERROR: could not describe table:', e)
            continue
        print('  Columns:')
        for c in cols:
            print('   -', c[0], '|', c[1], '|', 'nullable=' + c[2])
        try:
            total = count_rows(cur, t)
            print('  Total rows:', total)
        except Exception as e:
            print('  ERROR counting rows:', e)

        print('  Null counts per column:')
        nc = null_counts(cur, t, cols)
        for k, v in nc.items():
            print(f'   - {k}: {v}')

        print('\n  Sample rows (first 20):')
        s = sample_rows(cur, t, cols, limit=20)
        if isinstance(s, str) and s.startswith('ERR:'):
            print('   ERROR fetching sample:', s)
        else:
            for r in s:
                # pretty print dict-like row
                print('   -', dict(r))

    cur.close()
    conn.close()


if __name__ == '__main__':
    main()
