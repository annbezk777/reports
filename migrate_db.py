#!/usr/bin/env python3
"""
Database migration script - adds new columns without losing data
"""
import sqlite3
import os

DB_PATH = 'sape_reports.db'

def migrate():
    """Add worksheet_name column to report_configs table"""
    if not os.path.exists(DB_PATH):
        print("❌ Database file not found. No migration needed.")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        # Check if column already exists
        cursor.execute("PRAGMA table_info(report_configs)")
        columns = [col[1] for col in cursor.fetchall()]

        if 'worksheet_name' not in columns:
            print("Adding worksheet_name column to report_configs...")
            cursor.execute("ALTER TABLE report_configs ADD COLUMN worksheet_name VARCHAR(255)")
            conn.commit()
            print("✅ Migration completed successfully!")
        else:
            print("✅ Column worksheet_name already exists, no migration needed.")

    except Exception as e:
        print(f"❌ Migration failed: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == '__main__':
    migrate()
