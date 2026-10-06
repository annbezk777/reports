#!/usr/bin/env python3
"""
Sync database from production server to local
Usage: python sync_from_server.py
"""

import os
import subprocess
import shutil
from datetime import datetime

# Configuration
SERVER_HOST = "root@74.208.242.125"
SERVER_DB_PATH = "/root/web-projects/sape-reports/database/sape_reports.db"
LOCAL_DB_PATH = "database/sape_reports.db"  # FIXED: Use correct database path
BACKUP_DIR = "backups"

def create_backup():
    """Create backup of current local database"""
    if not os.path.exists(LOCAL_DB_PATH):
        print(f"ℹ️  No local database found at {LOCAL_DB_PATH}, skipping backup")
        return None

    # Create backups directory if doesn't exist
    os.makedirs(BACKUP_DIR, exist_ok=True)

    # Create timestamped backup
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = os.path.join(BACKUP_DIR, f"sape_reports_{timestamp}.db")

    shutil.copy2(LOCAL_DB_PATH, backup_path)
    print(f"✅ Backed up local database to: {backup_path}")
    return backup_path

def merge_databases(server_db_path, local_db_path):
    """Merge server database with local, preserving local-only tables"""
    import sqlite3

    # Tables that exist only locally (not on server)
    LOCAL_ONLY_TABLES = ['monitoring_campaigns']

    # Backup local-only tables
    print(f"   💾 Preserving local-only tables: {', '.join(LOCAL_ONLY_TABLES)}")

    local_tables_backup = {}

    if os.path.exists(local_db_path):
        # Extract local-only tables
        local_conn = sqlite3.connect(local_db_path)
        local_cursor = local_conn.cursor()

        # Get list of tables in local DB
        local_cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        existing_tables = [row[0] for row in local_cursor.fetchall()]

        for table_name in LOCAL_ONLY_TABLES:
            if table_name in existing_tables:
                # Get table schema
                local_cursor.execute(f"SELECT sql FROM sqlite_master WHERE type='table' AND name='{table_name}'")
                schema = local_cursor.fetchone()
                if schema:
                    local_tables_backup[table_name] = {
                        'schema': schema[0],
                        'data': []
                    }

                    # Get all data
                    local_cursor.execute(f"SELECT * FROM {table_name}")
                    local_tables_backup[table_name]['data'] = local_cursor.fetchall()

                    print(f"      ✅ Backed up {table_name}: {len(local_tables_backup[table_name]['data'])} rows")

        local_conn.close()

    # Replace with server database
    print(f"   🔄 Replacing with server database...")
    if os.path.exists(local_db_path):
        os.remove(local_db_path)
    shutil.copy2(server_db_path, local_db_path)

    # Restore local-only tables
    if local_tables_backup:
        print(f"   ♻️  Restoring local-only tables...")
        local_conn = sqlite3.connect(local_db_path)
        local_cursor = local_conn.cursor()

        for table_name, table_data in local_tables_backup.items():
            # Create table
            local_cursor.execute(table_data['schema'])

            # Insert data
            if table_data['data']:
                placeholders = ','.join(['?' for _ in table_data['data'][0]])
                local_cursor.executemany(
                    f"INSERT INTO {table_name} VALUES ({placeholders})",
                    table_data['data']
                )

            print(f"      ✅ Restored {table_name}: {len(table_data['data'])} rows")

        local_conn.commit()
        local_conn.close()

def sync_from_server():
    """Download database from server using scp and merge with local tables"""
    print(f"\n{'='*60}")
    print(f"🔄 Starting database sync from production server")
    print(f"{'='*60}\n")

    # Step 1: Backup local database
    print("📦 Step 1: Creating backup of local database...")
    backup_path = create_backup()

    # Step 2: Download from server
    print(f"\n📥 Step 2: Downloading database from server...")
    print(f"   Server: {SERVER_HOST}")
    print(f"   Remote path: {SERVER_DB_PATH}")
    print(f"   Local path: {LOCAL_DB_PATH}")

    temp_path = f"{LOCAL_DB_PATH}.tmp"

    try:
        # Use scp to download
        cmd = [
            "scp",
            f"{SERVER_HOST}:{SERVER_DB_PATH}",
            temp_path
        ]

        print(f"\n⏳ Running: {' '.join(cmd)}")
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)

        if result.returncode == 0:
            print(f"✅ Downloaded successfully")

            # Step 3: Merge databases (preserve local-only tables)
            print(f"\n📝 Step 3: Merging databases (preserving local tables)...")
            merge_databases(temp_path, LOCAL_DB_PATH)
            print(f"✅ Databases merged")

            # Cleanup temp file
            if os.path.exists(temp_path):
                os.remove(temp_path)

            # Step 4: Verify
            print(f"\n🔍 Step 4: Verifying database...")
            verify_database()

            # Save sync timestamp
            save_sync_timestamp()

            print(f"\n{'='*60}")
            print(f"✅ Sync completed successfully!")
            print(f"{'='*60}\n")

            if backup_path:
                print(f"💾 Backup saved at: {backup_path}")
            print(f"📊 Updated database at: {LOCAL_DB_PATH}")

        else:
            print(f"❌ SCP failed with return code: {result.returncode}")
            print(f"Error: {result.stderr}")

    except subprocess.CalledProcessError as e:
        print(f"\n❌ Error downloading from server: {e}")
        print(f"   Make sure you have SSH access to {SERVER_HOST}")

        # Cleanup temp file
        if os.path.exists(temp_path):
            os.remove(temp_path)

        # Restore backup if exists
        if backup_path and os.path.exists(backup_path):
            print(f"\n🔄 Restoring backup...")
            shutil.copy2(backup_path, LOCAL_DB_PATH)
            print(f"✅ Backup restored")

        raise

def verify_database():
    """Verify downloaded database has data"""
    import sqlite3

    try:
        conn = sqlite3.connect(LOCAL_DB_PATH)
        cursor = conn.cursor()

        # Check tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cursor.fetchall()
        print(f"   Found {len(tables)} tables: {', '.join([t[0] for t in tables])}")

        # Count records
        stats = {}
        for table_name in ['sape_accounts', 'campaigns', 'report_configs', 'monitoring_campaigns']:
            try:
                cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
                count = cursor.fetchone()[0]
                stats[table_name] = count
            except sqlite3.OperationalError:
                stats[table_name] = 'N/A'

        print(f"   Records:")
        for table, count in stats.items():
            print(f"     - {table}: {count}")

        conn.close()

    except Exception as e:
        print(f"   ⚠️  Could not verify database: {e}")

def save_sync_timestamp():
    """Save timestamp of last successful sync"""
    timestamp_file = '.last_sync'
    with open(timestamp_file, 'w') as f:
        f.write(datetime.now().isoformat())
    print(f"   💾 Saved sync timestamp to {timestamp_file}")

if __name__ == "__main__":
    try:
        sync_from_server()
    except KeyboardInterrupt:
        print("\n\n⚠️  Sync cancelled by user")
    except Exception as e:
        print(f"\n\n❌ Sync failed: {e}")
        exit(1)
