#!/bin/bash
# Prepare files for production deployment
# This script creates a deployment package

set -e

echo "📦 Подготовка файлов для продакшен..."

# Create deployment directory
DEPLOY_DIR="/tmp/deploy_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$DEPLOY_DIR"

echo "📁 Копирование обновленных файлов..."

# Copy updated files preserving directory structure
mkdir -p "$DEPLOY_DIR/app/api"
mkdir -p "$DEPLOY_DIR/app/templates"

cp "app/api/google_sheets_client.py" "$DEPLOY_DIR/app/api/"
cp "app.py" "$DEPLOY_DIR/"
cp "app/templates/edit_report.html" "$DEPLOY_DIR/app/templates/"
cp "app/models.py" "$DEPLOY_DIR/app/"

# Copy migration files
cp "/tmp/migrate_reach_settings_production.sh" "$DEPLOY_DIR/"
cp "/tmp/migration.sql" "$DEPLOY_DIR/"

# Create deployment instructions
cat > "$DEPLOY_DIR/DEPLOY.sh" <<'EOF'
#!/bin/bash
# Run this script on production server
# Usage: ./DEPLOY.sh

set -e

echo "🚀 Deploying to production..."

# Backup current files
BACKUP_DIR="backups/backup_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BACKUP_DIR/app/api"
mkdir -p "$BACKUP_DIR/app/templates"

echo "📦 Creating backup in $BACKUP_DIR..."
cp app/api/google_sheets_client.py "$BACKUP_DIR/app/api/" 2>/dev/null || true
cp app.py "$BACKUP_DIR/" 2>/dev/null || true
cp app/templates/edit_report.html "$BACKUP_DIR/app/templates/" 2>/dev/null || true
cp app/models.py "$BACKUP_DIR/app/" 2>/dev/null || true

# Copy new files
echo "📝 Copying new files..."
cp app/api/google_sheets_client.py app/api/
cp app.py .
cp app/templates/edit_report.html app/templates/
cp app/models.py app/

# Apply migration
echo "🗄️ Applying database migration..."
chmod +x migrate_reach_settings_production.sh
./migrate_reach_settings_production.sh

# Restart gunicorn
echo "🔄 Restarting Gunicorn..."
sudo systemctl restart gunicorn

# Check status
sleep 2
sudo systemctl status gunicorn --no-pager

echo "✅ Deployment complete!"
echo "📦 Backup saved in: $BACKUP_DIR"
echo "🌐 Check: http://85.239.51.28:5007"
EOF

chmod +x "$DEPLOY_DIR/DEPLOY.sh"

# Create deployment package
cd /tmp
ARCHIVE_NAME="deploy_$(date +%Y%m%d_%H%M%S).tar.gz"
tar -czf "$ARCHIVE_NAME" -C "$DEPLOY_DIR" .

echo ""
echo "✅ Пакет готов: /tmp/$ARCHIVE_NAME"
echo ""
echo "═══════════════════════════════════════════════════════════"
echo "  📤 КАК РАЗВЕРНУТЬ НА ПРОДАКШЕН"
echo "═══════════════════════════════════════════════════════════"
echo ""
echo "1️⃣  Скопируйте архив на сервер:"
echo "   scp /tmp/$ARCHIVE_NAME user@85.239.51.28:/tmp/"
echo ""
echo "2️⃣  Подключитесь к серверу:"
echo "   ssh user@85.239.51.28"
echo ""
echo "3️⃣  Распакуйте и запустите деплой:"
echo "   cd /path/to/api_google_sheets"
echo "   tar -xzf /tmp/$ARCHIVE_NAME"
echo "   ./DEPLOY.sh"
echo ""
echo "═══════════════════════════════════════════════════════════"
echo ""
echo "Или одной командой (после scp):"
echo "ssh user@85.239.51.28 'cd /path/to/api_google_sheets && tar -xzf /tmp/$ARCHIVE_NAME && ./DEPLOY.sh'"
echo ""

# Keep deploy dir for reference
echo "📁 Файлы также доступны в: $DEPLOY_DIR"
