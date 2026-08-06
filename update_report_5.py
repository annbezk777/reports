#!/usr/bin/env python3
"""
Quick script to update report #5 (Stroydvor) with new frequency settings
"""
import sys
import os
from datetime import datetime, timedelta

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import from app.py (main application file)
import app as app_module
app = app_module.app
db = app_module.db

from app.models import ReportConfig, Campaign, SapeAccount, ReportLog
from app.api.sape_client import SapeAPIClient
from app.api.google_sheets_client import GoogleSheetsClient

def update_stroydvor_report():
    """Update Stroydvor report #5"""
    with app.app_context():
        # Get report
        report = ReportConfig.query.get(5)
        if not report:
            print("❌ Report #5 not found!")
            return False

        print(f"📊 Updating report: {report.name}")
        print(f"   Campaign mode: {report.campaign_mode}")
        print(f"   Campaigns: {report.campaign_ids}")

        # Get campaigns
        campaigns = Campaign.query.filter(Campaign.id.in_(report.campaign_ids)).all()
        if not campaigns:
            print("❌ No campaigns found!")
            return False

        print(f"   Found {len(campaigns)} campaigns")

        # Print frequency settings
        print(f"\n📊 Frequency settings:")
        for campaign in campaigns:
            cid_str = str(campaign.id)
            if report.campaign_settings and cid_str in report.campaign_settings:
                settings = report.campaign_settings[cid_str]
                print(f"   Campaign {campaign.campaign_id} ({campaign.name}):")
                print(f"     daily_frequency: {settings.get('daily_frequency')}")
                print(f"     daily_variance: {settings.get('daily_variance')}")
                print(f"     total_frequency: {settings.get('total_frequency')}")
                print(f"     total_variance: {settings.get('total_variance')}")

        # Get account
        account = campaigns[0].account
        print(f"\n🔐 Using account: {account.login}")

        # Initialize SAPE client
        sape_client = SapeAPIClient(login=account.login, token=account.api_token)
        if not sape_client.authenticate():
            print("❌ SAPE authentication failed!")
            return False

        print("✅ SAPE authenticated")

        # Date range: May 1-10
        date_from = datetime(2026, 5, 1)
        date_to = datetime(2026, 5, 10)

        print(f"\n📅 Date range: {date_from.strftime('%Y-%m-%d')} to {date_to.strftime('%Y-%m-%d')}")

        # Initialize Google Sheets client
        gs_client = GoogleSheetsClient(
            credentials_file='google_credentials.json',
            scopes=['https://www.googleapis.com/auth/spreadsheets']
        )

        if not gs_client.authenticate():
            print("❌ Google Sheets authentication failed!")
            return False

        print("✅ Google Sheets authenticated")

        # Open worksheet once for caching
        print(f"\n📖 Opening worksheet: '{report.worksheet_name}'")
        cached_worksheet = gs_client.get_worksheet_object(
            sheet_url=report.google_sheet_url,
            sheet_name=report.worksheet_name
        )

        if not cached_worksheet:
            print("❌ Failed to open worksheet!")
            return False

        # Read data once
        cached_data = cached_worksheet.get('A1:DZ150')
        print(f"✅ Cached {len(cached_data)} rows")

        # Process each campaign (SEPARATE mode)
        total_impressions = 0
        total_clicks = 0
        sections_updated = 0

        for idx, campaign in enumerate(campaigns, 1):
            print(f"\n🔍 [{idx}/{len(campaigns)}] Processing campaign {campaign.campaign_id} ({campaign.name})")

            # Find structure for this campaign
            all_structures = gs_client.auto_detect_all_structures(
                sheet_url=report.google_sheet_url,
                sheet_name=report.worksheet_name,
                campaign_id=str(campaign.campaign_id),
                cached_data=cached_data
            )

            if not all_structures:
                print(f"❌ Structure not found for campaign {campaign.campaign_id}")
                continue

            structure = all_structures[0]
            print(f"✅ Found structure at row {structure['header_row']}")

            # Get daily stats
            is_video = campaign.format_type in ['V', 'CTV']
            daily_data = sape_client.get_daily_stats(
                campaign_ids=[int(campaign.campaign_id)],
                date_from=date_from,
                date_to=date_to,
                include_video_metrics=is_video
            )

            if not daily_data:
                print(f"⚠️ No data from SAPE API")
                continue

            print(f"✅ Got {len(daily_data)} days of data")

            # Get frequency settings
            cid_str = str(campaign.id)
            if report.campaign_settings and cid_str in report.campaign_settings:
                settings = report.campaign_settings[cid_str]
                daily_frequency = settings.get('daily_frequency', 3.0)
                daily_variance = settings.get('daily_variance', 0.1)
                total_frequency = settings.get('total_frequency', 3.0)
                total_variance = settings.get('total_variance', 0.1)
            else:
                daily_frequency = 3.0
                daily_variance = 0.1
                total_frequency = 3.0
                total_variance = 0.1

            print(f"📊 Using settings:")
            print(f"   Daily: freq={daily_frequency}, var={daily_variance}")
            print(f"   Total: freq={total_frequency}, var={total_variance}")

            # Prepare column mapping
            column_mapping = {
                'date_column': structure['date_column'],
                'impressions_column': structure['impressions_column'],
                'reach_column': structure['reach_column'],
                'clicks_column': structure['clicks_column'],
                'ctr_column': structure['ctr_column']
            }

            # Write data
            success = gs_client.write_daily_data(
                sheet_url=report.google_sheet_url,
                sheet_name=report.worksheet_name,
                daily_data=daily_data,
                column_mapping=column_mapping,
                data_start_row=structure['data_start_row'],
                daily_frequency=daily_frequency,
                daily_variance=daily_variance,
                total_frequency=total_frequency,
                total_variance=total_variance,
                cached_worksheet=cached_worksheet
            )

            if success:
                print(f"✅ Updated section for campaign {campaign.campaign_id}")
                sections_updated += 1
                total_impressions += sum(d['impressions'] for d in daily_data)
                total_clicks += sum(d['clicks'] for d in daily_data)
            else:
                print(f"❌ Failed to update section")

        # Log success
        if sections_updated > 0:
            avg_ctr = round(total_clicks / total_impressions * 100, 2) if total_impressions > 0 else 0
            metrics = {
                'total_impressions': total_impressions,
                'total_clicks': total_clicks,
                'avg_ctr': avg_ctr,
                'days_updated': len(daily_data) if daily_data else 0,
                'campaigns_updated': sections_updated
            }

            log = ReportLog(
                report_config_id=report.id,
                status='success',
                metrics=metrics
            )
            db.session.add(log)

            report.last_update = datetime.utcnow()
            db.session.commit()

            print(f"\n✅ Update complete!")
            print(f"   Campaigns updated: {sections_updated}/{len(campaigns)}")
            print(f"   Total impressions: {total_impressions:,}")
            print(f"   Total clicks: {total_clicks:,}")
            print(f"   Avg CTR: {avg_ctr}%")
            return True
        else:
            print(f"\n❌ No sections updated!")
            return False

if __name__ == '__main__':
    success = update_stroydvor_report()
    sys.exit(0 if success else 1)
