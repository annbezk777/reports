#!/usr/bin/env python3
"""
Restore SAPE accounts after database reset
"""
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
import os

# Import from app.py
import sys
sys.path.insert(0, os.path.dirname(__file__))

# Create Flask app and db
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///sape_reports.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# Import model
from app.models import SapeAccount

# Account credentials
ACCOUNTS = [
    {
        'name': 'Full Media PPL',
        'login': 'full_media_ppl@sape.ru',
        'api_token': '4e160b4d832182f06c669268a8835b448b4e0b0b6bfb54e6072925a6bcabc304'
    },
    {
        'name': 'Full StargeIT',
        'login': 'full-stargeit@sape.ru',
        'api_token': '15ef0145b28c2678aa9275d331cc6856ef184d6099f785986feed5324d83e97b'
    },
    {
        'name': 'Full Advelop',
        'login': 'full_advelop@sape.ru',
        'api_token': '19d5b488099189d49df4cf9357e65082baaf3f2d97a329db58ce2ce650b4d2b3'
    }
]

def restore_accounts():
    """Restore all SAPE accounts to database"""
    with app.app_context():
        print("🔄 Restoring SAPE accounts...")

        for acc_data in ACCOUNTS:
            # Check if account already exists
            existing = SapeAccount.query.filter_by(login=acc_data['login']).first()

            if existing:
                print(f"✅ Account already exists: {acc_data['name']} ({acc_data['login']})")
            else:
                account = SapeAccount(
                    name=acc_data['name'],
                    login=acc_data['login'],
                    api_token=acc_data['api_token'],
                    active=True
                )
                db.session.add(account)
                print(f"✅ Created account: {acc_data['name']} ({acc_data['login']})")

        db.session.commit()
        print("\n✅ All accounts restored successfully!")

if __name__ == '__main__':
    restore_accounts()
