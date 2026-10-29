-- Weekly Weborama diff badge needs to know when a pixel only covered
-- part of the week (compare_date_from mid-week) so it can compare
-- against a correctly-scoped SAPE fact instead of the full 7 days.
ALTER TABLE monitoring_weekly_stats ADD COLUMN weborama_partial_week BOOLEAN;
ALTER TABLE monitoring_weekly_stats ADD COLUMN weborama_coverage_start DATE;
ALTER TABLE monitoring_weekly_stats ADD COLUMN weborama_scoped_impressions INTEGER;
ALTER TABLE monitoring_weekly_stats ADD COLUMN weborama_scoped_clicks INTEGER;
