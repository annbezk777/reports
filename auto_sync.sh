#!/bin/bash
# Auto-sync script - runs sync every N minutes
# Usage: ./auto_sync.sh [interval_minutes]

INTERVAL_MINUTES=${1:-30}  # Default 30 minutes
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

echo "🔄 Starting auto-sync service..."
echo "   Interval: every $INTERVAL_MINUTES minutes"
echo "   Press Ctrl+C to stop"
echo ""

while true; do
    echo "$(date '+%Y-%m-%d %H:%M:%S') - Running sync..."

    cd "$SCRIPT_DIR"
    python3 sync_from_server.py

    if [ $? -eq 0 ]; then
        echo "✅ Sync completed successfully"
    else
        echo "❌ Sync failed"
    fi

    echo ""
    echo "⏰ Next sync in $INTERVAL_MINUTES minutes..."
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""

    sleep $((INTERVAL_MINUTES * 60))
done
