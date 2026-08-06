#!/bin/bash
# Start local development server
# Usage: ./start_local.sh

set -e

echo "🚀 Запуск локального сервера..."

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "❌ Виртуальное окружение не найдено!"
    echo "Создаю виртуальное окружение..."
    python3 -m venv venv
    echo "✅ Виртуальное окружение создано"
fi

# Activate virtual environment
echo "🔧 Активация виртуального окружения..."
source venv/bin/activate

# Install dependencies if needed
echo "📦 Проверка зависимостей..."
pip3 install -q -r requirements.txt

# Check if server is already running
if lsof -Pi :5006 -sTCP:LISTEN -t >/dev/null ; then
    echo "⚠️ Сервер уже запущен на порту 5006"
    echo "Используйте ./stop_local.sh чтобы остановить его"
    exit 1
fi

# Start server
echo "▶️ Запуск сервера на http://localhost:5006"
python3 app.py &

# Save PID
echo $! > .local_server.pid

# Wait a bit and check if server started
sleep 2

if lsof -Pi :5006 -sTCP:LISTEN -t >/dev/null ; then
    echo "✅ Локальный сервер успешно запущен!"
    echo "🌐 Откройте в браузере: http://localhost:5006"
    echo "📋 Чтобы остановить сервер: ./stop_local.sh"
else
    echo "❌ Ошибка запуска сервера"
    echo "Проверьте логи для подробностей"
    exit 1
fi
