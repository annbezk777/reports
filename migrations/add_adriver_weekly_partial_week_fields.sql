-- Mirrors the Weborama partial-week fields so the Adriver weekly
-- discrepancy badge compares against the SAME days the upload actually
-- covers, not the full 7-day SAPE total, when an Excel upload is partial.
ALTER TABLE monitoring_weekly_stats ADD COLUMN adriver_partial_week BOOLEAN;
ALTER TABLE monitoring_weekly_stats ADD COLUMN adriver_coverage_start DATE;
ALTER TABLE monitoring_weekly_stats ADD COLUMN adriver_coverage_end DATE;
ALTER TABLE monitoring_weekly_stats ADD COLUMN adriver_scoped_impressions INTEGER;
ALTER TABLE monitoring_weekly_stats ADD COLUMN adriver_scoped_clicks INTEGER;
