-- Manual per-card setting (task #46), toggled from a gear icon on the
-- monitoring card: which individual statistics columns to show. NULL
-- means "not configured" - show everything (minus the banner-without-KPI
-- VR default from task #48), same as before this setting existed.
ALTER TABLE monitoring_campaigns ADD COLUMN visible_columns JSON;
