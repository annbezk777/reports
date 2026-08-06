#!/usr/bin/env python3
"""
List all SAPE accounts from database
"""
import sqlite3

DATABASE_PATH = 'database/sape_reports.db'

def list_accounts():
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, name, login, sape_user_id, active, created_at
        FROM sape_accounts
        ORDER BY id
    """)

    accounts = cursor.fetchall()
    conn.close()

    print("=" * 120)
    print("СПИСОК АККАУНТОВ SAPE")
    print("=" * 120)
    print()

    if not accounts:
        print("Аккаунты не найдены")
        return

    print(f"Всего аккаунтов: {len(accounts)}")
    print()

    for account in accounts:
        account_id, name, login, sape_user_id, active, created_at = account
        status = "✅ Активен" if active else "❌ Неактивен"
        user_id_str = sape_user_id if sape_user_id else "❌ Не указан"

        print(f"{'='*120}")
        print(f"ID: {account_id}")
        print(f"Название: {name}")
        print(f"Логин: {login}")
        print(f"SAPE User ID: {user_id_str}")
        print(f"Статус: {status}")
        print(f"Создан: {created_at}")
        print()

if __name__ == '__main__':
    list_accounts()
