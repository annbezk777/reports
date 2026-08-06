#!/bin/bash
# Restart local development server
# Usage: ./restart_local.sh

echo "🔄 Перезапуск локального сервера..."

# Stop server
./stop_local.sh

# Wait a bit
sleep 1

# Start server
./start_local.sh
