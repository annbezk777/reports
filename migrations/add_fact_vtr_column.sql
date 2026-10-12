-- Migration: Add fact_vtr column to monitoring_campaigns table
-- Date: 2026-10-12
-- Description: Add fact_vtr (Video Through Rate / Visit Rate) column for storing actual VTR/VR data

-- Check if column exists before adding
-- SQLite doesn't support IF NOT EXISTS for columns, so we'll use a safer approach

-- Add fact_vtr column if it doesn't exist
-- For video formats (V, CTV) this stores VTR (%)
-- For banner/TGB formats (B, TGB) this stores VR (%)

-- Note: Run this command and ignore error if column already exists
ALTER TABLE monitoring_campaigns ADD COLUMN fact_vtr FLOAT;

-- Verify the column was added
-- SELECT name, type FROM pragma_table_info('monitoring_campaigns') WHERE name = 'fact_vtr';
