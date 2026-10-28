#!/usr/bin/env python3
"""
One-off backfill for task #22 (понедельная динамика): computes every
historical complete Mon-Sun week for every non-archived monitoring, from
its own campaign start through the last completed week - so the feature
doesn't start out empty for campaigns already in progress.

Safe to re-run: compute_monitoring_week_stats() upserts on
(monitoring_id, week_start), so an already-computed week just gets
overwritten with the same (or corrected) numbers, not duplicated.

Usage: venv/bin/python3 backfill_weekly_monitoring_stats.py
"""
import importlib.util
import logging
import os
import time
from datetime import timedelta

APP_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'app.py')
spec = importlib.util.spec_from_file_location("sape_main_app", APP_PATH)
main = importlib.util.module_from_spec(spec)
spec.loader.exec_module(main)


def monday_of(d):
    return d - timedelta(days=d.weekday())


def main_run():
    with main.app.app_context():
        import datetime as dt
        today = dt.date.today()
        last_monday, last_sunday = main.get_last_completed_week(today)

        monitorings = main.MonitoringCampaign.query.filter_by(archived=False).all()
        logging.info(f"📋 Backfilling weekly stats for {len(monitorings)} monitorings "
                     f"through week {last_monday}..{last_sunday}")

        total_weeks = 0
        failed_weeks = 0

        for monitoring in monitorings:
            week_start = monday_of(monitoring.date_from)
            weeks_for_this_monitoring = []
            while week_start <= last_monday:
                week_end = week_start + timedelta(days=6)
                weeks_for_this_monitoring.append((week_start, week_end))
                week_start += timedelta(days=7)

            if not weeks_for_this_monitoring:
                continue

            logging.info(f"🔄 {monitoring.id} {monitoring.name}: {len(weeks_for_this_monitoring)} weeks")
            for w_start, w_end in weeks_for_this_monitoring:
                try:
                    result = main.compute_monitoring_week_stats(monitoring, w_start, w_end)
                    if result:
                        total_weeks += 1
                        logging.info(f"   ✅ {w_start}..{w_end}: "
                                     f"показы={result.impressions}, клики={result.clicks}")
                    else:
                        failed_weeks += 1
                        logging.warning(f"   ⚠️ {w_start}..{w_end}: skipped (no account/campaigns)")
                except Exception as e:
                    failed_weeks += 1
                    logging.error(f"   ❌ {w_start}..{w_end}: {e}")
                time.sleep(1)

        logging.info(f"\n✅ BACKFILL COMPLETE: {total_weeks} weeks computed, {failed_weeks} failed/skipped")


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='%(message)s')
    main_run()
