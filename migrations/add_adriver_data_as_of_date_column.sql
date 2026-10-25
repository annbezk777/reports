-- Migration: Add adriver_data_as_of_date column to monitoring_campaigns table
-- Date: 2026-10-25
-- Description: Last date actually present in an uploaded Adriver/Sizmek
-- Excel export (parsed per-row from the file, not the upload timestamp) -
-- used to flag stale verifier data by file content, not by when the field
-- was last touched.

ALTER TABLE monitoring_campaigns ADD COLUMN adriver_data_as_of_date DATE;
