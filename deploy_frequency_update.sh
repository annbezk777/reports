#!/bin/bash
# Deploy frequency update (new campaign_settings structure)

set -e

SERVER="root@85.239.51.28"
REMOTE_PATH="/root/web-projects/sape-reports"

echo "🚀 Deploying frequency update to production..."
echo ""

# Create a temporary directory for deployment
TEMP_DIR="/tmp/deploy_frequency_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$TEMP_DIR/app/api"
mkdir -p "$TEMP_DIR/app/templates"

echo "1️⃣  Copying files to temporary directory..."

# Backend files
cp "app.py" "$TEMP_DIR/"
cp "app/models.py" "$TEMP_DIR/app/"
cp "app/api/google_sheets_client.py" "$TEMP_DIR/app/api/"

# Templates
cp "app/templates/add_report.html" "$TEMP_DIR/app/templates/"
cp "app/templates/edit_report.html" "$TEMP_DIR/app/templates/"

# Migration script
cp "migrate_to_campaign_settings.py" "$TEMP_DIR/"

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
BACKUP_DIR="backups/backup_frequency_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BACKUP_DIR/app/api"
mkdir -p "$BACKUP_DIR/app/templates"
mkdir -p "$BACKUP_DIR/database"

echo "📦 Creating backup..."
cp app.py "$BACKUP_DIR/" 2>/dev/null || true
cp main.py "$BACKUP_DIR/" 2>/dev/null || true
cp app/models.py "$BACKUP_DIR/app/" 2>/dev/null || true
cp app/api/google_sheets_client.py "$BACKUP_DIR/app/api/" 2>/dev/null || true
cp app/templates/add_report.html "$BACKUP_DIR/app/templates/" 2>/dev/null || true
cp app/templates/edit_report.html "$BACKUP_DIR/app/templates/" 2>/dev/null || true
cp database/sape_reports.db "$BACKUP_DIR/database/" 2>/dev/null || true
echo "✅ Backup created: $BACKUP_DIR"

# Extract new files
echo "📂 Extracting files..."
tar -xzf /tmp/deploy.tar.gz

# Copy app.py to main.py
cp app.py main.py

echo "🔄 Running database migration..."
python3 migrate_to_campaign_settings.py

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
echo "🧪 To test, create a new report or edit existing one"

# Cleanup
rm -rf "$TEMP_DIR"
