#!/usr/bin/env python3
"""
Restore SAPE accounts using direct SQL
"""
import sqlite3
from datetime import datetime

# Account credentials
ACCOUNTS = [
    {
        'name': 'Full Media PPL',
        'login': 'full_media_ppl@sape.ru',
        'api_token': '4e160b4d832182f06c669268a8835b448b4e0b0b6bfb54e6072925a6bcabc304'
    },
    {
        'name': 'Full StargeIT',
        'login': 'full-stargeit@sape.ru',
        'api_token': '15ef0145b28c2678aa9275d331cc6856ef184d6099f785986feed5324d83e97b'
    },
    {
        'name': 'Full Advelop',
        'login': 'full_advelop@sape.ru',
        'api_token': '19d5b488099189d49df4cf9357e65082baaf3f2d97a329db58ce2ce650b4d2b3'
    }
]

def restore_accounts():
    """Restore all SAPE accounts to database"""
    conn = sqlite3.connect('sape_reports.db')
    cursor = conn.cursor()

    print("🔄 Restoring SAPE accounts...")

    for acc_data in ACCOUNTS:
        # Check if account already exists
        cursor.execute("SELECT id FROM sape_accounts WHERE login = ?", (acc_data['login'],))
        existing = cursor.fetchone()

        if existing:
            print(f"✅ Account already exists: {acc_data['name']} ({acc_data['login']})")
        else:
            cursor.execute("""
                INSERT INTO sape_accounts (name, login, api_token, active, created_at)
                VALUES (?, ?, ?, 1, ?)
            """, (acc_data['name'], acc_data['login'], acc_data['api_token'], datetime.utcnow().isoformat()))

            print(f"✅ Created account: {acc_data['name']} ({acc_data['login']})")

    conn.commit()
    conn.close()
    print("\n✅ All accounts restored successfully!")
    print("\nТеперь можете синхронизировать кампании в панели: http://localhost:5006/accounts")

if __name__ == '__main__':
    restore_accounts()
