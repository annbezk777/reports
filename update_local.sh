#!/bin/bash

# 🔄 Скрипт обновления локальной версии
# Использовать после успешного деплоя на продакшен-сервер

set -e  # Остановиться при ошибке

echo "🔄 Обновление локальной версии..."

# Перейти в директорию проекта
cd "/Users/annabereznyak/api_google_sheets"

echo "📥 Получение последних изменений из GitHub..."
git pull origin main

echo "📦 Обновление зависимостей (если изменились)..."
source venv/bin/activate
pip install -r requirements.txt --upgrade --quiet

echo "🔄 Перезапуск локального сервера..."

# Остановить текущий сервер
if pgrep -f "python.*app.py" > /dev/null; then
    echo "⏹️  Останавливаем текущий сервер..."
    pkill -f "python.*app.py" || true
    sleep 2
fi

# Запустить сервер в фоне
echo "▶️  Запускаем обновленный сервер..."
nohup venv/bin/python3 app.py > server_local.log 2>&1 &

sleep 3

# Проверить что сервер запустился
if pgrep -f "python.*app.py" > /dev/null; then
    echo "✅ Локальный сервер обновлен и запущен!"
    echo "🌐 Доступен по адресу: http://127.0.0.1:5006/reports"
    echo ""
    echo "📋 Проверить статус: ./status_local.sh"
    echo "📄 Посмотреть логи: tail -f server_local.log"
else
    echo "❌ Ошибка запуска сервера!"
    echo "📄 Проверьте логи: tail -f server_local.log"
    exit 1
fi
