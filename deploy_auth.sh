#!/bin/bash
# Deploy authentication feature

set -e

SERVER="root@85.239.51.28"
REMOTE_PATH="/root/web-projects/sape-reports"

echo "🚀 Deploying authentication to production..."
echo ""

# Create a temporary directory for deployment
TEMP_DIR="/tmp/deploy_auth_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$TEMP_DIR/app/templates"

echo "1️⃣  Copying files to temporary directory..."

# Backend files
cp "app.py" "$TEMP_DIR/"

# Templates
cp "app/templates/base.html" "$TEMP_DIR/app/templates/"
cp "app/templates/login.html" "$TEMP_DIR/app/templates/"

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
BACKUP_DIR="backups/backup_auth_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BACKUP_DIR/app/templates"

echo "📦 Creating backup..."
cp app.py "$BACKUP_DIR/" 2>/dev/null || true
cp main.py "$BACKUP_DIR/" 2>/dev/null || true
cp app/templates/base.html "$BACKUP_DIR/app/templates/" 2>/dev/null || true
echo "✅ Backup created: $BACKUP_DIR"

# Extract new files
echo "📂 Extracting files..."
tar -xzf /tmp/deploy.tar.gz

# Copy app.py to main.py
cp app.py main.py

echo "🔄 Restarting service..."
systemctl restart sape-reports
sleep 3

# Check status
echo ""
echo "📊 Service status:"
systemctl status sape-reports --no-pager -l | head -15

echo ""
echo "✅ Deployment complete!"
echo "🌐 Login page: http://85.239.51.28:5007/login"
ENDSSH

echo ""
echo "✅ Deployment finished!"
echo ""
echo "📝 Default credentials:"
echo "   Login: a.bereznyak@sape.ru"
echo "   Password: sape2024"
echo ""
echo "🔐 All pages now require authentication"
echo "🌐 Test: http://85.239.51.28:5007"

# Cleanup
rm -rf "$TEMP_DIR"
