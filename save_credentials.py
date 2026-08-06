#!/usr/bin/env python3
"""
Save and restore SAPE account credentials
"""
import json
import os

CREDENTIALS_FILE = 'sape_credentials.json'

def save_credentials(name, login, token):
    """Save SAPE credentials to file"""
    data = {
        'name': name,
        'login': login,
        'token': token
    }

    with open(CREDENTIALS_FILE, 'w') as f:
        json.dump(data, f, indent=2)

    print(f"✅ Credentials saved to {CREDENTIALS_FILE}")

def restore_credentials():
    """Restore SAPE account from saved credentials"""
    if not os.path.exists(CREDENTIALS_FILE):
        print(f"❌ No credentials file found at {CREDENTIALS_FILE}")
        return None

    with open(CREDENTIALS_FILE, 'r') as f:
        data = json.load(f)

    print(f"✅ Loaded credentials for account: {data['name']}")
    return data

if __name__ == '__main__':
    import sys

    if len(sys.argv) < 2:
        print("Usage:")
        print("  Save: python save_credentials.py save <name> <login> <token>")
        print("  Load: python save_credentials.py load")
        sys.exit(1)

    command = sys.argv[1]

    if command == 'save' and len(sys.argv) == 5:
        save_credentials(sys.argv[2], sys.argv[3], sys.argv[4])
    elif command == 'load':
        creds = restore_credentials()
        if creds:
            print(f"Name: {creds['name']}")
            print(f"Login: {creds['login']}")
            print(f"Token: {creds['token']}")
    else:
        print("Invalid command or arguments")
