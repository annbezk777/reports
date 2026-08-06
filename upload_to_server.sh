#!/bin/bash
SERVER="annbezk@85.239.51.28"
REMOTE_PATH="/home/annbezk/api_google_sheets"

echo "Uploading fixed files to server..."

# Upload google_sheets_client.py
scp app/api/google_sheets_client.py $SERVER:$REMOTE_PATH/app/api/

# Upload app.py
scp app.py $SERVER:$REMOTE_PATH/

echo "Files uploaded! Now restart server on remote:"
echo "ssh $SERVER"
echo "cd $REMOTE_PATH"
echo "pkill -f 'python.*app.py'"
echo "nohup python3 app.py > server.log 2>&1 &"
