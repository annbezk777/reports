#!/usr/bin/env python3
"""
One-off backfill: scope adriver_fact_impressions/clicks to an approximate
as-of-date for existing Adriver/Sizmek uploads that predate the file-date
parsing fix (AdriverExcelParser._find_last_date), so the "Расхождения с
верификаторами" discrepancy % stops comparing SAPE's fact (refreshed
through yesterday by the scheduler) against an older verifier file.

Only touches monitorings with a linked report (report_config_id set) -
"кампании с отчетами" per the task. The exact day the old file covered is
lost (we no longer have the original file) - this approximates
data_as_of_date as the Moscow calendar date of adriver_data_updated_at
minus 1 day. It's a heuristic, not exact; the next real Adriver re-upload
replaces it with the actual parsed date via the now-fixed upload endpoint.

Safe to re-run - only processes rows where adriver_data_as_of_date is
still NULL, so already-backfilled or freshly-uploaded rows are untouched.
"""
from datetime import datetime, timedelta

import pytz
from flask import Flask

from config import Config
from app.models import db, MonitoringCampaign
from app.api.sape_client import SapeAPIClient

app = Flask(__name__)
app.config.from_object(Config)
db.init_app(app)

MOSCOW = pytz.timezone('Europe/Moscow')


def scoped_sape_fact(monitoring, as_of_date):
    campaigns = monitoring.get_campaigns()
    if not campaigns:
        return None
    account = monitoring.account
    if not account or not account.api_token:
        return None
    date_from = monitoring.adriver_compare_date_from or monitoring.date_from
    date_to = min(as_of_date, monitoring.date_to)
    if date_from > date_to:
        return None
    client = SapeAPIClient(login=account.login, token=account.api_token)
    if not client.authenticate():
        return None
    stats = client.get_stats(
        campaign_ids=[int(c.campaign_id) for c in campaigns],
        date_from=datetime.combine(date_from, datetime.min.time()),
        date_to=datetime.combine(date_to, datetime.min.time()),
        fields=None
    )
    if not stats:
        return None
    return stats.get('total', {})


def main():
    with app.app_context():
        monitorings = MonitoringCampaign.query.filter(
            MonitoringCampaign.adriver_impressions.isnot(None),
            MonitoringCampaign.report_config_id.isnot(None),
            MonitoringCampaign.adriver_data_as_of_date.is_(None),
            MonitoringCampaign.adriver_data_updated_at.isnot(None),
            MonitoringCampaign.archived == False,
        ).all()
        print(f"Найдено {len(monitorings)} мониторингов для бэкфилла")

        updated = skipped = errors = 0
        for mo in monitorings:
            approx_date = pytz.utc.localize(mo.adriver_data_updated_at).astimezone(MOSCOW).date() - timedelta(days=1)
            try:
                total = scoped_sape_fact(mo, approx_date)
            except Exception as e:
                print(f"  [{mo.id}] {mo.name}: ошибка SAPE API: {e}")
                errors += 1
                continue
            if total is None:
                print(f"  [{mo.id}] {mo.name}: нет кампаний/токена/периода - пропуск")
                skipped += 1
                continue
            mo.adriver_data_as_of_date = approx_date
            mo.adriver_fact_impressions = total.get('shows', 0)
            mo.adriver_fact_clicks = total.get('clicks', 0)
            print(f"  [{mo.id}] {mo.name}: as_of~{approx_date} (приближение), "
                  f"scoped SAPE факт показы={mo.adriver_fact_impressions}, клики={mo.adriver_fact_clicks}")
            updated += 1
            db.session.commit()

        print(f"\nГотово. Обновлено: {updated}, пропущено: {skipped}, ошибок: {errors}")


if __name__ == '__main__':
    main()
