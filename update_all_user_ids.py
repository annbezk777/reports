#!/usr/bin/env python3
"""
Update SAPE User IDs for ALL accounts
"""
import sqlite3

DATABASE_PATH = 'database/sape_reports.db'

# Complete mapping from both screenshots: ID -> Email
USER_IDS = {
    # From first screenshot
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

    # From second screenshot
    'full_clickru@sape.ru': '1845159',
    'full_adlabs@sape.ru': '1817034',
    'no_erid_izi.net@sape.ru': '1757113',
    'full_omd_resolution@sape.ru': '1756351',
    'full_sa_media@sape.ru': '1755384',
    'full-it-agency@sape.ru': '1681001',
    'full-izi.net@sape.ru': '1680149',
    'full-stargeit@sape.ru': '1673518',
    'full-raelweb@sape.ru': '1662255',
}

def update_user_ids():
    print("=" * 80)
    print("ОБНОВЛЕНИЕ ВСЕХ SAPE USER ID")
    print("=" * 80)
    print()

    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()

    updated_count = 0
    skipped_count = 0
    not_found_count = 0

    for email, user_id in USER_IDS.items():
        # Check if account exists
        cursor.execute("SELECT id, name, sape_user_id FROM sape_accounts WHERE login = ?", (email,))
        result = cursor.fetchone()

        if result:
            account_id, account_name, current_user_id = result

            if current_user_id == user_id:
                print(f"⏭️  {account_name} ({email}) - уже обновлен")
                skipped_count += 1
            else:
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

    # Show accounts without User ID
    print()
    print("=" * 80)
    print("АККАУНТЫ БЕЗ USER ID:")
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
        print("Все аккаунты имеют User ID! ✅")

    conn.close()

    print()
    print("=" * 80)
    print(f"✅ Обновлено: {updated_count}")
    print(f"⏭️  Пропущено (уже были): {skipped_count}")
    if not_found_count > 0:
        print(f"⚠️  Не найдено: {not_found_count}")
    print("=" * 80)

if __name__ == '__main__':
    update_user_ids()
