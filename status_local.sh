#!/bin/bash
# Check status of local development server
# Usage: ./status_local.sh

echo "📊 Статус локального сервера"
echo "=============================="

# Check if running
if lsof -Pi :5006 -sTCP:LISTEN -t >/dev/null 2>&1 ; then
    echo "✅ Статус: ЗАПУЩЕН"
    echo "🌐 URL: http://localhost:5006"
    echo ""
    echo "Процессы:"
    lsof -Pi :5006 -sTCP:LISTEN
    echo ""
    echo "Для остановки: ./stop_local.sh"
else
    echo "❌ Статус: НЕ ЗАПУЩЕН"
    echo ""
    echo "Для запуска: ./start_local.sh"
fi
