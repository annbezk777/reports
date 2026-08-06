#!/usr/bin/env python3
"""
Create Lazurny Bereg video report
"""
import sys
import os
os.chdir(os.path.dirname(os.path.abspath(__file__)))

from config import Config
from flask import Flask
from datetime import datetime

app = Flask(__name__)
app.config.from_object(Config)

from app.models import db, SapeAccount, Campaign, ReportConfig
db.init_app(app)

with app.app_context():
    # Find campaigns 287316 and 287317
    campaigns = Campaign.query.filter(
        Campaign.campaign_id.in_(['287316', '287317'])
    ).all()

    if len(campaigns) != 2:
        print(f"❌ Found {len(campaigns)} campaigns, need 2!")
        for c in campaigns:
            print(f"   - {c.campaign_id}: {c.name}")
        sys.exit(1)

    print(f"✅ Found campaigns:")
    for c in campaigns:
        print(f"   - {c.campaign_id}: {c.name} (format: {c.format_type})")

    campaign_ids = [c.id for c in campaigns]

    # Check if report exists
    existing = ReportConfig.query.filter_by(name='Лазурный берег видео Июнь').first()
    if existing:
        print(f"\n⚠️ Report already exists! ID: {existing.id}")
        print(f"   URL: {existing.google_sheet_url}")
        print(f"   Worksheet: {existing.worksheet_name}")
        print(f"   Campaign IDs in report: {existing.campaign_ids}")
        print(f"\nUpdating campaign IDs...")
        existing.campaign_ids = campaign_ids
        existing.campaign_id = campaign_ids[0]
        db.session.commit()
        print(f"✅ Updated!")
    else:
        # Create new report
        report = ReportConfig(
            name='Лазурный берег видео Июнь',
            campaign_id=campaign_ids[0],
            campaign_ids=campaign_ids,
            campaign_mode='separate',
            google_sheet_url='https://docs.google.com/spreadsheets/d/1113IvK_20s...',  # REPLACE
            worksheet_name='Баннеры_июнь',  # REPLACE
            active=True,
            created_at=datetime.utcnow()
        )
        db.session.add(report)
        db.session.commit()
        print(f"\n✅ Report created! ID: {report.id}")

    print(f"\n📋 All reports in DB:")
    all_reports = ReportConfig.query.order_by(ReportConfig.id).all()
    for r in all_reports:
        print(f"   {r.id}. {r.name} - {len(r.campaign_ids)} campaigns")
