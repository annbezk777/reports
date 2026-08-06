#!/usr/bin/env python3
"""
Initialize database and restore accounts
"""
import os
import sys

# Set up path
sys.path.insert(0, os.path.dirname(__file__))

# Import Flask app
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

# Configuration
DATABASE_URI = 'sqlite:///sape_reports.db'

# Create Flask app
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URI
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'dev-secret-key-change-in-production'

# Initialize database
db = SQLAlchemy(app)

# Import models AFTER db is created
from app.models import SapeAccount, Campaign, ReportConfig, ReportLog

# Account credentials to restore
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

def init_database():
    """Initialize database and restore accounts"""
    with app.app_context():
        print("🔄 Creating database tables...")
        db.create_all()
        print("✅ Database tables created!")

        print("\n🔄 Restoring SAPE accounts...")
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
                    active=True,
                    created_at=datetime.utcnow()
                )
                db.session.add(account)
                print(f"✅ Created account: {acc_data['name']} ({acc_data['login']})")

        db.session.commit()
        print("\n✅ All accounts restored successfully!")
        print("\nТеперь можете синхронизировать кампании: http://localhost:5006/accounts")

if __name__ == '__main__':
    init_database()
