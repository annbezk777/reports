#!/usr/bin/env python3
"""
Sync campaigns for Lazurny Bereg account
"""
import sys
import os

# Change to script directory
os.chdir(os.path.dirname(os.path.abspath(__file__)))

# Import Flask app
from config import Config
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

# Initialize app and db
app = Flask(__name__)
app.config.from_object(Config)

from app.models import db, SapeAccount, Campaign, Client
db.init_app(app)

from app.api.sape_client import SapeAPIClient

def detect_campaign_format(campaign_name, sape_type=None):
    """Detect campaign format from name or SAPE API type"""
    if sape_type is not None:
        # SAPE API returns type as integer: 1=video, 2=banner, 3=banner, 4=CTV
        if isinstance(sape_type, int):
            type_map = {1: 'V', 2: 'B', 3: 'B', 4: 'CTV'}
            return type_map.get(sape_type, 'B')
        # Or as string
        elif isinstance(sape_type, str):
            type_map = {'video': 'V', 'banner': 'B', 'native': 'N', 'ctv': 'CTV'}
            return type_map.get(sape_type.lower(), 'B')

    name_lower = campaign_name.lower()
    if 'olv' in name_lower or 'видео' in name_lower or 'video' in name_lower:
        return 'V'
    elif 'ctv' in name_lower:
        return 'CTV'
    elif 'tgb' in name_lower or 'target' in name_lower:
        return 'TGB'
    return 'B'

with app.app_context():
    # Get Lazurny Bereg account
    account = SapeAccount.query.filter_by(name='Лазурный берег').first()

    if not account:
        print("❌ Account 'Лазурный берег' not found!")
        sys.exit(1)

    print(f"🔄 Syncing campaigns for: {account.name}")
    print(f"   Last sync: {account.last_sync}")

    # Initialize SAPE client
    client = SapeAPIClient(login=account.login, token=account.api_token)

    # Authenticate
    print(f"\n🔐 Authenticating...")
    if not client.authenticate():
        print(f"❌ Authentication failed!")
        sys.exit(1)

    print(f"✅ Authenticated!")

    # Get campaigns
    print(f"\n📥 Fetching campaigns from SAPE API...")
    campaigns_data = client.get_campaigns()

    if not campaigns_data:
        print(f"❌ No campaigns data returned")
        sys.exit(1)

    print(f"📋 Received {len(campaigns_data)} campaigns from API")

    # Sync campaigns
    synced_count = 0
    updated_count = 0
    new_campaigns = []

    for camp in campaigns_data:
        campaign_id = str(camp['id'])
        campaign_name = camp.get('name', f"Campaign {camp['id']}")

        # Get detailed campaign info
        campaign_detail = client.get_campaign_detail(camp['id'])
        sape_type = campaign_detail.get('type') if campaign_detail else None

        # Detect format
        format_type = detect_campaign_format(campaign_name, sape_type)

        # Check if campaign exists
        campaign = Campaign.query.filter_by(
            account_id=account.id,
            campaign_id=campaign_id
        ).first()

        if not campaign:
            campaign = Campaign(
                account_id=account.id,
                campaign_id=campaign_id,
                name=campaign_name,
                format_type=format_type
            )
            db.session.add(campaign)
            synced_count += 1
            new_campaigns.append(f"{campaign_id} - {campaign_name}")
        else:
            campaign.name = campaign_name
            campaign.format_type = format_type
            updated_count += 1

    # Update last sync time
    account.last_sync = datetime.utcnow()
    db.session.commit()

    print(f"\n✅ Sync complete!")
    print(f"   New campaigns: {synced_count}")
    print(f"   Updated campaigns: {updated_count}")

    if new_campaigns:
        print(f"\n📋 New campaigns added:")
        for nc in new_campaigns[:20]:  # Show first 20
            print(f"   - {nc}")
        if len(new_campaigns) > 20:
            print(f"   ... and {len(new_campaigns) - 20} more")

    # Check if 287322 is now in DB
    print(f"\n🔍 Checking for campaign 287322...")
    c287322 = Campaign.query.filter_by(campaign_id='287322').first()
    if c287322:
        print(f"✅ Campaign 287322 found: {c287322.name} (format: {c287322.format_type})")
    else:
        print(f"❌ Campaign 287322 still not in database")
