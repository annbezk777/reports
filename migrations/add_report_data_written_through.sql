-- report.last_update is a wall-clock "when was Обновить last clicked"
-- timestamp shown in the UI (reports.html) - it is NOT the same as
-- "through which date is data actually written in the sheet". A manual
-- one-off run for a single past day sets last_update to today even
-- though it only wrote that one day, which made get_next_report_update_range()
-- skip the real gap on the next scheduled run. This column tracks the
-- real high-water mark (date_to of whatever range was actually written)
-- separately, so the scheduler always resumes right after it.
ALTER TABLE report_configs ADD COLUMN data_written_through DATE;
