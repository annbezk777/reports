#!/usr/bin/env python3
"""
Create complete authentication system with registration
"""
import sqlite3
import hashlib

DATABASE_PATH = 'database/sape_reports.db'

def create_users_table():
    """Create users table in database"""
    print("=" * 80)
    print("СОЗДАНИЕ ТАБЛИЦЫ ПОЛЬЗОВАТЕЛЕЙ")
    print("=" * 80)

    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()

    # Create users table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email VARCHAR(255) UNIQUE NOT NULL,
            password_hash VARCHAR(255) NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            active BOOLEAN DEFAULT 1
        )
    """)

    print("✅ Таблица users создана")

    # Create first admin user
    admin_email = "a.bereznyak@sape.ru"
    admin_password = "sape2024"
    password_hash = hashlib.sha256(admin_password.encode()).hexdigest()

    try:
        cursor.execute("""
            INSERT INTO users (email, password_hash)
            VALUES (?, ?)
        """, (admin_email, password_hash))
        print(f"✅ Создан администратор: {admin_email}")
        print(f"   Пароль: {admin_password}")
    except sqlite3.IntegrityError:
        print(f"ℹ️  Администратор {admin_email} уже существует")

    conn.commit()
    conn.close()

    print("=" * 80)

if __name__ == '__main__':
    create_users_table()
