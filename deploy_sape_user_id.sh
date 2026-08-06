#!/bin/bash
# Deploy SAPE User ID feature

set -e

SERVER="root@85.239.51.28"
REMOTE_PATH="/root/web-projects/sape-reports"

echo "🚀 Deploying SAPE User ID feature to production..."
echo ""

# Create a temporary directory for deployment
TEMP_DIR="/tmp/deploy_sape_user_id_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$TEMP_DIR/app/templates"

echo "1️⃣  Copying files to temporary directory..."

# Backend files
cp "app.py" "$TEMP_DIR/"
cp "app/models.py" "$TEMP_DIR/app/"

# Templates
cp "app/templates/reports.html" "$TEMP_DIR/app/templates/"
cp "app/templates/add_account.html" "$TEMP_DIR/app/templates/"
cp "app/templates/edit_account.html" "$TEMP_DIR/app/templates/"
cp "app/templates/add_report.html" "$TEMP_DIR/app/templates/"

# Migration script
cp "add_sape_user_id.py" "$TEMP_DIR/"

echo "2️⃣  Creating deployment archive..."
cd "$TEMP_DIR"
tar -czf deploy.tar.gz *
cd - > /dev/null

echo "3️⃣  Uploading to server..."
scp "$TEMP_DIR/deploy.tar.gz" "$SERVER:/tmp/"

echo "4️⃣  Deploying on server..."
ssh "$SERVER" << 'ENDSSH'
cd /root/web-projects/sape-reports

# Create backup
BACKUP_DIR="backups/backup_sape_user_id_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BACKUP_DIR/app/templates"
mkdir -p "$BACKUP_DIR/database"

echo "📦 Creating backup..."
cp app.py "$BACKUP_DIR/" 2>/dev/null || true
cp main.py "$BACKUP_DIR/" 2>/dev/null || true
cp app/models.py "$BACKUP_DIR/app/" 2>/dev/null || true
cp app/templates/reports.html "$BACKUP_DIR/app/templates/" 2>/dev/null || true
cp app/templates/add_account.html "$BACKUP_DIR/app/templates/" 2>/dev/null || true
cp app/templates/edit_account.html "$BACKUP_DIR/app/templates/" 2>/dev/null || true
cp app/templates/add_report.html "$BACKUP_DIR/app/templates/" 2>/dev/null || true
cp database/sape_reports.db "$BACKUP_DIR/database/" 2>/dev/null || true
echo "✅ Backup created: $BACKUP_DIR"

# Extract new files
echo "📂 Extracting files..."
tar -xzf /tmp/deploy.tar.gz

# Copy app.py to main.py
cp app.py main.py

echo "🔄 Running database migration..."
python3 add_sape_user_id.py

echo "🔄 Restarting service..."
systemctl restart sape-reports
sleep 3

# Check status
echo ""
echo "📊 Service status:"
systemctl status sape-reports --no-pager -l | head -20

echo ""
echo "✅ Deployment complete!"
echo "🌐 Check: http://85.239.51.28:5007"
ENDSSH

echo ""
echo "✅ Deployment finished!"
echo "🧪 To test:"
echo "   1. Edit an account and add SAPE User ID"
echo "   2. Check that login becomes a hyperlink in report cards"
echo "   3. Click the link to verify it opens SAPE cabinet"

# Cleanup
rm -rf "$TEMP_DIR"
