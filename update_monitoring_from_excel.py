#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Universal script to update any monitoring with IVT data from Adriver Excel export
"""

import sys
import os

# Add current directory to path
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

from flask import Flask
from config import Config
from app.models import db, MonitoringCampaign
from parse_adriver_excel import AdriverExcelParser

app = Flask(__name__)
app.config.from_object(Config)
db.init_app(app)


def update_monitoring_from_excel(monitoring_name, excel_file_path):
    """
    Update monitoring with IVT data from Adriver Excel export

    Args:
        monitoring_name: Name pattern of monitoring (e.g., "Rossko" will match "AlfaDigital // Rossko октябрь")
        excel_file_path: Path to Adriver Excel export file
    """
    with app.app_context():
        # Find monitoring
        monitorings = MonitoringCampaign.query.filter(
            MonitoringCampaign.name.like(f'%{monitoring_name}%')
        ).all()

        if not monitorings:
            print(f"❌ No monitoring found matching: {monitoring_name}")
            return False

        if len(monitorings) > 1:
            print(f"⚠️  Found {len(monitorings)} monitorings matching '{monitoring_name}':")
            for i, m in enumerate(monitorings, 1):
                print(f"   {i}. {m.name} (ID: {m.id})")

            choice = input("\nEnter number to select (or 'all' for all): ").strip()

            if choice.lower() == 'all':
                selected_monitorings = monitorings
            else:
                try:
                    idx = int(choice) - 1
                    selected_monitorings = [monitorings[idx]]
                except:
                    print("❌ Invalid choice")
                    return False
        else:
            selected_monitorings = monitorings

        # Parse Excel file
        parser = AdriverExcelParser(excel_file_path)
        ivt_data = parser.parse()

        if not ivt_data:
            print("❌ Failed to parse Excel file")
            return False

        # Update each monitoring
        print("\n" + "="*60)
        for monitoring in selected_monitorings:
            print(f"\n📝 Updating: {monitoring.name}")
            print("="*60)

            # Update fact data
            monitoring.fact_impressions = ivt_data['impressions']
            monitoring.fact_clicks = ivt_data['clicks']
            monitoring.fact_ivt_impressions = ivt_data['ivt_impressions_percent']
            monitoring.fact_givt_impressions = ivt_data['givt_impressions_percent']
            monitoring.fact_sivt_impressions = ivt_data['sivt_impressions_percent']
            monitoring.fact_givt_clicks = ivt_data['givt_clicks_percent']

            print(f"\n✅ Updated:")
            print(f"   Показы: {ivt_data['impressions']:,}")
            print(f"   Клики: {ivt_data['clicks']:,}")
            print(f"   IVT: {ivt_data['ivt_impressions_percent']}%")
            print(f"   GIVT показы: {ivt_data['givt_impressions_percent']}%")
            print(f"   SIVT показы: {ivt_data['sivt_impressions_percent']}%")
            print(f"   GIVT клики: {ivt_data['givt_clicks_percent']}%")

        # Commit all changes
        try:
            db.session.commit()
            print("\n" + "="*60)
            print(f"✅ Successfully updated {len(selected_monitorings)} monitoring(s)!")
            print("="*60)
            return True
        except Exception as e:
            db.session.rollback()
            print(f"\n❌ Error committing to database: {e}")
            return False


def main():
    """Main function"""
    if len(sys.argv) < 3:
        print("📋 Usage:")
        print("   python update_monitoring_from_excel.py <monitoring_name> <excel_file_path>")
        print("\nExamples:")
        print("   python update_monitoring_from_excel.py 'Rossko' '/path/to/rossko_stats.xlsx'")
        print("   python update_monitoring_from_excel.py 'Аэрофлот' '/path/to/aeroflot_stats.xlsx'")
        print("   python update_monitoring_from_excel.py 'Теле2' '/path/to/tele2_stats.xlsx'")
        return

    monitoring_name = sys.argv[1]
    excel_file_path = sys.argv[2]

    if not os.path.exists(excel_file_path):
        print(f"❌ File not found: {excel_file_path}")
        return

    print(f"🚀 Updating monitoring with IVT data")
    print(f"   Monitoring: {monitoring_name}")
    print(f"   Excel file: {excel_file_path}\n")

    update_monitoring_from_excel(monitoring_name, excel_file_path)


if __name__ == '__main__':
    main()
