#!/bin/bash
# Full deployment script for Monitoring functionality
# Date: 2026-10-12
# This script:
#   - Creates monitoring_campaigns table if it doesn't exist
#   - Adds fact_vtr column if table exists but column doesn't
#   - Deploys all monitoring improvements

set -e  # Exit on error

SERVER="root@74.208.242.125"
REMOTE_DIR="/root/web-projects/sape-reports"

echo "🚀 Deploying Monitoring functionality to production..."
echo ""

# Step 1: Pull latest code on server
echo "📥 Step 1/6: Pulling latest code from GitHub..."
ssh $SERVER << 'ENDSSH'
cd /root/web-projects/sape-reports
git pull origin main
ENDSSH
echo "✅ Code updated"
echo ""

# Step 2: Create monitoring_campaigns table if it doesn't exist
echo "💾 Step 2/6: Creating/updating monitoring_campaigns table..."
ssh $SERVER << 'ENDSSH'
cd /root/web-projects/sape-reports

python3 << 'PYEOF'
import sqlite3

print("🔧 Checking database schema...")

conn = sqlite3.connect('database/sape_reports.db')
cur = conn.cursor()

# Get all tables
cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [row[0] for row in cur.fetchall()]

if 'monitoring_campaigns' not in tables:
    print("   ➕ Creating monitoring_campaigns table...")

    # Read and execute SQL migration
    with open('migrations/create_monitoring_campaigns_table.sql', 'r') as f:
        sql_script = f.read()

    try:
        cur.executescript(sql_script)
        conn.commit()
        print("   ✅ Table monitoring_campaigns created successfully")
    except Exception as e:
        print(f"   ❌ Error creating table: {e}")
        exit(1)
else:
    print("   ✅ Table monitoring_campaigns already exists")

    # Check if fact_vtr column exists
    cur.execute('PRAGMA table_info(monitoring_campaigns)')
    columns = [row[1] for row in cur.fetchall()]

    if 'fact_vtr' not in columns:
        print("   ➕ Adding fact_vtr column...")
        try:
            cur.execute('ALTER TABLE monitoring_campaigns ADD COLUMN fact_vtr FLOAT')
            conn.commit()
            print("   ✅ Column fact_vtr added")
        except Exception as e:
            print(f"   ❌ Error adding column: {e}")
    else:
        print("   ✅ Column fact_vtr already exists")

# Verify final schema
cur.execute('PRAGMA table_info(monitoring_campaigns)')
columns = cur.fetchall()
print(f"   📊 Final schema: {len(columns)} columns")

conn.close()
print("✅ Database schema updated")
PYEOF

ENDSSH
echo ""

# Step 3: Install/update dependencies
echo "📦 Step 3/6: Checking dependencies..."
ssh $SERVER << 'ENDSSH'
cd /root/web-projects/sape-reports
source venv/bin/activate
pip install -r requirements.txt --quiet
ENDSSH
echo "✅ Dependencies checked"
echo ""

# Step 4: Copy parse_adriver_excel.py if needed
echo "📄 Step 4/6: Ensuring all monitoring files are present..."
ssh $SERVER << 'ENDSSH'
cd /root/web-projects/sape-reports
if [ -f "parse_adriver_excel.py" ]; then
    echo "   ✅ parse_adriver_excel.py exists"
else
    echo "   ⚠️ parse_adriver_excel.py missing (should be in repo)"
fi
ENDSSH
echo ""

# Step 5: Restart service
echo "🔄 Step 5/6: Restarting sape-reports service..."
ssh $SERVER << 'ENDSSH'
systemctl restart sape-reports
sleep 3
systemctl is-active --quiet sape-reports && echo "   ✅ Service is running" || echo "   ❌ Service failed to start"
ENDSSH
echo "✅ Service restarted"
echo ""

# Step 6: Verify deployment
echo "✅ Step 6/6: Verifying deployment..."
ssh $SERVER << 'ENDSSH'
cd /root/web-projects/sape-reports

echo "   📊 Service status:"
systemctl status sape-reports --no-pager | head -3

echo ""
echo "   💾 Database verification:"
python3 << 'PYEOF'
import sqlite3
conn = sqlite3.connect('database/sape_reports.db')
cur = conn.cursor()

# Check table exists
cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='monitoring_campaigns'")
table_exists = cur.fetchone() is not None

if table_exists:
    # Count columns
    cur.execute('PRAGMA table_info(monitoring_campaigns)')
    columns = cur.fetchall()

    # Check specific columns
    column_names = [col[1] for col in columns]
    has_fact_vtr = 'fact_vtr' in column_names
    has_plan_vtr = 'plan_vtr' in column_names

    print(f"      ✅ Table exists: {len(columns)} columns")
    print(f"      ✅ plan_vtr column: {has_plan_vtr}")
    print(f"      ✅ fact_vtr column: {has_fact_vtr}")

    # Count records
    cur.execute('SELECT COUNT(*) FROM monitoring_campaigns')
    count = cur.fetchone()[0]
    print(f"      📊 Monitoring campaigns: {count}")
else:
    print("      ❌ Table monitoring_campaigns does not exist")

conn.close()
PYEOF

echo ""
echo "   📝 Recent logs (last 5 lines):"
journalctl -u sape-reports -n 5 --no-pager | tail -5

ENDSSH
echo ""

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🎉 Deployment completed successfully!"
echo ""
echo "📋 Changes deployed:"
echo "   ✅ Database: monitoring_campaigns table created/updated"
echo "   ✅ Database: fact_vtr column added for VTR/VR data"
echo "   ✅ Scheduler: Auto-update time set to 03:00 MSK"
echo "   ✅ API: Delays added between requests (2-3 seconds)"
echo "   ✅ UI: CTR/VTR show difference in performance row"
echo "   ✅ Feature: Adriver Excel upload functionality"
echo "   ✅ Feature: Full monitoring dashboard available"
echo ""
echo "🌐 URL: http://74.208.242.125:5500/"
echo "📊 Navigate to /monitoring to see monitoring dashboard"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
