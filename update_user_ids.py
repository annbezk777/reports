#!/usr/bin/env python3
"""
Update SAPE User IDs for accounts
"""
import sqlite3

DATABASE_PATH = 'database/sape_reports.db'

# Mapping from screenshot: ID -> Email
USER_IDS = {
    'full-kokoc@sape.ru': '1864157',
    'account10@sape.ru': '1862825',
    'account9@sape.ru': '1862824',
    'full_media_ppl@sape.ru': '1862471',
    'full_advelop@sape.ru': '1861509',
    'full-rosst-mbr@sape.ru': '1861000',
    'full_novacosmetics@sape.ru': '1860647',
    'full_lazurnyibereg@sape.ru': '1859989',
    'full_flowwow@sape.ru': '1859245',
    'full_nomica@sape.ru': '1852102',
    'account2@sape.ru': '1847426',
}

def update_user_ids():
    print("=" * 80)
    print("ОБНОВЛЕНИЕ SAPE USER ID")
    print("=" * 80)
    print()

    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()

    updated_count = 0
    not_found_count = 0

    for email, user_id in USER_IDS.items():
        # Check if account exists
        cursor.execute("SELECT id, name FROM sape_accounts WHERE login = ?", (email,))
        result = cursor.fetchone()

        if result:
            account_id, account_name = result

            # Update user_id
            cursor.execute(
                "UPDATE sape_accounts SET sape_user_id = ? WHERE id = ?",
                (user_id, account_id)
            )

            print(f"✅ {account_name} ({email})")
            print(f"   → User ID: {user_id}")
            updated_count += 1
        else:
            print(f"⚠️  Аккаунт не найден: {email}")
            not_found_count += 1

    conn.commit()
    conn.close()

    print()
    print("=" * 80)
    print(f"✅ Обновлено: {updated_count}")
    if not_found_count > 0:
        print(f"⚠️  Не найдено: {not_found_count}")
    print("=" * 80)

if __name__ == '__main__':
    update_user_ids()
