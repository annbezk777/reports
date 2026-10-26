#!/usr/bin/env python3
"""
Standalone scheduler tick, meant to be run once a minute by an external
systemd timer (sape-reports-scheduler.timer), NOT by the gunicorn-hosted
web app.

Why this exists: the old scheduler lived in-process inside ONE gunicorn
worker, picked via a non-blocking file lock (see the ENABLE_AUTO_SYNC
block in app.py). Each worker only ever tries to acquire that lock ONCE,
at startup - if it loses the race (because the previous lock-holder
hadn't died yet during a rolling `systemctl reload`), it gives up
permanently. The lock-holder dying on any later reload then left NO
worker running the scheduler, silently, with nothing in the logs to
flag it. This is exactly what caused ~36 scheduled reports to go
un-updated from 2026-10-19 to 2026-10-25/26.

A systemd timer is a separate process entirely decoupled from gunicorn's
worker lifecycle, so it can't be killed off by a web app reload. Run
this directly - it imports app.py (not the app/ package - see the
importlib trick below, same as app.py's own wsgi.py loader) and performs
exactly the checks the old in-process scheduler.add_job() calls did,
once, then exits:
  - scheduled_update_reports(): every tick (each report checks its own
    schedule_time/schedule_days internally)
  - scheduled_refresh_all_monitorings(): daily at 08:00 Moscow
  - scheduled_refresh_weborama_verifiers(): daily at 08:30 Moscow
  - scheduled_sync_all_accounts(): Mon-Fri at 09:00 Moscow

IMPORTANT: the web app's ENABLE_AUTO_SYNC must be "0" (not "1") once this
timer is running, or both this script AND the in-process scheduler would
fire the same jobs twice.
"""
import importlib.util
import logging
import os
import sys
from datetime import datetime

import pytz

APP_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'app.py')

spec = importlib.util.spec_from_file_location("sape_main_app", APP_PATH)
main = importlib.util.module_from_spec(spec)
spec.loader.exec_module(main)

MOSCOW = pytz.timezone('Europe/Moscow')


def run_tick():
    now = datetime.now(MOSCOW)
    logging.info(f"⏰ scheduler_tick at {now.strftime('%Y-%m-%d %H:%M:%S %Z')}")

    main.scheduled_update_reports()

    if now.hour == 8 and now.minute == 0:
        main.scheduled_refresh_all_monitorings()

    if now.hour == 8 and now.minute == 30:
        main.scheduled_refresh_weborama_verifiers()

    if now.isoweekday() <= 5 and now.hour == 9 and now.minute == 0:
        main.scheduled_sync_all_accounts()


if __name__ == '__main__':
    run_tick()
