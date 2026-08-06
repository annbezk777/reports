#!/bin/bash
# Quick deploy script - copies updated files to production server

set -e

SERVER="root@85.239.51.28"
REMOTE_PATH="/root/api_google_sheets"

echo "📦 Deploying debug improvements to production..."
echo ""

# Create a temporary directory for deployment
TEMP_DIR="/tmp/deploy_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$TEMP_DIR/app/api"

echo "1️⃣  Copying files to temporary directory..."
cp "app.py" "$TEMP_DIR/"
cp "app/api/google_sheets_client.py" "$TEMP_DIR/app/api/"

echo "2️⃣  Creating deployment archive..."
cd "$TEMP_DIR"
tar -czf deploy.tar.gz *
cd - > /dev/null

echo "3️⃣  Uploading to server..."
scp "$TEMP_DIR/deploy.tar.gz" "$SERVER:/tmp/"

echo "4️⃣  Deploying on server..."
ssh "$SERVER" << 'ENDSSH'
cd /root/api_google_sheets

# Create backup
BACKUP_DIR="backups/backup_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BACKUP_DIR/app/api"
cp app.py "$BACKUP_DIR/" 2>/dev/null || true
cp main.py "$BACKUP_DIR/" 2>/dev/null || true
cp app/api/google_sheets_client.py "$BACKUP_DIR/app/api/" 2>/dev/null || true
echo "✅ Backup created: $BACKUP_DIR"

# Extract new files
tar -xzf /tmp/deploy.tar.gz

# Copy app.py to main.py
cp app.py main.py

# Restart service
systemctl restart sape-reports
sleep 2

# Check status
systemctl status sape-reports --no-pager -l | head -15

echo ""
echo "✅ Deployment complete!"
echo "🌐 Check: http://85.239.51.28:5007"
ENDSSH

echo ""
echo "✅ Deployment finished!"
echo ""
echo "Now try updating the report 'Акира оил баннер' and check the logs:"
echo "ssh $SERVER 'journalctl -u sape-reports -n 100 --no-pager'"
