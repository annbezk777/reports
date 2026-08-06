#!/usr/bin/env python3
"""
Backup and restore database with all important data
"""
import sqlite3
import json
import os
from datetime import datetime
import shutil

DB_FILE = 'sape_reports.db'
BACKUP_DIR = 'backups'

def backup_database():
    """Create full backup of database"""
    # Create backup directory if not exists
    if not os.path.exists(BACKUP_DIR):
        os.makedirs(BACKUP_DIR)

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_file = os.path.join(BACKUP_DIR, f'sape_reports_{timestamp}.db')

    # Copy database file
    shutil.copy2(DB_FILE, backup_file)

    # Also export accounts to JSON for easy recovery
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    cursor.execute("SELECT id, name, login, api_token FROM sape_accounts")
    accounts = cursor.fetchall()

    accounts_data = [
        {
            'id': acc[0],
            'name': acc[1],
            'login': acc[2],
            'api_token': acc[3]
        }
        for acc in accounts
    ]

    json_file = os.path.join(BACKUP_DIR, f'accounts_{timestamp}.json')
    with open(json_file, 'w') as f:
        json.dump(accounts_data, f, indent=2)

    conn.close()

    print(f"✅ Backup created:")
    print(f"   Database: {backup_file}")
    print(f"   Accounts: {json_file}")
    print(f"   Total accounts: {len(accounts_data)}")

    return backup_file, json_file

def list_backups():
    """List all available backups"""
    if not os.path.exists(BACKUP_DIR):
        print("No backups found")
        return []

    backups = [f for f in os.listdir(BACKUP_DIR) if f.endswith('.db')]
    backups.sort(reverse=True)

    if not backups:
        print("No backups found")
        return []

    print("Available backups:")
    for i, backup in enumerate(backups, 1):
        filepath = os.path.join(BACKUP_DIR, backup)
        size = os.path.getsize(filepath) / 1024  # KB
        mtime = datetime.fromtimestamp(os.path.getmtime(filepath))
        print(f"{i}. {backup} ({size:.1f} KB, {mtime.strftime('%Y-%m-%d %H:%M:%S')})")

    return backups

def restore_database(backup_file):
    """Restore database from backup"""
    if not os.path.exists(backup_file):
        print(f"❌ Backup file not found: {backup_file}")
        return False

    # Create backup of current database before restoring
    if os.path.exists(DB_FILE):
        print("Creating backup of current database before restore...")
        backup_database()

    # Restore
    shutil.copy2(backup_file, DB_FILE)
    print(f"✅ Database restored from: {backup_file}")
    return True

if __name__ == '__main__':
    import sys

    if len(sys.argv) < 2:
        print("Usage:")
        print("  Backup:  python backup_restore.py backup")
        print("  List:    python backup_restore.py list")
        print("  Restore: python backup_restore.py restore <backup_file>")
        sys.exit(1)

    command = sys.argv[1]

    if command == 'backup':
        backup_database()
    elif command == 'list':
        list_backups()
    elif command == 'restore' and len(sys.argv) == 3:
        restore_database(sys.argv[2])
    else:
        print("Invalid command")
