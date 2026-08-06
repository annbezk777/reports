#!/bin/bash
# Deploy critical fixes to server

SERVER="annbezk@85.239.51.28"
PASSWORD="Bereznysk23"

echo "🚀 Deploying fixes to $SERVER..."

# Use sshpass if available, otherwise manual
if command -v sshpass &> /dev/null; then
    echo "Using sshpass for authentication..."

    # Find project path on server
    echo "1️⃣ Finding project path..."
    PROJECT_PATH=$(sshpass -p "$PASSWORD" ssh -o StrictHostKeyChecking=no $SERVER "find /home /root -name 'app.py' -path '*/api_google*' 2>/dev/null | head -1 | xargs dirname" 2>/dev/null)

    if [ -z "$PROJECT_PATH" ]; then
        echo "❌ Project not found on server!"
        exit 1
    fi

    echo "✅ Found project: $PROJECT_PATH"

    # Upload files
    echo "2️⃣ Uploading fixed files..."
    sshpass -p "$PASSWORD" scp -o StrictHostKeyChecking=no app/api/google_sheets_client.py $SERVER:$PROJECT_PATH/app/api/
    sshpass -p "$PASSWORD" scp -o StrictHostKeyChecking=no app.py $SERVER:$PROJECT_PATH/

    # Restart server
    echo "3️⃣ Restarting server..."
    sshpass -p "$PASSWORD" ssh -o StrictHostKeyChecking=no $SERVER "cd $PROJECT_PATH && pkill -f 'python.*app.py' && nohup python3 app.py > server.log 2>&1 &"

    echo "✅ Deployment complete!"
else
    echo "⚠️ sshpass not found. Manual deployment required."
    echo ""
    echo "Run these commands manually:"
    echo ""
    echo "# Upload files (enter password when prompted)"
    echo "scp app/api/google_sheets_client.py $SERVER:/path/to/project/app/api/"
    echo "scp app.py $SERVER:/path/to/project/"
    echo ""
    echo "# SSH to server"
    echo "ssh $SERVER"
    echo "cd /path/to/project"
    echo "pkill -f 'python.*app.py'"
    echo "nohup python3 app.py > server.log 2>&1 &"
fi
