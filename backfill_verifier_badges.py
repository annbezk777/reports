#!/usr/bin/env python3
"""
One-off backfill: pull the "Верификатор:" note from every monitoring's
linked Asana task and store the parsed letter badge (W/S/T/A) in
monitoring_campaigns.verifier_badge. Safe to re-run - only touches that
one column, никаких других плановых полей не трогает.
"""
import sqlite3
import sys

from app.api.asana_client import AsanaClient

DB_PATH = 'database/sape_reports.db'


def main():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute(
        "SELECT id, name, asana_task_url, verifier_badge FROM monitoring_campaigns "
        "WHERE asana_task_url IS NOT NULL AND asana_task_url != ''"
    )
    rows = cur.fetchall()
    print(f"Найдено {len(rows)} мониторингов со ссылкой на Asana")

    client = AsanaClient()
    if not client.token:
        print("Asana токен не найден - прерываю")
        sys.exit(1)

    updated = skipped = errors = 0
    for row in rows:
        task_gid = client.extract_task_gid(row['asana_task_url'])
        if not task_gid:
            print(f"  [{row['id']}] {row['name']}: не удалось извлечь ID задачи из ссылки")
            skipped += 1
            continue
        try:
            task = client.get_task(task_gid)
        except Exception as e:
            print(f"  [{row['id']}] {row['name']}: ошибка Asana API: {e}")
            errors += 1
            continue

        badge = AsanaClient.parse_task_notes(task.get('notes')).get('verifier_badge')
        if not badge:
            print(f"  [{row['id']}] {row['name']}: поле 'Верификатор:' не найдено в заметках")
            skipped += 1
            continue

        if badge != row['verifier_badge']:
            cur.execute("UPDATE monitoring_campaigns SET verifier_badge = ? WHERE id = ?", (badge, row['id']))
            print(f"  [{row['id']}] {row['name']}: verifier_badge -> {badge}")
            updated += 1
        else:
            print(f"  [{row['id']}] {row['name']}: уже {badge}, без изменений")

    conn.commit()
    conn.close()
    print(f"\nГотово. Обновлено: {updated}, пропущено: {skipped}, ошибок: {errors}")


if __name__ == '__main__':
    main()
