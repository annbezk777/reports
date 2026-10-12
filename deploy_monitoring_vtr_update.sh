#!/bin/bash
# Deployment script for Monitoring VTR/CTR improvements
# Date: 2026-10-12
# Changes:
#   - Add fact_vtr column to database
#   - Change auto-update time from 09:00 to 03:00
#   - Add delays between API requests to prevent timeouts
#   - Change CTR/VTR display in performance row to show difference instead of percentage
#   - Add Adriver Excel upload functionality

set -e  # Exit on error

SERVER="root@74.208.242.125"
REMOTE_DIR="/root/web-projects/sape-reports"

echo "🚀 Deploying Monitoring VTR/CTR improvements to production..."
echo ""

# Step 1: Pull latest code on server
echo "📥 Step 1/5: Pulling latest code from GitHub..."
ssh $SERVER << 'ENDSSH'
cd /root/web-projects/sape-reports
git pull origin main
ENDSSH
echo "✅ Code updated"
echo ""

# Step 2: Run database migration
echo "💾 Step 2/5: Running database migration (add fact_vtr column)..."
ssh $SERVER << 'ENDSSH'
cd /root/web-projects/sape-reports
sqlite3 database/sape_reports.db "ALTER TABLE monitoring_campaigns ADD COLUMN fact_vtr FLOAT;" 2>/dev/null || echo "   ℹ️ Column already exists (this is OK)"
sqlite3 database/sape_reports.db "SELECT name, type FROM pragma_table_info('monitoring_campaigns') WHERE name = 'fact_vtr';" | grep -q "fact_vtr" && echo "   ✅ Column fact_vtr exists" || echo "   ❌ Migration failed"
ENDSSH
echo "✅ Database migration completed"
echo ""

# Step 3: Install/update dependencies (if needed)
echo "📦 Step 3/5: Checking dependencies..."
ssh $SERVER << 'ENDSSH'
cd /root/web-projects/sape-reports
source venv/bin/activate
pip install -r requirements.txt --quiet
ENDSSH
echo "✅ Dependencies checked"
echo ""

# Step 4: Restart service
echo "🔄 Step 4/5: Restarting sape-reports service..."
ssh $SERVER << 'ENDSSH'
systemctl restart sape-reports
sleep 3
systemctl is-active --quiet sape-reports && echo "   ✅ Service is running" || echo "   ❌ Service failed to start"
ENDSSH
echo "✅ Service restarted"
echo ""

# Step 5: Verify deployment
echo "✅ Step 5/5: Verifying deployment..."
ssh $SERVER << 'ENDSSH'
echo "   📊 Service status:"
systemctl status sape-reports --no-pager | head -3
echo ""
echo "   📝 Recent logs (last 5 lines):"
journalctl -u sape-reports -n 5 --no-pager | tail -5
ENDSSH
echo ""

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🎉 Deployment completed successfully!"
echo ""
echo "📋 Changes deployed:"
echo "   ✅ Database: Added fact_vtr column for VTR/VR data"
echo "   ✅ Scheduler: Auto-update time changed from 09:00 to 03:00 MSK"
echo "   ✅ API: Added delays between requests (2-3 seconds)"
echo "   ✅ UI: CTR/VTR show difference instead of percentage in performance row"
echo "   ✅ Feature: Added Adriver Excel upload functionality"
echo ""
echo "🌐 URL: http://74.208.242.125:5500/"
echo "📊 Check monitoring page to verify changes"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
