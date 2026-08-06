#!/usr/bin/env python3
"""
Update final 2 SAPE User IDs
"""
import sqlite3

DATABASE_PATH = 'database/sape_reports.db'

# Last 2 accounts from screenshot
USER_IDS = {
    'full-canvas-digital@sape.ru': '1659212',
    'dsp-deltaclick@sape.ru': '1651493',
}

def update_user_ids():
    print("=" * 80)
    print("ОБНОВЛЕНИЕ ПОСЛЕДНИХ SAPE USER ID")
    print("=" * 80)
    print()

    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()

    updated_count = 0

    for email, user_id in USER_IDS.items():
        cursor.execute("SELECT id, name FROM sape_accounts WHERE login = ?", (email,))
        result = cursor.fetchone()

        if result:
            account_id, account_name = result
            cursor.execute(
                "UPDATE sape_accounts SET sape_user_id = ? WHERE id = ?",
                (user_id, account_id)
            )
            print(f"✅ {account_name} ({email})")
            print(f"   → User ID: {user_id}")
            updated_count += 1
        else:
            print(f"⚠️  Аккаунт не найден: {email}")

    conn.commit()

    # Final check
    print()
    print("=" * 80)
    print("ФИНАЛЬНАЯ ПРОВЕРКА - АККАУНТЫ БЕЗ USER ID:")
    print("=" * 80)

    cursor.execute("""
        SELECT id, name, login
        FROM sape_accounts
        WHERE (sape_user_id IS NULL OR sape_user_id = '') AND active = 1
        ORDER BY id
    """)

    missing = cursor.fetchall()
    if missing:
        for acc_id, name, login in missing:
            print(f"❌ {name} ({login})")
    else:
        print("✅ ВСЕ АККАУНТЫ ИМЕЮТ USER ID!")

    # Count statistics
    cursor.execute("SELECT COUNT(*) FROM sape_accounts WHERE active = 1")
    total = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM sape_accounts WHERE active = 1 AND sape_user_id IS NOT NULL AND sape_user_id != ''")
    with_id = cursor.fetchone()[0]

    conn.close()

    print()
    print("=" * 80)
    print(f"✅ Обновлено: {updated_count}")
    print(f"📊 Статистика: {with_id} из {total} аккаунтов имеют User ID")
    print("=" * 80)

if __name__ == '__main__':
    update_user_ids()
