#!/usr/bin/env python3
"""
One-way database sync: production -> local.

This is the ONLY direction that's safe to automate - production's
fact_impressions/fact_clicks/last_sync etc. are live and independently
refreshed by its own scheduled jobs, so a local -> production sync
could roll that data back. Pulling production down to local carries no
such risk: local is a dev sandbox (ENABLE_AUTO_SYNC=0, no live refresh
of its own), so simply replacing it wholesale is correct and simple -
no per-table merge logic needed (a previous version of this script
tried to preserve monitoring_campaigns as "local-only", which stopped
being true once monitoring data started living on production too).

Usage: python sync_from_server.py
"""

import os
import shutil
import subprocess
import sqlite3
from datetime import datetime

SERVER_HOST = "root@74.208.242.125"
SERVER_DB_PATH = "/root/web-projects/sape-reports/database/sape_reports.db"
LOCAL_DB_PATH = "database/sape_reports.db"
BACKUP_DIR = "backups"


def backup_local():
    if not os.path.exists(LOCAL_DB_PATH):
        print(f"ℹ️  No local database at {LOCAL_DB_PATH}, skipping backup")
        return None
    os.makedirs(BACKUP_DIR, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = os.path.join(BACKUP_DIR, f"sape_reports_{timestamp}.db")
    shutil.copy2(LOCAL_DB_PATH, backup_path)
    print(f"✅ Backed up local database to: {backup_path}")
    return backup_path


def print_table_counts(db_path, label):
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    for table in ('sape_accounts', 'campaigns', 'report_configs', 'monitoring_campaigns', 'verifier_links'):
        try:
            cur.execute(f"SELECT COUNT(*) FROM {table}")
            print(f"   {table}: {cur.fetchone()[0]}")
        except sqlite3.OperationalError:
            print(f"   {table}: (no such table)")
    conn.close()


def sync_from_server():
    print(f"\n{'=' * 60}\n🔄 Syncing database: production -> local\n{'=' * 60}\n")

    backup_path = backup_local()

    temp_path = f"{LOCAL_DB_PATH}.tmp"
    print(f"\n📥 Downloading from {SERVER_HOST}:{SERVER_DB_PATH} ...")
    try:
        subprocess.run(["scp", f"{SERVER_HOST}:{SERVER_DB_PATH}", temp_path], check=True)
    except subprocess.CalledProcessError:
        if os.path.exists(temp_path):
            os.remove(temp_path)
        print("❌ Download failed - local database left untouched")
        raise

    os.replace(temp_path, LOCAL_DB_PATH)
    print("✅ Local database replaced with production's copy")

    with open('.last_sync', 'w') as f:
        f.write(datetime.now().isoformat())

    print("\n📊 Row counts after sync:")
    print_table_counts(LOCAL_DB_PATH, "local")

    print(f"\n{'=' * 60}\n✅ Sync complete{'=' * 60}")
    if backup_path:
        print(f"💾 Pre-sync backup: {backup_path}")


if __name__ == "__main__":
    try:
        sync_from_server()
    except KeyboardInterrupt:
        print("\n⚠️  Sync cancelled")
    except Exception as e:
        print(f"\n❌ Sync failed: {e}")
        exit(1)
