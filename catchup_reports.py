#!/usr/bin/env python3
"""
One-off catch-up: run every scheduled report's update ONE AT A TIME
(not in parallel), writing from its own last_update through yesterday -
same date-range logic run_report_update()/get_next_report_update_range()
already use for the normal scheduler, just triggered manually right now
instead of waiting for each report's own schedule_time to come around.

A small delay between reports avoids bursting the Google Sheets/SAPE
APIs with 38 near-simultaneous requests.
"""
import time

import importlib.util
spec = importlib.util.spec_from_file_location("sape_main_app", "app.py")
main = importlib.util.module_from_spec(spec)
spec.loader.exec_module(main)


def run():
    with main.app.app_context():
        reports = main.ReportConfig.query.filter_by(
            schedule_enabled=True, active=True, archived=False
        ).order_by(main.ReportConfig.id).all()
        print(f"Найдено {len(reports)} отчётов с автообновлением")

        updated = up_to_date = failed = 0
        for i, report in enumerate(reports, 1):
            name = report.name or (report.campaign.name if report.campaign else f"Отчёт #{report.id}")
            date_from, date_to = main.get_next_report_update_range(report)
            if date_from.date() > date_to.date():
                print(f"  [{i}/{len(reports)}] {report.id} {name}: уже актуален")
                up_to_date += 1
                continue
            print(f"  [{i}/{len(reports)}] {report.id} {name}: {date_from.date()} .. {date_to.date()}")
            try:
                ok = main.run_report_update(report)
                if ok:
                    updated += 1
                    print(f"      -> OK")
                else:
                    failed += 1
                    print(f"      -> FAILED (см. лог)")
            except Exception as e:
                failed += 1
                print(f"      -> ERROR: {e}")
            time.sleep(3)

        print(f"\nГотово. Обновлено: {updated}, уже актуальны: {up_to_date}, ошибок: {failed}")


if __name__ == '__main__':
    run()
