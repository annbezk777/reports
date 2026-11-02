-- Stable numeric Google Sheets tab ID, used as a fallback lookup when
-- worksheet_name no longer matches (e.g. someone renamed the tab).
ALTER TABLE report_configs ADD COLUMN worksheet_gid INTEGER;
