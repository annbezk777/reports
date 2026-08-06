#!/usr/bin/env python3
"""
Create users table with email verification support
"""
import sqlite3
import hashlib

DATABASE_PATH = 'database/sape_reports.db'

def create_users_table():
    """Create users table in database"""
    print("=" * 80)
    print("СОЗДАНИЕ ТАБЛИЦЫ ПОЛЬЗОВАТЕЛЕЙ")
    print("=" * 80)
    print()

    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()

    # Drop existing users table if exists
    cursor.execute("DROP TABLE IF EXISTS users")
    print("✅ Удалена старая таблица users (если была)")

    # Create users table with verification fields
    cursor.execute("""
        CREATE TABLE users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email VARCHAR(255) UNIQUE NOT NULL,
            password_hash VARCHAR(255) NOT NULL,
            verification_code VARCHAR(6),
            email_verified BOOLEAN DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            active BOOLEAN DEFAULT 1
        )
    """)

    print("✅ Таблица users создана со следующими полями:")
    print("   - id (INTEGER PRIMARY KEY)")
    print("   - email (VARCHAR(255) UNIQUE)")
    print("   - password_hash (VARCHAR(255))")
    print("   - verification_code (VARCHAR(6))")
    print("   - email_verified (BOOLEAN)")
    print("   - created_at (TIMESTAMP)")
    print("   - active (BOOLEAN)")
    print()

    # Create first admin user (already verified)
    admin_email = "a.bereznyak@sape.ru"
    admin_password = "sape2024"
    password_hash = hashlib.sha256(admin_password.encode()).hexdigest()

    try:
        cursor.execute("""
            INSERT INTO users (email, password_hash, email_verified, active)
            VALUES (?, ?, 1, 1)
        """, (admin_email, password_hash))
        print(f"✅ Создан администратор:")
        print(f"   Email: {admin_email}")
        print(f"   Пароль: {admin_password}")
        print(f"   Email подтвержден: Да")
    except sqlite3.IntegrityError:
        print(f"ℹ️  Администратор {admin_email} уже существует")

    conn.commit()
    conn.close()

    print()
    print("=" * 80)
    print("✅ ТАБЛИЦА ГОТОВА К ИСПОЛЬЗОВАНИЮ")
    print("=" * 80)

if __name__ == '__main__':
    create_users_table()
