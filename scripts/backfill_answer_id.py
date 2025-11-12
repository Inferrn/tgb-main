import os
import psycopg2
import psycopg2.extras


def main():
    pw = os.getenv('PGPASSWORD') or os.getenv('DB_PASSWORD')
    if not pw:
        pw = input("Postgres password for user 'postgres': ")
    conn = psycopg2.connect(dbname='city_for_all', user='postgres', password=pw, host='localhost')
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

    # Count rows with NULL answer_id
    cur.execute('SELECT count(*) FROM "Анкета_ответ" WHERE "answer_id" IS NULL')
    null_count = cur.fetchone()[0]
    print('Анкета_ответ rows with NULL answer_id:', null_count)

    # Find distinct answer_text values among those rows
    cur.execute('SELECT "answer_text", count(*) as cnt FROM "Анкета_ответ" WHERE "answer_id" IS NULL GROUP BY "answer_text" ORDER BY cnt DESC LIMIT 50')
    samples = cur.fetchall()
    print('\nTop 50 distinct answer_text (NULL answer_id):')
    for r in samples:
        print(' -', r['cnt'], 'x', repr(r['answer_text'])[:200])

    # For preview, attempt to match distinct texts to Ответ
    cur.execute('SELECT id, text FROM "Ответ"')
    ans_map = {r['text']: r['id'] for r in cur.fetchall()}

    matches = []
    for r in samples:
        txt = r['answer_text']
        if txt is None:
            continue
        # skip JSON-like values (lists) because matching may fail
        t0 = txt.strip()
        if t0.startswith('[') or t0.startswith('{'):
            continue
        if txt in ans_map:
            matches.append((txt, ans_map[txt], r['cnt']))

    print('\nSample matches (answer_text -> Ответ.id) up to 50:')
    for m in matches[:50]:
        print(' -', m[2], 'rows:', repr(m[0])[:200], '-> id=', m[1])

    if not matches:
        print('\nNo exact-text matches found; nothing to backfill automatically.')
        cur.close()
        conn.close()
        return

    confirm = input('\nProceed to update Анкета_ответ.answer_id for exact-text matches? [y/N]: ')
    if confirm.lower() != 'y':
        print('Aborted by user.')
        cur.close()
        conn.close()
        return

    # Perform updates for each matching text
    total_updated = 0
    for txt, aid, cnt in matches:
        cur.execute('UPDATE "Анкета_ответ" SET "answer_id" = %s WHERE "answer_id" IS NULL AND "answer_text" = %s', (aid, txt))
        updated = cur.rowcount
        total_updated += updated
        print(f'Updated {updated} rows for Ответ.id={aid} (text={repr(txt)[:80]})')

    conn.commit()
    print('\nTotal updated rows:', total_updated)

    cur.close()
    conn.close()

if __name__ == "__main__":
    main()
