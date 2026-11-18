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
  - scheduled_refresh_all_monitorings(): daily at 09:00 Moscow
  - scheduled_compute_current_week_stats(): daily at 09:05 Moscow, right
    after the monitoring refresh above so its SAPE facts are fresh - the
    CURRENT, still-in-progress Mon-Sun week's numbers through yesterday
    (task #73), so the понедельная динамика table shows the week that's
    happening right now, updating day by day, instead of only appearing
    once scheduled_compute_weekly_monitoring_stats freezes it the
    following Monday. No-ops on Mondays themselves (today IS the new
    week's Monday - nothing of it has happened yet).
  - scheduled_refresh_weborama_verifiers(): daily at 09:30, retried once
    more at 09:40 - kept the same 30/40-minute offset from the monitoring
    refresh above when that moved from 08:00 to 09:00, since this job's
    own docstring requires running AFTER it (discrepancy % needs fresh
    SAPE facts). A transient failure (SAPE hiccup, Sheets/Weborama
    quota, etc.) used to mean that pixel just never got refreshed for
    the rest of the day. The function itself only touches links that
    haven't already succeeded today, so the 09:40 call after a
    successful 09:30 is a cheap no-op. Two tries is enough to tell a
    blip from a real problem - if still stale past 09:50, it stays stale
    until tomorrow - see needs_weborama_attention() in app.py for the
    dashboard/monitoring-card indicators that flag this. Note: on Mondays
    this now shares its 09:30 slot with scheduled_compute_weekly_monitoring_stats
    below - both still run (sequential within the same tick), just back
    to back instead of spaced apart.
  - scheduled_sync_all_accounts(): Mon-Fri at 09:00 Moscow
  - scheduled_compute_weekly_monitoring_stats(): Mon at 09:30 Moscow - after
    the other morning jobs so monitoring facts are fresh. Can run long
    (each Weborama-linked monitoring is a real ~20-25s browser session per
    verifier link) - that's fine once a week, but it does mean this tick
    blocks the next few ticks of scheduled_update_reports() until it's
    done; acceptable since that job just re-checks report schedules and
    isn't time-critical to the minute.

IMPORTANT: the web app's ENABLE_AUTO_SYNC must be "0" (not "1") once this
timer is running, or both this script AND the in-process scheduler would
fire the same jobs twice.

Task #91 - exact-minute triggers (hour==9 and minute==N) are fragile:
systemd refuses to start a second instance of this one-shot service
while a previous tick is still running, so if scheduled_refresh_all_
monitorings() (09:00) happens to take longer than usual (confirmed on
prod: 7+ minutes on 2026-11-17 instead of its usual ~1-2), every tick
that would fire WHILE it's still running - including the one single
minute an exact-minute check is watching for - is silently skipped
entirely, not delayed. That's exactly what caused понедельная
статистика to miss a whole day's update: the 09:05 tick for
scheduled_compute_current_week_stats() never ran because 09:00's job
was still occupying the service slot.

Fixed by widening each exact minute into a multi-minute (or multi-hour)
catch-up WINDOW, combined with a once-per-day marker file (same
disk-persisted-state idea as _REPORT_RETRY_COOLDOWN_FILE in app.py,
needed because scheduler_tick.py is a fresh process every single tick -
an in-memory flag would never survive between ticks) so a late tick
within the window still runs the job exactly once, instead of either
silently skipping it (narrow window) or re-running it every minute for
the rest of the window (no guard).
"""
import importlib.util
import json
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

_MARKER_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.scheduler_daily_markers.json')


def _load_markers():
    try:
        with open(_MARKER_FILE) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _save_markers(markers):
    tmp_path = _MARKER_FILE + '.tmp'
    with open(tmp_path, 'w') as f:
        json.dump(markers, f)
    os.replace(tmp_path, _MARKER_FILE)


def _run_once_per_day(job_key, day_str, fn):
    """Run fn() at most once per calendar day (MSK) for this job_key -
    see task #91 note above for why this exists. Call from inside a
    WIDENED catch-up window, not an exact-minute check, so a tick delayed
    by a still-running previous job can still catch it later in the same
    window without re-running it on every subsequent tick."""
    markers = _load_markers()
    if markers.get(job_key) == day_str:
        return
    fn()
    markers[job_key] = day_str
    _save_markers(markers)


def run_tick(now=None):
    if now is None:
        now = datetime.now(MOSCOW)
    logging.info(f"⏰ scheduler_tick at {now.strftime('%Y-%m-%d %H:%M:%S %Z')}")
    day_str = now.strftime('%Y-%m-%d')

    main.scheduled_update_reports()

    # Catch-up window 09:00-11:59 instead of an exact minute==0 check -
    # nothing precedes this one in the morning, but it's still cheap
    # insurance against e.g. a slow report-check tick stealing the exact
    # minute right before it.
    if now.hour in (9, 10, 11):
        _run_once_per_day('refresh_all_monitorings', day_str, main.scheduled_refresh_all_monitorings)

    # Catch-up window 09:05-11:59 (after the refresh above).
    if (now.hour == 9 and now.minute >= 5) or now.hour in (10, 11):
        _run_once_per_day('current_week_stats', day_str, main.scheduled_compute_current_week_stats)

    # Two attempts, each its own once-per-day marker so the 2-retry
    # design is preserved - just each attempt now tolerates a few
    # minutes of scheduling jitter instead of needing its exact minute.
    if now.hour == 9 and 30 <= now.minute <= 36:
        _run_once_per_day('weborama_attempt1', day_str, main.scheduled_refresh_weborama_verifiers)
    if now.hour == 9 and 40 <= now.minute <= 46:
        _run_once_per_day('weborama_attempt2', day_str, main.scheduled_refresh_weborama_verifiers)

    if now.isoweekday() <= 5 and now.hour in (9, 10, 11):
        _run_once_per_day('sync_all_accounts', day_str, main.scheduled_sync_all_accounts)

    if now.isoweekday() == 1 and ((now.hour == 9 and now.minute >= 30) or now.hour in (10, 11)):
        _run_once_per_day('weekly_freeze', day_str, main.scheduled_compute_weekly_monitoring_stats)


if __name__ == '__main__':
    run_tick()
