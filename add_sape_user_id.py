#!/usr/bin/env python3
"""
Migration: Add sape_user_id field to sape_accounts table
"""

import sqlite3
import sys

DATABASE_PATH = 'database/sape_reports.db'

def migrate():
    print("="*80)
    print("МИГРАЦИЯ: Добавление поля sape_user_id")
    print("="*80)

    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()

    # Add new column
    print("\n1️⃣ Добавление колонки sape_user_id...")
    try:
        cursor.execute("ALTER TABLE sape_accounts ADD COLUMN sape_user_id VARCHAR(50)")
        print("   ✅ Колонка sape_user_id добавлена")
    except sqlite3.OperationalError as e:
        if 'duplicate column name' in str(e).lower():
            print("   ℹ️  Колонка sape_user_id уже существует")
        else:
            raise

    conn.commit()
    conn.close()

    print("\n" + "="*80)
    print("✅ МИГРАЦИЯ ЗАВЕРШЕНА")
    print("="*80)
    print("\nТеперь можно добавлять User ID в форме редактирования аккаунта.")

if __name__ == '__main__':
    try:
        migrate()
    except Exception as e:
        print(f"\n❌ КРИТИЧЕСКАЯ ОШИБКА: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
