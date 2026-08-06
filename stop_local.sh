#!/bin/bash
# Stop local development server
# Usage: ./stop_local.sh

echo "🛑 Остановка локального сервера..."

# Find and kill process on port 5006
PID=$(lsof -ti:5006)

if [ -z "$PID" ]; then
    echo "⚠️ Сервер не запущен на порту 5006"
    exit 0
fi

kill $PID 2>/dev/null

# Wait a bit
sleep 1

# Check if killed
if lsof -Pi :5006 -sTCP:LISTEN -t >/dev/null 2>&1 ; then
    echo "⚠️ Сервер не остановился, принудительная остановка..."
    kill -9 $PID 2>/dev/null
    sleep 1
fi

# Final check
if lsof -Pi :5006 -sTCP:LISTEN -t >/dev/null 2>&1 ; then
    echo "❌ Не удалось остановить сервер"
    exit 1
else
    echo "✅ Локальный сервер остановлен"
    # Remove PID file if exists
    rm -f .local_server.pid
fi
